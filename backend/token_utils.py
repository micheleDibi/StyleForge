"""
Utility per i limiti di output token dei modelli.

L'SDK Anthropic rifiuta con 400 le richieste in cui `max_tokens` supera il
massimo output del modello (per claude-opus-4-8: 128000). Le formule del tipo
`word_count * 2.5 + 2000` possono superarlo su testi molto lunghi: vanno sempre
limitate con `cap_output_tokens()`.
"""

import os

# Tetto di sicurezza leggermente sotto il massimo hard (128000) per lasciare margine.
MODEL_MAX_OUTPUT_TOKENS = int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "120000"))


def cap_output_tokens(n: int, ceiling: int = MODEL_MAX_OUTPUT_TOKENS) -> int:
    """Limita max_tokens al massimo output del modello, mantenendo almeno 1."""
    return max(1, min(int(n), ceiling))
