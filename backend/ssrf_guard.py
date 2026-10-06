"""
Guard SSRF condivisa: valida e scarica gli URL influenzati dall'utente.

Perche' esiste: tre sink del backend fetchano URL che l'utente controlla (il
proxy video, gli allegati-URL della tesi, il download dei paper). Un'allowlist
di hostname non basta: non ferma un IP interno passato direttamente, ne' il DNS
rebinding. Qui la logica sta in un posto solo, cosi' i tre sink non divergono.

Contratto:
  - solo https (http viene promosso, mai fetchato in chiaro);
  - OGNI IP restituito dal DNS viene validato, non solo il primo;
  - la connessione va a un IP gia' validato (pinning), senza ri-risolvere il
    nome: e' cio' che chiude il DNS rebinding;
  - i redirect non li segue httpx: ogni hop viene ri-validato qui;
  - cap sui byte grezzi (una gzip bomb esplode PRIMA del contatore, se si
    contano i byte decompressi) + deadline wall-clock (httpx non ha un timeout
    complessivo: `read` e' per-operazione, quindi non ferma uno slow-drip).

MANUTENZIONE: il pinning sostituisce `_pool._network_backend`, che e' API
privata di httpx/httpcore. `test_ssrf_guard.py::TestPinning::test_hook_di_pinning_esiste_ancora`
fallisce se un upgrade la rimuove — senza quel hook la guard degraderebbe in
silenzio, che e' il modo peggiore in cui puo' rompersi.
"""

from __future__ import annotations

import asyncio
import functools
import ipaddress
import logging
import re
import socket
import time
import zlib
from dataclasses import dataclass
from typing import Callable, Collection, Iterable, Optional, Sequence
from urllib.parse import urlsplit, urlunsplit

import httpcore
import httpx

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_PORTS = frozenset({443})
DEFAULT_MAX_REDIRECTS = 3

_REDIRECT_STATUS = frozenset({301, 302, 303, 307, 308})

# Caratteri di controllo/spazio: urlsplit li STRIPPA silenziosamente, cambiando
# scheme e host sotto di noi ('ht\ntps://interno/' -> scheme='https'). Rifiutiamo
# l'URL prima di darlo in pasto al parser.
_FORBIDDEN_URL_CHARS = re.compile(r"[\x00-\x20\x7f]")

# Label numerica con zero iniziale ('0177'): getaddrinfo la interpreta come
# ottale su Linux e non su macOS. Rifiutarla evita che una guard testata sul Mac
# si comporti diversamente in produzione.
_LEADING_ZERO_LABEL = re.compile(r"^0[0-9]+$")

# ============================================================================
# RETI NON AMMESSE
# ============================================================================
# Perche' una deny-list esplicita OLTRE ai flag di ipaddress: i flag cambiano
# tra le patch release di CPython (gh-113171), la deny-list no. I flag restano
# come rinforzo, non come unica regola.

_DENY_V4 = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",           # "questa rete"
        "10.0.0.0/8",          # privata
        "100.64.0.0/10",       # CGNAT (e' il range di Tailscale: is_private=False!)
        "127.0.0.0/8",         # loopback
        "169.254.0.0/16",      # link-local: metadata cloud
        "172.16.0.0/12",       # privata
        "192.0.0.0/24",        # IETF protocol assignments
        "192.0.2.0/24",        # TEST-NET-1
        "192.88.99.0/24",      # 6to4 relay anycast
        "192.168.0.0/16",      # privata
        "198.18.0.0/15",       # benchmark
        "198.51.100.0/24",     # TEST-NET-2
        "203.0.113.0/24",      # TEST-NET-3
        "224.0.0.0/4",         # multicast (is_global=True!)
        "240.0.0.0/4",         # riservata
        "255.255.255.255/32",  # broadcast
    )
)

_DENY_V6 = tuple(
    ipaddress.ip_network(n)
    for n in (
        "::/96",             # IPv4-compatible (::127.0.0.1)
        "::1/128",           # loopback
        "::ffff:0:0/96",     # IPv4-mapped
        "::ffff:0:0:0/96",   # IPv4-translated
        "64:ff9b::/96",      # NAT64: su rete IPv6-only raggiunge DAVVERO 127.0.0.1
        "64:ff9b:1::/48",    # NAT64 locale
        "100::/64",          # discard-only
        "2001::/32",         # Teredo
        "2001:db8::/32",     # documentazione
        "2002::/16",         # 6to4 (2002:7f00:1:: -> 127.0.0.1)
        "fc00::/7",          # unique local
        "fe80::/10",         # link-local
        "ff00::/8",          # multicast
    )
)

# Prefissi che incapsulano un IPv4 negli ultimi 32 bit e per cui ipaddress NON
# espone alcun attributo di unwrap (ipv4_mapped/sixtofour/teredo non li vedono).
_EMBEDDED_V4_PREFIXES = tuple(
    ipaddress.ip_network(n)
    for n in ("::/96", "::ffff:0:0/96", "::ffff:0:0:0/96", "64:ff9b::/96", "64:ff9b:1::/48")
)


# ============================================================================
# ECCEZIONI
# ============================================================================

class GuardError(Exception):
    """Base: destinazione rifiutata o fetch abortito dalla guard."""


class SsrfBlocked(GuardError):
    """La destinazione non e' un endpoint pubblico ammesso."""

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"URL non consentito ({reason}): {url}")


class ResponseTooLarge(GuardError):
    """La risposta supera il cap di dimensione previsto per questo sink."""


class ContentTypeNotAllowed(GuardError):
    """Il Content-Type della risposta non e' fra quelli attesi."""


class FetchTimeout(GuardError):
    """Superato il time budget complessivo del fetch."""


@dataclass(frozen=True)
class ValidatedTarget:
    """Esito della validazione: l'URL da usare e gli IP a cui e' lecito connettersi."""

    url: str
    hostname: str
    ips: tuple[str, ...]
    port: int


@dataclass(frozen=True)
class GuardedResponse:
    """Risposta finale (dopo gli eventuali redirect), con il body gia' cappato."""

    url: str
    status_code: int
    headers: httpx.Headers
    content: bytes

    @property
    def text(self) -> str:
        encoding = self.headers.get("content-type", "")
        charset = "utf-8"
        if "charset=" in encoding:
            charset = encoding.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        try:
            return self.content.decode(charset, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


# ============================================================================
# VALIDAZIONE IP
# ============================================================================

def _unwrap_embedded_ipv4(ip: ipaddress.IPv6Address) -> Optional[ipaddress.IPv4Address]:
    """L'IPv4 incapsulato in un IPv6, se c'e'."""
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]  # (server, client): il client e' il target
    for net in _EMBEDDED_V4_PREFIXES:
        if ip in net:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def _ip_rejection_reason(ip: ipaddress._BaseAddress) -> Optional[str]:
    """Motivo per cui l'IP non e' una destinazione pubblica lecita, o None."""
    networks = _DENY_V4 if ip.version == 4 else _DENY_V6
    for net in networks:
        if ip in net:
            return f"IP in rete non pubblica {net} ({ip})"

    # I due flag prendono cose diverse e nessuno dei due basta da solo:
    # 100.64.0.1 e' is_private=False (lo prende solo `not is_global`),
    # 224.0.0.1 e' is_global=True (lo prende solo la lista dei flag).
    if not ip.is_global:
        return f"IP non globale ({ip})"
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return f"IP riservato ({ip})"

    if ip.version == 6:
        embedded = _unwrap_embedded_ipv4(ip)  # type: ignore[arg-type]
        if embedded is not None:
            inner = _ip_rejection_reason(embedded)
            if inner:
                return f"IPv6 che incapsula un IPv4 non ammesso -> {inner}"

    return None


# ============================================================================
# VALIDAZIONE URL
# ============================================================================

def _resolve(host: str, port: int) -> list[str]:
    """Risolve host -> lista di IP (stringhe), nell'ordine restituito dal resolver."""
    infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    ips: list[str] = []
    for _family, _type, _proto, _canon, sockaddr in infos:
        ip = sockaddr[0]
        if ip not in ips:
            ips.append(ip)
    return ips


def check_url_shape(
    url: str,
    *,
    allowed_ports: Collection[int] = DEFAULT_ALLOWED_PORTS,
) -> ValidatedTarget:
    """
    Controlli che NON richiedono rete: caratteri, scheme, userinfo, host, porta.

    Serve dove l'URL va validato al salvataggio, prima e indipendentemente dal
    fetch (e dove una risoluzione DNS sarebbe sia lenta sia inutile: puo'
    cambiare fra il salvataggio e il download). Il campo `ips` resta vuoto:
    solo validate_public_url risolve, ed e' l'unico che autorizza a connettersi.
    """
    if not isinstance(url, str) or not url.strip():
        raise SsrfBlocked(str(url), "URL vuoto")

    if _FORBIDDEN_URL_CHARS.search(url):
        raise SsrfBlocked(url, "l'URL contiene spazi o caratteri di controllo")

    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme == "http":
        # Promozione, non fetch in chiaro: rifiutare seccamente romperebbe gli
        # URL fonte incollati a mano, che sono ancora spesso http://.
        parts = parts._replace(scheme="https")
        url = urlunsplit(parts)
        scheme = "https"
    if scheme != "https":
        raise SsrfBlocked(url, f"schema non consentito: {parts.scheme or '(assente)'}")

    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL as exc:
        raise SsrfBlocked(url, f"URL non valido: {exc}") from exc

    if parsed.userinfo:
        raise SsrfBlocked(url, "le credenziali nell'URL non sono ammesse")

    raw_host = parsed.raw_host  # httpx CONNETTE su raw_host (punycode), non su .host
    if not raw_host:
        raise SsrfBlocked(url, "hostname assente")
    hostname = raw_host.decode("ascii").lower()

    for label in hostname.split("."):
        if _LEADING_ZERO_LABEL.match(label):
            raise SsrfBlocked(url, f"label numerica con zero iniziale: {label}")

    port = parsed.port or 443
    if port not in allowed_ports:
        raise SsrfBlocked(url, f"porta non consentita: {port}")

    # Se l'host e' gia' un IP letterale lo si giudica subito, senza DNS. E'
    # AGGIUNTIVO, non una scorciatoia: validate_public_url risolve e rivalida
    # comunque ogni record. La scorciatoia pericolosa sarebbe l'opposto —
    # "e' un letterale, salto il DNS" — perche' ip_address('0177.0.0.1') alza
    # ValueError pur essendo loopback su Linux.
    try:
        literal = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        reason = _ip_rejection_reason(literal)
        if reason:
            raise SsrfBlocked(url, reason)

    return ValidatedTarget(url=str(parsed), hostname=hostname, ips=(), port=port)


def validate_public_url(
    url: str,
    *,
    allowed_ports: Collection[int] = DEFAULT_ALLOWED_PORTS,
    resolve: Optional[Callable[[str, int], Sequence[str]]] = None,
) -> ValidatedTarget:
    """
    Valida un URL come destinazione pubblica e ne risolve gli IP.

    `resolve` e' iniettabile per i test. Il default NON va messo nella firma
    (`resolve=_resolve`): verrebbe catturato a def-time e il monkeypatch del
    modulo sarebbe ignorato, dando test che sembrano isolati ma fanno DNS vero.
    """
    resolver = resolve or _resolve

    shape = check_url_shape(url, allowed_ports=allowed_ports)
    url, hostname, port = shape.url, shape.hostname, shape.port

    try:
        ips = list(resolver(hostname, port))
    except socket.gaierror as exc:
        raise SsrfBlocked(url, f"risoluzione DNS fallita: {exc}") from exc

    if not ips:
        raise SsrfBlocked(url, "nessun indirizzo risolto")

    # Tutti gli IP devono essere pubblici: un round-robin con un record pubblico
    # e uno privato e' un bypass classico.
    for raw_ip in ips:
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError as exc:
            raise SsrfBlocked(url, f"indirizzo risolto non valido: {raw_ip!r}") from exc
        reason = _ip_rejection_reason(ip)
        if reason:
            raise SsrfBlocked(url, reason)

    return ValidatedTarget(url=url, hostname=hostname, ips=tuple(ips), port=port)


# ============================================================================
# PINNING
# ============================================================================
# Il pinning NON va fatto riscrivendo l'URL con l'IP: il pool di httpcore e'
# indicizzato su (scheme, host, port) e IGNORA sni_hostname, quindi due host
# sullo stesso IP si riciclerebbero la connessione TLS l'uno dell'altro.
# Pinnando nel network backend l'hostname resta nell'URL: il pool distingue gli
# origin, SNI e verifica del certificato restano corretti da soli, e
# url.join() sui redirect relativi continua a funzionare.

class _PinnedAsyncBackend(httpcore.AsyncNetworkBackend):
    """Connette solo agli IP gia' validati per quell'hostname."""

    def __init__(self, inner: httpcore.AsyncNetworkBackend, pins: dict[str, list[str]]):
        self._inner = inner
        self._pins = pins

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable] = None,
    ) -> httpcore.AsyncNetworkStream:
        ips = self._pins.get(host.lower())
        if not ips:
            raise SsrfBlocked(host, "host non validato (nessun IP pinnato)")
        last: Optional[BaseException] = None
        # Piu' IP con fallback in ordine: getaddrinfo restituisce l'IPv6 per primo
        # su doi.org e semanticscholar.org, e pinnare solo il primo renderebbe
        # ogni fonte accademica irraggiungibile da un deploy IPv4-only.
        for ip in ips:
            try:
                return await self._inner.connect_tcp(
                    ip,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # noqa: PERF203 - fallback per-IP, come create_connection
                last = exc
        assert last is not None
        raise last

    async def connect_unix_socket(self, *args, **kwargs) -> httpcore.AsyncNetworkStream:
        raise SsrfBlocked("unix://", "socket unix non consentiti")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class _PinnedSyncBackend(httpcore.NetworkBackend):
    """Variante sync di _PinnedAsyncBackend (per httpx.Client)."""

    def __init__(self, inner: httpcore.NetworkBackend, pins: dict[str, list[str]]):
        self._inner = inner
        self._pins = pins

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable] = None,
    ) -> httpcore.NetworkStream:
        ips = self._pins.get(host.lower())
        if not ips:
            raise SsrfBlocked(host, "host non validato (nessun IP pinnato)")
        last: Optional[BaseException] = None
        for ip in ips:
            try:
                return self._inner.connect_tcp(
                    ip,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # noqa: PERF203
                last = exc
        assert last is not None
        raise last

    def connect_unix_socket(self, *args, **kwargs) -> httpcore.NetworkStream:
        raise SsrfBlocked("unix://", "socket unix non consentiti")

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


def _pin_async_transport(transport: httpx.AsyncHTTPTransport, pins: dict[str, list[str]]) -> None:
    pool = transport._pool  # noqa: SLF001 - vedi nota di manutenzione in cima al modulo
    pool._network_backend = _PinnedAsyncBackend(pool._network_backend, pins)  # noqa: SLF001


def _pin_sync_transport(transport: httpx.HTTPTransport, pins: dict[str, list[str]]) -> None:
    pool = transport._pool  # noqa: SLF001
    pool._network_backend = _PinnedSyncBackend(pool._network_backend, pins)  # noqa: SLF001


# ============================================================================
# FETCH
# ============================================================================

def _base_headers(headers: Optional[dict]) -> dict:
    out = dict(headers or {})
    # Chiediamo identity: httpx decomprime senza max_length, quindi una gzip
    # bomb (misurata: ratio 1029x) verrebbe allocata INTERA prima che un
    # contatore sui byte decompressi possa abortire.
    out["Accept-Encoding"] = "identity"
    return out


def _headers_for_hop(headers: dict, previous_url: str, next_url: str) -> dict:
    """Con follow_redirects=False la pulizia cross-origin tocca a noi (httpx la fa da solo)."""
    prev, nxt = httpx.URL(previous_url), httpx.URL(next_url)
    same_origin = (prev.scheme, prev.host, prev.port) == (nxt.scheme, nxt.host, nxt.port)
    out = dict(headers)
    out.pop("Cookie", None)
    out.pop("cookie", None)
    if not same_origin:
        out.pop("Authorization", None)
        out.pop("authorization", None)
    return out


def _check_deadline(deadline: float, url: str) -> None:
    if time.monotonic() > deadline:
        raise FetchTimeout(f"time budget esaurito su {url}")


def _check_precondition(resp_headers: httpx.Headers, max_bytes: int,
                        allowed_content_types: Optional[Collection[str]], url: str) -> None:
    clen = resp_headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > max_bytes:
        raise ResponseTooLarge(f"Content-Length {clen} > {max_bytes} su {url}")
    if allowed_content_types is not None:
        ctype = (resp_headers.get("content-type") or "").lower()
        if not any(allowed in ctype for allowed in allowed_content_types):
            raise ContentTypeNotAllowed(f"Content-Type {ctype!r} non atteso su {url}")


def _decode_body(raw: bytes, content_encoding: Optional[str], max_bytes: int) -> bytes:
    """Decomprime con un tetto esplicito: il server puo' ignorare Accept-Encoding: identity."""
    enc = (content_encoding or "").strip().lower()
    if not enc or enc == "identity":
        return raw
    if enc in ("gzip", "x-gzip"):
        decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
    elif enc == "deflate":
        decomp = zlib.decompressobj()
    else:
        raise ResponseTooLarge(f"Content-Encoding non gestito: {enc}")
    out = decomp.decompress(raw, max_bytes + 1)
    if len(out) > max_bytes or decomp.unconsumed_tail:
        raise ResponseTooLarge(f"body decompresso oltre {max_bytes} byte (ratio sospetto)")
    return out


def _timeout(deadline_s: float) -> httpx.Timeout:
    connect = min(10.0, deadline_s)
    return httpx.Timeout(connect=connect, read=deadline_s, write=deadline_s, pool=connect)


async def safe_get(
    url: str,
    *,
    max_bytes: int,
    deadline_s: float,
    headers: Optional[dict] = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    allowed_ports: Collection[int] = DEFAULT_ALLOWED_PORTS,
    allowed_content_types: Optional[Collection[str]] = None,
    resolve: Optional[Callable[[str, int], Sequence[str]]] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> GuardedResponse:
    """
    GET di un URL non fidato: destinazione validata, IP pinnato, redirect
    ri-validati a ogni hop, body cappato, deadline complessiva.

    `transport` e' iniettabile per i test (MockTransport): in quel caso il
    pinning non si applica, perche' non si apre nessuna connessione reale.
    """
    deadline = time.monotonic() + deadline_s
    pins: dict[str, list[str]] = {}
    loop = asyncio.get_running_loop()

    injected = transport is not None
    client_transport = transport
    if client_transport is None:
        client_transport = httpx.AsyncHTTPTransport(retries=0)
        _pin_async_transport(client_transport, pins)

    hop_headers = _base_headers(headers)
    current = url

    async with httpx.AsyncClient(
        transport=client_transport,
        timeout=_timeout(deadline_s),
        follow_redirects=False,
    ) as client:
        for hop in range(max_redirects + 1):
            _check_deadline(deadline, current)

            # getaddrinfo e' bloccante: fuori dall'event loop.
            target = await loop.run_in_executor(
                None,
                functools.partial(
                    validate_public_url, current, allowed_ports=allowed_ports, resolve=resolve
                ),
            )
            if not injected:
                pins[target.hostname] = list(target.ips)

            async with client.stream("GET", target.url, headers=hop_headers) as resp:
                if resp.status_code in _REDIRECT_STATUS and "location" in resp.headers:
                    if hop >= max_redirects:
                        raise SsrfBlocked(current, f"troppi redirect (> {max_redirects})")
                    nxt = str(httpx.URL(target.url).join(resp.headers["location"]))
                    hop_headers = _headers_for_hop(hop_headers, target.url, nxt)
                    logger.info("SSRF guard: redirect %s -> %s", target.url, nxt)
                    current = nxt
                    continue

                _check_precondition(resp.headers, max_bytes, allowed_content_types, target.url)

                raw = bytearray()
                async for chunk in resp.aiter_raw():
                    _check_deadline(deadline, target.url)
                    raw += chunk
                    if len(raw) > max_bytes:
                        raise ResponseTooLarge(f"body oltre {max_bytes} byte su {target.url}")

                content = _decode_body(
                    bytes(raw), resp.headers.get("content-encoding"), max_bytes
                )
                return GuardedResponse(
                    url=str(resp.url),
                    status_code=resp.status_code,
                    headers=resp.headers,
                    content=content,
                )

    raise SsrfBlocked(url, f"troppi redirect (> {max_redirects})")


def safe_get_sync(
    url: str,
    *,
    max_bytes: int,
    deadline_s: float,
    headers: Optional[dict] = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    allowed_ports: Collection[int] = DEFAULT_ALLOWED_PORTS,
    allowed_content_types: Optional[Collection[str]] = None,
    resolve: Optional[Callable[[str, int], Sequence[str]]] = None,
    transport: Optional[httpx.BaseTransport] = None,
) -> GuardedResponse:
    """Variante sync di safe_get (serve a llm_wiki/paper_downloader.py)."""
    deadline = time.monotonic() + deadline_s
    pins: dict[str, list[str]] = {}

    injected = transport is not None
    client_transport = transport
    if client_transport is None:
        client_transport = httpx.HTTPTransport(retries=0)
        _pin_sync_transport(client_transport, pins)

    hop_headers = _base_headers(headers)
    current = url

    with httpx.Client(
        transport=client_transport,
        timeout=_timeout(deadline_s),
        follow_redirects=False,
    ) as client:
        for hop in range(max_redirects + 1):
            _check_deadline(deadline, current)

            target = validate_public_url(current, allowed_ports=allowed_ports, resolve=resolve)
            if not injected:
                pins[target.hostname] = list(target.ips)

            with client.stream("GET", target.url, headers=hop_headers) as resp:
                if resp.status_code in _REDIRECT_STATUS and "location" in resp.headers:
                    if hop >= max_redirects:
                        raise SsrfBlocked(current, f"troppi redirect (> {max_redirects})")
                    nxt = str(httpx.URL(target.url).join(resp.headers["location"]))
                    hop_headers = _headers_for_hop(hop_headers, target.url, nxt)
                    logger.info("SSRF guard: redirect %s -> %s", target.url, nxt)
                    current = nxt
                    continue

                _check_precondition(resp.headers, max_bytes, allowed_content_types, target.url)

                raw = bytearray()
                for chunk in resp.iter_raw():
                    _check_deadline(deadline, target.url)
                    raw += chunk
                    if len(raw) > max_bytes:
                        raise ResponseTooLarge(f"body oltre {max_bytes} byte su {target.url}")

                content = _decode_body(
                    bytes(raw), resp.headers.get("content-encoding"), max_bytes
                )
                return GuardedResponse(
                    url=str(resp.url),
                    status_code=resp.status_code,
                    headers=resp.headers,
                    content=content,
                )

    raise SsrfBlocked(url, f"troppi redirect (> {max_redirects})")
