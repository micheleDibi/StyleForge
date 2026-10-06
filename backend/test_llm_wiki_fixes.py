"""
Test unitari per i fix dell'ingest wiki (nessun DB/rete: client Anthropic finto,
filesystem in tmp_path).

- _run_tool_loop: risposta troncata (stop=max_tokens) con tool_use -> niente
  tool_use orfani nella conversazione, nessun tool eseguito.
- run_ingest: se un batch fallisce, la conversazione torna a com'era prima del
  batch e il successivo riparte valido.
- count_wiki_pages: sottocartelle mancanti non fanno esplodere (500 su /wiki/status).
- restore_snapshot: scambio tramite cartella temporanea.

Esecuzione: python3 -m pytest test_llm_wiki_fixes.py -q
"""

import os
from types import SimpleNamespace

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

import pytest

import config
from llm_wiki import wiki_runner, wiki_workspace


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool_use(id_, name="write_file", path="wiki/fonti/x.md"):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input={"path": path})


def _resp(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


class FakeClient:
    """Restituisce le risposte in ordine; un'eccezione nella lista viene sollevata."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []  # snapshot dei messages inviati a ogni chiamata
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(list(kwargs["messages"]))
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _tool_use_ids(messages):
    return [
        b.id
        for m in messages if m["role"] == "assistant"
        for b in m["content"] if getattr(b, "type", None) == "tool_use"
    ]


def _loop(client, messages, tmp_path):
    return wiki_runner._run_tool_loop(
        client=client, system=[], messages=messages, tools=[],
        wiki_root=tmp_path, model="m", max_tokens=10,
    )


@pytest.fixture
def no_dispatch(monkeypatch):
    def _boom(**kwargs):
        raise AssertionError("tool troncato eseguito")
    monkeypatch.setattr(wiki_runner.wiki_tools, "dispatch_tool", _boom)


# --- (a) tool_use troncati -------------------------------------------------

def test_max_tokens_scarta_tool_use_e_tiene_il_testo(tmp_path, no_dispatch):
    client = FakeClient([_resp("max_tokens", [_text("ok"), _tool_use("t1"), _tool_use("t2")])])
    messages = [{"role": "user", "content": "go"}]
    resp, stats = _loop(client, messages, tmp_path)

    assert stats.last_stop_reason == "max_tokens"
    assert len(messages) == 2
    assert [b.type for b in messages[1]["content"]] == ["text"]
    assert _tool_use_ids(messages) == []


def test_max_tokens_solo_tool_use_non_appende_turno_vuoto(tmp_path, no_dispatch):
    client = FakeClient([_resp("max_tokens", [_tool_use("t1")])])
    messages = [{"role": "user", "content": "go"}]
    _loop(client, messages, tmp_path)

    assert messages == [{"role": "user", "content": "go"}]


def test_tool_use_normale_resta_invariato(tmp_path, monkeypatch):
    monkeypatch.setattr(wiki_runner.wiki_tools, "dispatch_tool", lambda **kw: '{"ok": true}')
    client = FakeClient([
        _resp("tool_use", [_tool_use("t1")]),
        _resp("end_turn", [_text("fatto")]),
    ])
    messages = [{"role": "user", "content": "go"}]
    _, stats = _loop(client, messages, tmp_path)

    assert stats.write_calls == 1
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[2]["content"][0]["tool_use_id"] == "t1"


# --- (b) rollback della conversazione su batch fallito ---------------------

def test_run_ingest_batch_fallito_non_sporca_il_successivo(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    files = [raw / "a.md", raw / "b.md"]
    for f in files:
        f.write_text("x", encoding="utf-8")

    monkeypatch.setattr(wiki_workspace, "get_wiki_root", lambda tid: tmp_path)
    monkeypatch.setattr(wiki_workspace, "list_raw_files", lambda tid: files)
    monkeypatch.setattr(config, "WIKI_INGEST_BATCH_SIZE", 1)
    monkeypatch.setattr(wiki_runner, "_load_constitution", lambda: "costituzione")
    monkeypatch.setattr(wiki_runner.wiki_tools, "dispatch_tool", lambda **kw: '{"ok": true}')

    client = FakeClient([
        _resp("tool_use", [_tool_use("t1")]),       # batch 1, iter 0
        RuntimeError("400 tool_use senza tool_result"),  # batch 1, iter 1
        _resp("tool_use", [_tool_use("t2")]),       # batch 2, iter 0
        _resp("end_turn", [_text("fatto")]),        # batch 2, iter 1
    ])
    monkeypatch.setattr(wiki_runner, "get_claude_client", lambda: SimpleNamespace(client=client))

    summary = wiki_runner.run_ingest("tesi")

    assert len(summary.errors) == 1 and summary.errors[0].startswith("batch 1:")
    batch2_first = client.calls[2]
    # Conversazione azzerata: il batch 2 riparte dal prompt completo, senza residui del batch 1.
    assert len(batch2_first) == 1
    assert batch2_first[0]["role"] == "user"
    assert "Batch corrente 2/2" in batch2_first[0]["content"]
    assert "PROCEDURA OBBLIGATORIA" in batch2_first[0]["content"]
    assert "t1" not in _tool_use_ids(client.calls[3])


# --- (d) count_wiki_pages con sottocartelle mancanti -----------------------

def test_count_wiki_pages_salta_sottocartelle_mancanti(tmp_path, monkeypatch):
    monkeypatch.setattr(wiki_workspace, "get_wiki_root", lambda tid: tmp_path)
    assert wiki_workspace.count_wiki_pages("tesi") == 0  # wiki/ assente

    (tmp_path / "wiki" / "fonti").mkdir(parents=True)
    (tmp_path / "wiki" / "fonti" / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "wiki" / "fonti" / "b.txt").write_text("x", encoding="utf-8")
    (tmp_path / "wiki" / "concetti").mkdir()
    (tmp_path / "wiki" / "concetti" / "c.md").write_text("x", encoding="utf-8")

    assert wiki_workspace.count_wiki_pages("tesi") == 2


# --- (e) restore_snapshot ---------------------------------------------------

def test_restore_snapshot_scambia_e_pulisce(tmp_path, monkeypatch):
    monkeypatch.setattr(wiki_workspace, "get_wiki_root", lambda tid: tmp_path)
    (tmp_path / "wiki" / "fonti").mkdir(parents=True)
    (tmp_path / "wiki" / "fonti" / "nuova.md").write_text("nuova", encoding="utf-8")
    backup = tmp_path / "wiki.bak.20260101-000000"
    (backup / "fonti").mkdir(parents=True)
    (backup / "fonti" / "vecchia.md").write_text("vecchia", encoding="utf-8")

    wiki_workspace.restore_snapshot("tesi", backup)

    assert (tmp_path / "wiki" / "fonti" / "vecchia.md").read_text(encoding="utf-8") == "vecchia"
    assert not (tmp_path / "wiki" / "fonti" / "nuova.md").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["wiki"]


def test_restore_snapshot_senza_wiki_corrente(tmp_path, monkeypatch):
    monkeypatch.setattr(wiki_workspace, "get_wiki_root", lambda tid: tmp_path)
    backup = tmp_path / "wiki.bak.20260101-000000"
    (backup / "fonti").mkdir(parents=True)

    wiki_workspace.restore_snapshot("tesi", backup)

    assert (tmp_path / "wiki" / "fonti").is_dir()
    assert not backup.exists()


# --- (f) paper_downloader: anti-collisione con slug gia' al limite ----------

def test_materialize_one_collisione_slug_lungo_termina(tmp_path, monkeypatch):
    from llm_wiki import paper_downloader

    # Guardia: con la regressione il ciclo girerebbe all'infinito, cosi' fallisce.
    calls = []
    real = paper_downloader.make_raw_filename

    def counted(*args, **kwargs):
        calls.append(args)
        assert len(calls) < 10, "ciclo anti-collisione non termina"
        return real(*args, **kwargs)

    monkeypatch.setattr(paper_downloader, "make_raw_filename", counted)

    att = SimpleNamespace(
        id="att-1",
        original_filename="parola " * 30,  # slug > 80 char -> troncato al limite
        extracted_text="",
        file_path="",  # nessun URL: niente rete
    )
    paper_dir = tmp_path / "raw" / "paper"
    paper_dir.mkdir(parents=True)
    base = wiki_workspace.make_raw_filename(None, "parola " * 30)
    assert len(base) == 80 + len(".md")
    (paper_dir / base).write_text("esistente", encoding="utf-8")

    res = paper_downloader._materialize_one(att, tmp_path)

    nuovo = tmp_path / res.raw_path
    assert nuovo.exists() and nuovo.name != base
    assert (paper_dir / base).read_text(encoding="utf-8") == "esistente"
