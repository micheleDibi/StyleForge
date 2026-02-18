"""
Eccezioni personalizzate per errori AI (crediti insufficienti, quota, rate limit).

Centralizza la logica di rilevamento errori di crediti/quota
per tutti i provider AI (OpenAI, Anthropic/Claude).
"""

import re
import logging

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """
    Eccezione sollevata quando il provider AI segnala crediti insufficienti,
    quota esaurita o rate limit superato.

    Attributi:
        provider: Il provider AI che ha generato l'errore ("openai" o "claude")
        original_error: L'errore originale dal provider
        user_message: Messaggio leggibile per l'utente
    """

    def __init__(self, provider: str, original_error: Exception, user_message: str = None):
        self.provider = provider
        self.original_error = original_error
        self.user_message = user_message or self._default_message(provider)
        super().__init__(self.user_message)

    @staticmethod
    def _default_message(provider: str) -> str:
        if provider == "openai":
            return (
                "Crediti OpenAI insufficienti. "
                "Verifica il tuo piano e il saldo su https://platform.openai.com/account/billing"
            )
        elif provider == "claude":
            return (
                "Crediti Anthropic/Claude insufficienti. "
                "Verifica il tuo piano e il saldo su https://console.anthropic.com/settings/billing"
            )
        return f"Crediti insufficienti per il provider {provider}."


# ============================================================================
# PATTERN DI ERRORE PER PROVIDER
# ============================================================================

# OpenAI: errori di crediti/quota/billing
OPENAI_CREDIT_PATTERNS = [
    "insufficient_quota",
    "billing_hard_limit_reached",
    "rate_limit_exceeded",
    "exceeded your current quota",
    "you exceeded your current quota",
    "insufficient funds",
    "billing issue",
    "account deactivated",
    "past due",
    "payment required",
    "quota exceeded",
]

# Anthropic/Claude: errori di crediti/quota/billing
CLAUDE_CREDIT_PATTERNS = [
    "credit balance is too low",
    "insufficient credit",
    "rate_limit_error",
    "overloaded_error",
    "billing",
    "exceeded.*quota",
    "account.*suspended",
    "payment.*required",
    "credit.*exhausted",
    "usage.*limit",
]


def check_openai_error(error: Exception) -> None:
    """
    Controlla se un errore OpenAI e' relativo a crediti/quota.
    Se si', solleva InsufficientCreditsError. Altrimenti rilancia l'errore originale.

    Args:
        error: L'eccezione catturata dalla chiamata OpenAI

    Raises:
        InsufficientCreditsError: Se l'errore e' di crediti/quota
    """
    error_str = str(error).lower()
    error_type = type(error).__name__

    # Controlla il tipo di errore OpenAI
    # openai.RateLimitError (429), openai.AuthenticationError (401)
    if error_type in ("RateLimitError", "APIStatusError"):
        # Controlla se e' un errore di quota (429 con "insufficient_quota")
        if any(pattern in error_str for pattern in OPENAI_CREDIT_PATTERNS):
            user_msg = _extract_openai_message(error)
            logger.error(f"OpenAI crediti insufficienti: {error}")
            raise InsufficientCreditsError("openai", error, user_msg) from error

    if error_type == "AuthenticationError":
        logger.error(f"OpenAI errore autenticazione: {error}")
        raise InsufficientCreditsError(
            "openai", error,
            "Chiave API OpenAI non valida o scaduta. Verifica la configurazione."
        ) from error

    # Controlla anche per pattern generici nella stringa dell'errore
    for pattern in OPENAI_CREDIT_PATTERNS:
        if pattern in error_str:
            user_msg = _extract_openai_message(error)
            logger.error(f"OpenAI crediti/quota errore (pattern match): {error}")
            raise InsufficientCreditsError("openai", error, user_msg) from error

    # Controlla HTTP status code se disponibile
    status_code = getattr(error, 'status_code', None) or getattr(error, 'http_status', None)
    if status_code in (402, 429):
        user_msg = _extract_openai_message(error)
        logger.error(f"OpenAI HTTP {status_code}: {error}")
        raise InsufficientCreditsError("openai", error, user_msg) from error


def check_claude_error(error: Exception) -> None:
    """
    Controlla se un errore Anthropic/Claude e' relativo a crediti/quota.
    Se si', solleva InsufficientCreditsError. Altrimenti rilancia l'errore originale.

    Args:
        error: L'eccezione catturata dalla chiamata Claude

    Raises:
        InsufficientCreditsError: Se l'errore e' di crediti/quota
    """
    error_str = str(error).lower()
    error_type = type(error).__name__

    # Controlla il tipo di errore Anthropic
    # anthropic.RateLimitError (429), anthropic.AuthenticationError (401)
    if error_type == "RateLimitError":
        user_msg = _extract_claude_message(error)
        logger.error(f"Claude rate limit / crediti: {error}")
        raise InsufficientCreditsError("claude", error, user_msg) from error

    if error_type == "AuthenticationError":
        logger.error(f"Claude errore autenticazione: {error}")
        raise InsufficientCreditsError(
            "claude", error,
            "Chiave API Anthropic non valida o scaduta. Verifica la configurazione."
        ) from error

    # Controlla pattern nella stringa dell'errore
    for pattern in CLAUDE_CREDIT_PATTERNS:
        if re.search(pattern, error_str):
            user_msg = _extract_claude_message(error)
            logger.error(f"Claude crediti/quota errore (pattern match): {error}")
            raise InsufficientCreditsError("claude", error, user_msg) from error

    # Controlla HTTP status code se disponibile
    status_code = getattr(error, 'status_code', None) or getattr(error, 'http_status', None)
    if status_code in (402, 429):
        user_msg = _extract_claude_message(error)
        logger.error(f"Claude HTTP {status_code}: {error}")
        raise InsufficientCreditsError("claude", error, user_msg) from error


def _extract_openai_message(error: Exception) -> str:
    """Estrae un messaggio leggibile dall'errore OpenAI."""
    error_str = str(error).lower()

    if "insufficient_quota" in error_str or "exceeded your current quota" in error_str:
        return (
            "Crediti OpenAI esauriti. "
            "Ricarica il tuo account su https://platform.openai.com/account/billing"
        )
    if "rate_limit_exceeded" in error_str:
        return (
            "Limite di richieste OpenAI superato. "
            "Attendi qualche minuto e riprova, oppure verifica il tuo piano."
        )
    if "billing_hard_limit_reached" in error_str:
        return (
            "Raggiunto il limite di spesa massimo su OpenAI. "
            "Aumenta il limite su https://platform.openai.com/account/billing"
        )
    return InsufficientCreditsError._default_message("openai")


def _extract_claude_message(error: Exception) -> str:
    """Estrae un messaggio leggibile dall'errore Claude/Anthropic."""
    error_str = str(error).lower()

    if "credit balance is too low" in error_str or "insufficient credit" in error_str:
        return (
            "Crediti Anthropic esauriti. "
            "Ricarica il tuo account su https://console.anthropic.com/settings/billing"
        )
    if "rate_limit" in error_str:
        return (
            "Limite di richieste Anthropic superato. "
            "Attendi qualche minuto e riprova, oppure verifica il tuo piano."
        )
    if "overloaded" in error_str:
        return (
            "I server Anthropic sono sovraccarichi al momento. "
            "Attendi qualche minuto e riprova."
        )
    return InsufficientCreditsError._default_message("claude")
