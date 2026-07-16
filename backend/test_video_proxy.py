"""
Test di regressione per /api/video/proxy (nessun DB/rete: auth e fetch sono
sostituiti via dependency_overrides e monkeypatch).

Codificano il PoC di vuln-0001: l'endpoint non deve piu' accettare un URL dal
client, e deve pretendere un admin vero.

Esecuzione: python3 -m pytest test_video_proxy.py -q
"""

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import ssrf_guard
import video_routes
from auth import get_current_admin_user

VIDEO = b"\x00\x00\x00\x18ftypmp42" + b"x" * 512


class FakeAdmin:
    id = "11111111-1111-1111-1111-111111111111"
    is_admin = True
    is_active = True


def _app(admin=True):
    app = FastAPI()
    app.include_router(video_routes.router)
    if admin:
        app.dependency_overrides[get_current_admin_user] = lambda: FakeAdmin()
    else:
        def _nega():
            raise HTTPException(status_code=403, detail="Permessi insufficienti")
        app.dependency_overrides[get_current_admin_user] = _nega
    return TestClient(app)


@pytest.fixture(autouse=True)
def _minimax_configurata(monkeypatch):
    monkeypatch.setattr(video_routes.config, "MINIMAX_API_KEY", "chiave-finta")


def _risolve_in(monkeypatch, url):
    async def _fake(file_id):
        return url
    monkeypatch.setattr(video_routes.minimax_service, "retrieve_file_url", _fake)


def _guard_restituisce(monkeypatch, content=VIDEO, status=200):
    async def _fake(url, **kwargs):
        return ssrf_guard.GuardedResponse(
            url=url, status_code=status, headers=httpx.Headers({}), content=content
        )
    monkeypatch.setattr(video_routes.ssrf_guard, "safe_get", _fake)


class TestPocVuln0001:
    def test_lurl_non_e_piu_un_parametro(self, monkeypatch):
        # Il PoC del report non e' piu' nemmeno esprimibile: senza file_id la
        # richiesta e' malformata, e `url` viene semplicemente ignorato.
        _risolve_in(monkeypatch, "https://cdn.minimax.example/v.mp4")
        _guard_restituisce(monkeypatch)
        r = _app().get(
            "/api/video/proxy",
            params={"url": "http://169.254.169.254/latest/meta-data/", "token": "qualsiasi"},
        )
        assert r.status_code == 422, "l'endpoint accetta ancora un URL dal client!"

    def test_un_url_interno_non_raggiunge_il_fetch(self, monkeypatch):
        chiamate = []

        async def _spia(url, **kwargs):
            chiamate.append(url)
            return ssrf_guard.GuardedResponse(url, 200, httpx.Headers({}), b"")

        monkeypatch.setattr(video_routes.ssrf_guard, "safe_get", _spia)
        _risolve_in(monkeypatch, "https://cdn.minimax.example/v.mp4")
        r = _app().get(
            "/api/video/proxy",
            params={"file_id": "abc123", "url": "http://169.254.169.254/latest/meta-data/"},
        )
        assert r.status_code == 200
        assert chiamate == ["https://cdn.minimax.example/v.mp4"], "l'URL del client e' arrivato al fetch!"

    def test_niente_token_in_query(self, monkeypatch):
        # Il token in query finiva in access log, Referer e cronologia: ora
        # l'auth passa dall'header e `token` non e' piu' un parametro.
        import inspect

        params = inspect.signature(video_routes.proxy_video).parameters
        assert "token" not in params
        assert "url" not in params
        assert "file_id" in params


class TestAutorizzazione:
    def test_serve_un_admin(self, monkeypatch):
        # Prima questa route faceva un jwt.decode a mano e passava qualsiasi
        # utente autenticato, anche disabilitato.
        _risolve_in(monkeypatch, "https://cdn.minimax.example/v.mp4")
        _guard_restituisce(monkeypatch)
        r = _app(admin=False).get("/api/video/proxy", params={"file_id": "abc123"})
        assert r.status_code == 403

    def test_senza_credenziali_e_401(self):
        # Senza override: la dependency vera chiede un Bearer. Se qualcuno
        # rimettesse un decode manuale del token, questo test lo direbbe.
        app = FastAPI()
        app.include_router(video_routes.router)
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/api/video/proxy", params={"file_id": "abc"}).status_code == 401


class TestValidazione:
    @pytest.mark.parametrize(
        "file_id",
        ["../etc/passwd", "abc def", "a" * 200, "", "x?y=1", "http://interno/"],
    )
    def test_file_id_malformato(self, file_id, monkeypatch):
        _risolve_in(monkeypatch, "https://cdn.minimax.example/v.mp4")
        _guard_restituisce(monkeypatch)
        r = _app().get("/api/video/proxy", params={"file_id": file_id})
        assert r.status_code in (400, 422)


class TestFlussoLegittimo:
    def test_il_video_arriva(self, monkeypatch):
        _risolve_in(monkeypatch, "https://cdn.minimax.example/v.mp4")
        _guard_restituisce(monkeypatch)
        r = _app().get("/api/video/proxy", params={"file_id": "abc123"})
        assert r.status_code == 200
        assert r.content == VIDEO
        assert r.headers["content-type"] == "video/mp4"

    def test_non_e_piu_cacheabile_pubblicamente(self, monkeypatch):
        # Era "public, max-age=3600" su una risposta autenticata.
        _risolve_in(monkeypatch, "https://cdn.minimax.example/v.mp4")
        _guard_restituisce(monkeypatch)
        r = _app().get("/api/video/proxy", params={"file_id": "abc123"})
        assert r.headers["cache-control"] == "private, no-store"

    def test_guard_che_blocca_non_fa_uscire_byte(self, monkeypatch):
        async def _bloccata(url, **kwargs):
            raise ssrf_guard.SsrfBlocked(url, "IP riservato")

        _risolve_in(monkeypatch, "https://cdn.minimax.example/v.mp4")
        monkeypatch.setattr(video_routes.ssrf_guard, "safe_get", _bloccata)
        r = _app().get("/api/video/proxy", params={"file_id": "abc123"})
        assert r.status_code == 502
        assert b"IP riservato" not in r.content, "il motivo interno e' uscito al client"

    def test_minimax_irraggiungibile(self, monkeypatch):
        async def _esplode(file_id):
            raise ValueError("MiniMax file retrieve failed")

        monkeypatch.setattr(video_routes.minimax_service, "retrieve_file_url", _esplode)
        r = _app().get("/api/video/proxy", params={"file_id": "abc123"})
        assert r.status_code == 502
