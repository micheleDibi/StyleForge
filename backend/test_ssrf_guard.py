"""
Test unitari per ssrf_guard (nessun DB/rete/API key: il resolver e il transport
sono iniettati).

Esecuzione: python3 -m pytest test_ssrf_guard.py -q
"""

import asyncio
import os
import zlib

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

import httpx
import pytest

import ssrf_guard
from ssrf_guard import (
    ContentTypeNotAllowed,
    GuardError,
    ResponseTooLarge,
    SsrfBlocked,
    safe_get,
    safe_get_sync,
    validate_public_url,
)

PUBLIC_IP = "93.184.216.34"


def _resolver(*ips):
    """Resolver fisso: nessuna rete."""
    return lambda host, port: list(ips)


def _boom(exc):
    def _r(host, port):
        raise exc
    return _r


def _run(coro):
    """pytest-asyncio non e' fra le dipendenze: si gira l'evento a mano."""
    return asyncio.run(coro)


# ═══════════════════════════════════════════ REGOLA IP ═══════════════════════

# Ogni riga e' un IP che DEVE essere rifiutato. I tre casi commentati sono
# quelli che sfuggono a una regola sola: senza l'unione delle regole passano.
BLOCKED_IPS = [
    "127.0.0.1",
    "127.1.1.1",
    "10.0.0.1",
    "172.16.0.1",
    "192.168.1.1",
    "169.254.169.254",       # metadata cloud
    "0.0.0.0",
    "100.64.0.1",            # CGNAT: is_private=False -> lo prende solo `not is_global`
    "224.0.0.1",             # multicast: is_global=True -> lo prende solo la lista flag
    "240.0.0.1",
    "255.255.255.255",
    "198.18.0.1",
    "192.0.2.1",
    "203.0.113.1",
    "192.88.99.1",
    "::1",
    "fe80::1",
    "fc00::1",
    "ff02::1",
    "100::1",
    "2001:db8::1",
    "::ffff:127.0.0.1",      # IPv4-mapped
    "2002:7f00:1::",         # 6to4 -> 127.0.0.1: sfugge a ENTRAMBE le regole, serve l'unwrap
    "2002:a9fe:a9fe::",      # 6to4 -> 169.254.169.254
    "64:ff9b::7f00:1",       # NAT64 -> 127.0.0.1 (raggiungibile davvero su rete IPv6-only)
    "64:ff9b:1::7f00:1",     # NAT64 locale
    "::127.0.0.1",           # IPv4-compatible
    "::ffff:0:7f00:1",       # IPv4-translated
    "2001:0:4136:e378:8000:63bf:3fff:fdd2",  # Teredo
]

PUBLIC_IPS = ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700:4700::1111", "2a00:1450:4001:800::200e"]


class TestRegolaIP:
    @pytest.mark.parametrize("ip", BLOCKED_IPS)
    def test_ip_interni_rifiutati(self, ip):
        with pytest.raises(SsrfBlocked):
            validate_public_url("https://ok.example/x", resolve=_resolver(ip))

    @pytest.mark.parametrize("ip", PUBLIC_IPS)
    def test_ip_pubblici_ammessi(self, ip):
        t = validate_public_url("https://ok.example/x", resolve=_resolver(ip))
        assert t.ips == (ip,)

    def test_tutti_gli_ip_devono_essere_pubblici(self):
        # Round-robin con un record pubblico e uno privato: bypass classico.
        with pytest.raises(SsrfBlocked, match="127.0.0.1"):
            validate_public_url("https://ok.example/x", resolve=_resolver(PUBLIC_IP, "127.0.0.1"))

    def test_lista_multipla_tutta_pubblica_passa(self):
        t = validate_public_url(
            "https://ok.example/x", resolve=_resolver("2606:4700::1111", "8.8.8.8")
        )
        assert len(t.ips) == 2


# ═══════════════════════════════════════ VALIDAZIONE URL ═════════════════════

class TestValidazioneUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "gopher://interno:70/x",
            "ftp://interno/x",
            "javascript:alert(1)",
            "data:text/html,<b>x</b>",
        ],
    )
    def test_schemi_non_https_rifiutati(self, url):
        with pytest.raises(SsrfBlocked, match="schema"):
            validate_public_url(url, resolve=_resolver(PUBLIC_IP))

    def test_http_viene_promosso_a_https(self):
        t = validate_public_url("http://ok.example/pagina", resolve=_resolver(PUBLIC_IP))
        assert t.url.startswith("https://")

    def test_http_con_porta_80_esplicita_non_passa(self):
        # Promosso a https, la porta 80 resta e non e' in allowlist: giusto cosi'.
        with pytest.raises(SsrfBlocked, match="porta"):
            validate_public_url("http://ok.example:80/x", resolve=_resolver(PUBLIC_IP))

    @pytest.mark.parametrize(
        "url",
        [
            "ht\ntps://interno/x",   # urlsplit strippa il \n e lo scheme diventa https
            "https://ok.example/x\r\nHost: interno",
            "https://ok.example/\tx",
            "https://ok example/x",
        ],
    )
    def test_caratteri_di_controllo_rifiutati(self, url):
        with pytest.raises(SsrfBlocked, match="controllo"):
            validate_public_url(url, resolve=_resolver(PUBLIC_IP))

    def test_userinfo_rifiutato(self):
        with pytest.raises(SsrfBlocked, match="credenziali"):
            validate_public_url("https://user:pw@ok.example/x", resolve=_resolver(PUBLIC_IP))

    @pytest.mark.parametrize("port", [22, 80, 8080, 6379, 11211])
    def test_porte_non_ammesse(self, port):
        with pytest.raises(SsrfBlocked, match="porta"):
            validate_public_url(f"https://ok.example:{port}/x", resolve=_resolver(PUBLIC_IP))

    def test_label_con_zero_iniziale_rifiutata(self):
        # 0177.0.0.1 e' ottale su Linux e non su macOS: rifiutarla evita che la
        # guard si comporti diversamente fra dev e produzione.
        # La forma nuda la rifiuta gia' httpx ("Invalid IPv4 address"); quella col
        # punto finale NON e' un IPv4 letterale per httpx e arriva alla nostra regola.
        with pytest.raises(SsrfBlocked):
            validate_public_url("https://0177.0.0.1/x", resolve=_resolver(PUBLIC_IP))
        with pytest.raises(SsrfBlocked, match="zero iniziale"):
            validate_public_url("https://0177.0.0.1./x", resolve=_resolver(PUBLIC_IP))

    def test_dns_fallito_e_fail_closed(self):
        import socket as _socket

        with pytest.raises(SsrfBlocked, match="DNS"):
            validate_public_url("https://inesistente.example/x", resolve=_boom(_socket.gaierror("nope")))

    def test_nessun_ip_risolto(self):
        with pytest.raises(SsrfBlocked, match="nessun indirizzo"):
            validate_public_url("https://ok.example/x", resolve=_resolver())

    @pytest.mark.parametrize("url", ["", "   ", "https://", "https:///path"])
    def test_url_degeneri(self, url):
        with pytest.raises(SsrfBlocked):
            validate_public_url(url, resolve=_resolver(PUBLIC_IP))

    def test_forme_alternative_passano_dal_dns_non_da_scorciatoie(self, monkeypatch):
        # Il valore di questo test: se un domani qualcuno aggiunge un ramo
        # "se e' gia' un IP letterale salto il DNS", queste forme lo aggirano.
        visti = []

        def fake(host, port):
            visti.append(host)
            return ["127.0.0.1"]

        for url in ["https://2130706433/x", "https://127.1/x", "https://0/x", "https://[::1]/x"]:
            with pytest.raises(SsrfBlocked):
                validate_public_url(url, resolve=fake)
        assert len(visti) == 4, "ogni forma deve passare dal resolver, senza scorciatoie"

    def test_resolver_di_default_e_monkeypatchabile(self, monkeypatch):
        # Invariante di design: `resolve or _resolve` dentro il corpo, MAI
        # `resolve=_resolve` nella firma (verrebbe catturato a def-time e i test
        # farebbero DNS vero pur sembrando isolati).
        monkeypatch.setattr(ssrf_guard, "_resolve", _resolver("127.0.0.1"))
        with pytest.raises(SsrfBlocked):
            validate_public_url("https://ok.example/x")


# ═══════════════════════════════════════════ REDIRECT ════════════════════════

def _mock(handler):
    return httpx.MockTransport(handler)


def _resp(status=200, body=b"", headers=None):
    """
    Risposta finta con stream NON letto.

    `httpx.Response(200, content=b'..')` legge subito lo stream e iter_raw()
    diventa inutilizzabile: e' un artefatto della costruzione diretta, non del
    codice sotto test. I transport veri consegnano uno stream ancora da leggere,
    ed e' quello che ByteStream riproduce.
    """
    return httpx.Response(status, stream=httpx.ByteStream(body), headers=headers or {})


class TestRedirect:
    def test_redirect_verso_interno_bloccato(self):
        def handler(request):
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

        def resolve(host, port):
            return [PUBLIC_IP] if host == "ok.example" else ["169.254.169.254"]

        with pytest.raises(SsrfBlocked, match="169.254.169.254"):
            _run(safe_get(
                "https://ok.example/x", max_bytes=1000, deadline_s=5,
                resolve=resolve, transport=_mock(handler),
            ))

    def test_redirect_protocol_relative_rivalidato(self):
        # '//interno/x' cambia host senza sembrare assoluto.
        def handler(request):
            if request.url.host == "ok.example":
                return httpx.Response(302, headers={"location": "//interno.example/x"})
            return _resp(200, b"segreto")

        def resolve(host, port):
            return [PUBLIC_IP] if host == "ok.example" else ["10.0.0.5"]

        with pytest.raises(SsrfBlocked, match="10.0.0.5"):
            _run(safe_get(
                "https://ok.example/x", max_bytes=1000, deadline_s=5,
                resolve=resolve, transport=_mock(handler),
            ))

    def test_redirect_relativo_risolto_contro_url_corrente(self):
        def handler(request):
            if request.url.path == "/a":
                return httpx.Response(302, headers={"location": "/b"})
            assert str(request.url) == "https://ok.example/b"
            return _resp(200, b"ok")

        r = _run(safe_get(
            "https://ok.example/a", max_bytes=1000, deadline_s=5,
            resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
        ))
        assert r.content == b"ok"
        assert r.url == "https://ok.example/b"

    def test_troppi_redirect(self):
        def handler(request):
            return httpx.Response(302, headers={"location": "https://ok.example/next"})

        with pytest.raises(SsrfBlocked, match="troppi redirect"):
            _run(safe_get(
                "https://ok.example/x", max_bytes=1000, deadline_s=5, max_redirects=2,
                resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
            ))

    def test_authorization_strippata_cross_origin(self):
        visti = {}

        def handler(request):
            visti[request.url.host] = dict(request.headers)
            if request.url.host == "ok.example":
                return httpx.Response(302, headers={"location": "https://altro.example/x"})
            return _resp(200, b"ok")

        _run(safe_get(
            "https://ok.example/x", max_bytes=1000, deadline_s=5,
            headers={"Authorization": "Bearer segreto", "Cookie": "s=1"},
            resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
        ))
        assert "authorization" in visti["ok.example"]
        assert "authorization" not in visti["altro.example"], "token perso verso un altro host!"
        assert "cookie" not in visti["altro.example"]


# ═══════════════════════════════════════════ CAP / BUDGET ════════════════════

class TestCap:
    def test_content_length_oltre_il_cap(self):
        def handler(request):
            return _resp(200, b"x" * 100, {"content-length": "100"})

        with pytest.raises(ResponseTooLarge, match="Content-Length"):
            _run(safe_get(
                "https://ok.example/x", max_bytes=10, deadline_s=5,
                resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
            ))

    def test_body_oltre_il_cap_senza_content_length(self):
        def handler(request):
            return _resp(200, b"x" * 5000)

        with pytest.raises(ResponseTooLarge):
            _run(safe_get(
                "https://ok.example/x", max_bytes=100, deadline_s=5,
                resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
            ))

    def test_gzip_bomb_non_esplode(self):
        # 5 MB di 'A' -> pochi KB compressi: il cap sui byte grezzi passerebbe,
        # ed e' esattamente il motivo per cui serve il tetto in decompressione.
        bomb = zlib.compress(b"A" * (5 * 1024 * 1024))
        assert len(bomb) < 20_000

        def handler(request):
            return _resp(200, bomb, {"content-encoding": "deflate"})

        with pytest.raises(ResponseTooLarge, match="ratio|decompresso"):
            _run(safe_get(
                "https://ok.example/x", max_bytes=64 * 1024, deadline_s=5,
                resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
            ))

    def test_content_type_non_atteso(self):
        def handler(request):
            return _resp(200, b"<html>", {"content-type": "text/html"})

        with pytest.raises(ContentTypeNotAllowed):
            _run(safe_get(
                "https://ok.example/x.pdf", max_bytes=1000, deadline_s=5,
                allowed_content_types={"pdf"},
                resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
            ))

    def test_chiediamo_identity(self):
        visti = {}

        def handler(request):
            visti.update(request.headers)
            return _resp(200, b"ok")

        _run(safe_get(
            "https://ok.example/x", max_bytes=1000, deadline_s=5,
            resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
        ))
        assert visti["accept-encoding"] == "identity"

    def test_fetch_legittimo_passa(self):
        def handler(request):
            return _resp(200, b"<html>contenuto</html>",
                         {"content-type": "text/html; charset=utf-8"})

        r = _run(safe_get(
            "https://ok.example/x", max_bytes=10_000, deadline_s=5,
            resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
        ))
        assert r.status_code == 200
        assert "contenuto" in r.text


class TestVarianteSync:
    def test_sync_blocca_interni(self):
        with pytest.raises(SsrfBlocked):
            safe_get_sync(
                "https://ok.example/x", max_bytes=1000, deadline_s=5,
                resolve=_resolver("169.254.169.254"),
                transport=_mock(lambda r: _resp(200, b"x")),
            )

    def test_sync_legittimo_passa(self):
        def handler(request):
            return _resp(200, b"%PDF-1.4", {"content-type": "application/pdf"})

        r = safe_get_sync(
            "https://ok.example/p.pdf", max_bytes=1000, deadline_s=5,
            allowed_content_types={"pdf"},
            resolve=_resolver(PUBLIC_IP), transport=_mock(handler),
        )
        assert r.content.startswith(b"%PDF")


# ═══════════════════════════════════════════ PINNING ═════════════════════════

class _FakeInner:
    """Backend finto: registra a quale IP ci si e' connessi, e puo' fallire."""

    def __init__(self, falliscono=()):
        self.tentati = []
        self.falliscono = set(falliscono)

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.tentati.append(host)
        if host in self.falliscono:
            raise OSError(f"no route to {host}")
        return f"stream->{host}"

    async def sleep(self, seconds):
        return None


class TestPinning:
    def test_hook_di_pinning_esiste_ancora(self):
        # Se questo test fallisce dopo un upgrade di httpx/httpcore, il pinning
        # NON sta piu' funzionando: la guard degraderebbe in silenzio.
        t = httpx.AsyncHTTPTransport()
        assert hasattr(t, "_pool"), "httpx.AsyncHTTPTransport._pool sparito"
        assert hasattr(t._pool, "_network_backend"), "httpcore pool._network_backend sparito"
        s = httpx.HTTPTransport()
        assert hasattr(s._pool, "_network_backend")

    def test_pinning_applicato_al_transport(self):
        t = httpx.AsyncHTTPTransport()
        pins = {"ok.example": [PUBLIC_IP]}
        ssrf_guard._pin_async_transport(t, pins)
        assert isinstance(t._pool._network_backend, ssrf_guard._PinnedAsyncBackend)

    def test_connette_allip_pinnato_non_allhostname(self):
        inner = _FakeInner()
        b = ssrf_guard._PinnedAsyncBackend(inner, {"ok.example": [PUBLIC_IP]})
        out = _run(b.connect_tcp("ok.example", 443))
        assert inner.tentati == [PUBLIC_IP], "si e' connesso al nome: il DNS verrebbe ri-risolto"
        assert out == f"stream->{PUBLIC_IP}"

    def test_fallback_multi_ip(self):
        # getaddrinfo mette l'IPv6 per primo su doi.org e semanticscholar.org:
        # su un deploy IPv4-only pinnare solo ips[0] romperebbe ogni fonte.
        inner = _FakeInner(falliscono={"2606:4700::1111"})
        b = ssrf_guard._PinnedAsyncBackend(inner, {"doi.example": ["2606:4700::1111", "8.8.8.8"]})
        out = _run(b.connect_tcp("doi.example", 443))
        assert inner.tentati == ["2606:4700::1111", "8.8.8.8"]
        assert out == "stream->8.8.8.8"

    def test_tutti_gli_ip_falliscono_propaga(self):
        inner = _FakeInner(falliscono={"8.8.8.8"})
        b = ssrf_guard._PinnedAsyncBackend(inner, {"x.example": ["8.8.8.8"]})
        with pytest.raises(OSError):
            _run(b.connect_tcp("x.example", 443))

    def test_host_non_pinnato_e_fail_closed(self):
        b = ssrf_guard._PinnedAsyncBackend(_FakeInner(), {})
        with pytest.raises(SsrfBlocked):
            _run(b.connect_tcp("sconosciuto.example", 443))

    def test_unix_socket_rifiutato(self):
        b = ssrf_guard._PinnedAsyncBackend(_FakeInner(), {})
        with pytest.raises(SsrfBlocked):
            _run(b.connect_unix_socket("/tmp/x.sock"))

    def test_rebinding_il_pin_vince_sulla_seconda_risoluzione(self):
        # Il resolver risponde pubblico alla validazione e interno subito dopo:
        # il backend deve usare l'IP gia' validato, non ri-risolvere.
        risposte = [[PUBLIC_IP], ["127.0.0.1"]]

        def resolve(host, port):
            return risposte.pop(0) if risposte else ["127.0.0.1"]

        target = validate_public_url("https://ok.example/x", resolve=resolve)
        pins = {target.hostname: list(target.ips)}
        inner = _FakeInner()
        b = ssrf_guard._PinnedAsyncBackend(inner, pins)
        _run(b.connect_tcp("ok.example", 443))
        assert inner.tentati == [PUBLIC_IP], "ha ri-risolto il nome: rebinding possibile"


class TestGerarchiaEccezioni:
    def test_tutto_deriva_da_guarderror(self):
        # paper_downloader cattura GuardError: se una sottoclasse sfugge, un URL
        # bloccato fa saltare l'intero ingest dei paper.
        for exc in (SsrfBlocked("https://x/", "r"), ResponseTooLarge("x"),
                    ContentTypeNotAllowed("x"), ssrf_guard.FetchTimeout("x")):
            assert isinstance(exc, GuardError)

    def test_ssrfblocked_porta_url_e_motivo(self):
        e = SsrfBlocked("https://interno/x", "IP riservato")
        assert e.url == "https://interno/x"
        assert e.reason == "IP riservato"
