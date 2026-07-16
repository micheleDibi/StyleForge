"""
Limiter condiviso fra api.py e i router.

Perche' un modulo a parte: il Limiter viveva dentro api.py, che importa i
router, quindi un router non poteva usarlo senza import circolare. Da qui lo
importano entrambi.

Nota su cosa NON e' attivo: `Limiter(default_limits=[...])` in api.py non ha mai
limitato nulla. I default_limits li applica solo SlowAPIMiddleware, che non e'
registrato, e nel repo non c'e' un solo @limiter.limit. Accendere ora quel
middleware a 60/min per IP e' rischioso e non e' un fix di sicurezza: il
frontend fa polling ogni 5 secondi, e get_remote_address dietro nginx vede l'IP
del proxy, quindi tutti gli utenti di un ateneo o di un ufficio condividerebbero
lo stesso contatore e si prenderebbero 429 a vicenda.

Qui si mette invece un limite MIRATO sugli endpoint che fanno fetch di URL, con
chiave per-utente: un umano che incolla delle fonti non lo sfiora, mentre una
scansione automatica smette di essere gratis.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

import config


def user_or_ip(request: Request) -> str:
    """
    Chiave di rate limiting: l'utente se c'e' un Bearer valido, altrimenti l'IP.

    Per-utente e non per-IP perche' dietro un reverse proxy l'IP e' quello di
    nginx per tutti: un limite su quella chiave sarebbe di fatto globale, e un
    solo utente rumoroso basterebbe a bloccare gli altri.
    """
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        # Import locale: auth importa config, non rate_limit — cosi' resta senza cicli.
        from auth import decode_token

        token_data = decode_token(auth.split(" ", 1)[1])
        if token_data and token_data.user_id:
            return f"user:{token_data.user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=user_or_ip,
    default_limits=[f"{config.RATE_LIMIT_PER_MINUTE}/minute"],
)

# Endpoint che scaricano URL forniti dall'utente.
FETCH_LIMIT = "10/minute"
