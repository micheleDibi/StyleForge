"""
Test di regressione SSRF sugli allegati della tesi (nessun DB/rete veri: la
sessione e' finta e il fetch e' sostituito).

Codificano i PoC di vuln-0002 e quello del sink che il report non ha visto
(/attachments/papers, dove full_text_url arriva dal payload del client).

Esecuzione: python3 -m pytest test_thesis_attachments_ssrf.py -q
"""

import os
import uuid
from datetime import datetime

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import ssrf_guard
import thesis_routes
from auth import get_current_active_user, require_permission
from database import get_db
from rate_limit import limiter

PAGINA = b"<html><head><title>Fonte pubblica</title></head><body><main>Contenuto della fonte.</main></body></html>"

# URL che l'endpoint rifiuta PRIMA di qualsiasi I/O, guardando solo la forma.
# `localhost` e i nomi che risolvono all'interno non stanno qui: quelli li ferma
# la guard al momento del fetch, quando risolve il DNS (test dedicato sotto, e
# copertura completa in test_ssrf_guard.py).
INTERNI = [
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
    "http://127.0.0.1:8000/admin",
    "https://10.0.0.1/interno",
    "https://192.168.1.1/router",
    "https://[::1]/x",
    "https://2002:7f00:1::/x",
    "file:///etc/passwd",
    "gopher://interno:70/x",
    "https://user:pw@ok.example/x",
]


class _FakeQuery:
    def filter(self, *a, **k):
        return self

    def count(self):
        return 0


class FakeDB:
    def __init__(self):
        self.added = []

    def query(self, *a, **k):
        return _FakeQuery()

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        obj.id = uuid.uuid4()
        obj.created_at = datetime.utcnow()


class FakeUser:
    id = uuid.uuid4()
    is_active = True
    is_admin = True  # require_permission('thesis') passa dal ramo admin
    role = None


class FakeThesis:
    id = uuid.uuid4()


@pytest.fixture(autouse=True)
def _azzera_rate_limit():
    """
    Il limite e' per-utente e i test condividono lo stesso utente finto: senza
    reset, dall'undicesima richiesta in poi arriverebbero dei 429 e i test si
    romperebbero a vicenda a seconda dell'ordine.
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def db():
    return FakeDB()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(thesis_routes, "get_thesis_by_id", lambda *a, **k: FakeThesis())
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(thesis_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: FakeUser()
    return TestClient(app)


@pytest.fixture
def fetch_spia(monkeypatch):
    """Registra ogni URL realmente fetchato: la lista deve restare vuota sui PoC."""
    chiamate = []

    async def _fake(url, **kwargs):
        chiamate.append(url)
        return ssrf_guard.GuardedResponse(
            url=url,
            status_code=200,
            headers=httpx.Headers({"content-type": "text/html"}),
            content=PAGINA,
        )

    monkeypatch.setattr(thesis_routes.ssrf_guard, "safe_get", _fake)
    return chiamate


def _post_urls(client, urls):
    return client.post(f"/api/thesis/{FakeThesis.id}/attachments/urls", json={"urls": urls})


# ═════════════════════════════════ PoC vuln-0002 ═════════════════════════════

class TestPocVuln0002:
    @pytest.mark.parametrize("url", INTERNI)
    def test_url_interni_rifiutati_senza_fetch(self, client, fetch_spia, url):
        r = _post_urls(client, [url])
        assert r.status_code == 400, f"{url} non e' stato bloccato"
        assert "non consentito" in r.json()["detail"]
        assert fetch_spia == [], "la destinazione e' stata comunque contattata"

    def test_un_solo_url_cattivo_ferma_tutta_la_richiesta(self, client, fetch_spia):
        # Validare tutto PRIMA di fetchare: altrimenti i tempi di risposta
        # raccontano quali porte interne sono aperte, chiuse o filtrate.
        r = _post_urls(client, ["https://fonte.example/a", "http://169.254.169.254/"])
        assert r.status_code == 400
        assert fetch_spia == [], "ha gia' fetchato il primo URL: oracolo di scansione"

    def test_nessun_allegato_creato(self, client, db, fetch_spia):
        _post_urls(client, ["http://169.254.169.254/latest/meta-data/"])
        assert db.added == []

    def test_il_titolo_interno_non_torna_al_client(self, client, fetch_spia):
        # original_filename e' il <title> della pagina fetchata ed e' mostrato in
        # UI: era un oracolo di lettura anche senza extracted_text.
        r = _post_urls(client, ["http://169.254.169.254/"])
        assert "Fonte pubblica" not in r.text

    def test_nome_che_risolve_allinterno_diventa_400(self, client, monkeypatch):
        # Un hostname pubblico che punta a un IP interno (o un servizio DNS tipo
        # nip.io) passa i controlli di forma: lo ferma la guard quando risolve.
        # Qui si verifica solo che l'endpoint traduca quel blocco in un 400 e non
        # se lo mangi nell'except generico.
        async def _bloccata(url, **kwargs):
            raise ssrf_guard.SsrfBlocked(url, "IP in rete non pubblica 127.0.0.0/8")

        monkeypatch.setattr(thesis_routes.ssrf_guard, "safe_get", _bloccata)
        r = _post_urls(client, ["https://127-0-0-1.nip.io/admin"])
        assert r.status_code == 400
        assert "non consentito" in r.json()["detail"]


class TestOracoli:
    def test_il_motivo_del_blocco_non_distingue_i_casi(self, client, fetch_spia):
        # Stessa risposta per "IP privato" e "porta chiusa": niente da leggere.
        risposte = {
            _post_urls(client, [u]).json()["detail"].replace(u, "<url>")
            for u in ["http://127.0.0.1/", "https://10.0.0.1/", "https://192.168.1.1/"]
        }
        assert len(risposte) == 1, f"i messaggi discriminano fra destinazioni: {risposte}"


# ═════════════════════════════ flusso legittimo ══════════════════════════════

class TestFlussoLegittimo:
    def test_url_pubblico_diventa_allegato(self, client, db, fetch_spia):
        r = _post_urls(client, ["https://fonte.example/articolo"])
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1
        assert fetch_spia == ["https://fonte.example/articolo"]
        assert db.added[0].extracted_text.startswith("Contenuto")
        assert db.added[0].original_filename == "Fonte pubblica"

    def test_http_pubblico_viene_promosso_a_https(self, client, fetch_spia):
        # Rifiutarlo seccamente romperebbe gli URL incollati a mano.
        r = _post_urls(client, ["http://fonte.example/articolo"])
        assert r.status_code == 200
        assert fetch_spia == ["https://fonte.example/articolo"]

    def test_una_fonte_giu_non_rompe_le_altre(self, client, db, monkeypatch):
        async def _fake(url, **kwargs):
            if "rotta" in url:
                raise httpx.ConnectError("giu'")
            return ssrf_guard.GuardedResponse(url, 200, httpx.Headers({}), PAGINA)

        monkeypatch.setattr(thesis_routes.ssrf_guard, "safe_get", _fake)
        r = client.post(
            f"/api/thesis/{FakeThesis.id}/attachments/urls",
            json={"urls": ["https://rotta.example/x", "https://fonte.example/ok"]},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_lista_vuota_rifiutata(self, client):
        assert _post_urls(client, []).status_code == 422

    def test_titolo_lunghissimo_non_fa_esplodere_linsert(self, client, db, monkeypatch):
        # original_filename e' String(500): prima un <title> piu' lungo finiva
        # nell'except generico e l'URL spariva senza spiegazioni.
        lungo = b"<html><head><title>" + b"T" * 900 + b"</title></head><body>x</body></html>"

        async def _fake(url, **kwargs):
            return ssrf_guard.GuardedResponse(url, 200, httpx.Headers({}), lungo)

        monkeypatch.setattr(thesis_routes.ssrf_guard, "safe_get", _fake)
        r = _post_urls(client, ["https://fonte.example/x"])
        assert r.status_code == 200
        assert len(db.added[0].original_filename) <= 500


# ══════════════════════ sink papers (assente dal report) ═════════════════════

def _paper(full_text_url=None, doi=None):
    return {
        "id": "p1",
        "title": "Un paper",
        "authors": ["Tizio"],
        "doi": doi,
        "full_text_url": full_text_url,
    }


def _post_papers(client, paper):
    return client.post(
        f"/api/thesis/{FakeThesis.id}/attachments/papers",
        json={"items": [{"paper": paper}]},
    )


class TestRateLimit:
    def test_il_limite_per_utente_morde(self, client, fetch_spia):
        # Non e' una difesa SSRF (quella e' la guard): serve a non regalare una
        # scansione gratuita di host pubblici usando il server come proxy.
        for i in range(10):
            assert _post_urls(client, [f"https://fonte.example/{i}"]).status_code == 200
        assert _post_urls(client, ["https://fonte.example/oltre"]).status_code == 429


class TestSinkPapers:
    @pytest.mark.parametrize("url", ["http://169.254.169.254/", "https://127.0.0.1/x", "https://10.0.0.1/p.pdf"])
    def test_full_text_url_interno_rifiutato_al_salvataggio(self, client, db, url):
        # Questo URL sarebbe stato scaricato DOPO, dalla pipeline wiki, dentro
        # un BackgroundTask: SSRF differita e persistente.
        r = _post_papers(client, _paper(full_text_url=url))
        assert r.status_code == 400, r.text
        assert db.added == []

    def test_schema_non_http_viene_azzerato_non_salvato(self, client, db):
        # Il validator del modello lo annulla: il paper resta, l'URL sparisce.
        r = _post_papers(client, _paper(full_text_url="file:///etc/passwd", doi="10.1000/182"))
        assert r.status_code == 200
        assert db.added[0].file_path == "doi:10.1000/182"

    def test_url_pubblico_viene_salvato(self, client, db):
        r = _post_papers(client, _paper(full_text_url="https://arxiv.example/pdf/1706.03762"))
        assert r.status_code == 200
        assert db.added[0].file_path == "https://arxiv.example/pdf/1706.03762"
