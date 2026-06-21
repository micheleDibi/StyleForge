"""
Pipeline anti-rilevamento AI condivisa — unica fonte di verità.

Estratta dalla pipeline della Tesi (`thesis_routes._apply_anti_ai`) per poter
applicare lo STESSO identico meccanismo anti-AI a:
  - generazione di contenuto su sessione addestrata (`claude_client.generazione`)
  - umanizzazione di testo su sessione addestrata (`claude_client.umanizzazione`)
  - generazione delle tesi (`thesis_routes._apply_anti_ai`, ora un wrapper)

Due componenti:
  1. ANTI_AI_PROMPT_BLOCK — istruzioni anti-AI di livello prompt, register-respecting:
     da iniettare IDENTICHE nei prompt di generazione e umanizzazione.
  2. apply_anti_ai_pipeline() — post-processing in 3 stage:
       Stage 0  parafrasi controllata ricorsiva (DIPPER-style) — leva principale
       Stage 1  riscrittura de-AI accademica via LLM — opzionale (off di default)
       Stage 2  pass algoritmico (anti_ai_processor) register-safe
     Preserva citazioni [x], note {{nota}}, registro e lunghezza (floor 90%).
"""

import logging

from ai_exceptions import InsufficientCreditsError

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# BLOCCO PROMPT ANTI-AI CONDIVISO (register-respecting)
# ═══════════════════════════════════════════════════════════════════════════
# Da concatenare nei prompt di generazione e umanizzazione (NON contiene `{}`,
# ma per sicurezza va iniettato per concatenazione, non dentro un'f-string).
# Obiettivo: rimuovere SOLO i tic generici da modello, RISPETTANDO lo stile
# dell'autore appreso in addestramento (qualunque ne sia il registro).
ANTI_AI_PROMPT_BLOCK = """
═══════════════════════════════════════════════════════════════
ANTI-RILEVAMENTO AI — RISPETTANDO LO STILE DELL'AUTORE
═══════════════════════════════════════════════════════════════
Il testo non deve sembrare generato da un'intelligenza artificiale. I rilevatori
riconoscono i pattern troppo regolari e le formule da modello: elimina quei tic
SENZA tradire la voce dell'autore appresa in addestramento.

REGOLA DI SALVAGUARDIA (PRIORITARIA SU TUTTO IL RESTO):
- Rispetta il registro e le idiosincrasie genuine dell'autore. NON forzare un tono
  colloquiale né uno accademico se non è il suo.
- Se l'autore usa periodi lunghi, latinismi, incisi con trattino, punto e virgola,
  citazioni o strutture bilanciate, MANTIENILE: sono firma stilistica, non difetti.
- Non aggiungere autocorrezioni, esitazioni, "errori finti", interiezioni o casi
  inventati se non appartengono allo stile dell'autore.

TIC GENERICI DA AI DA EVITARE (questi sì, sempre):
- Formule da manuale: "è importante notare/sottolineare", "vale la pena", "in
  conclusione", "in definitiva", "in ultima analisi", "appare evidente", "occorre".
- Attacchi formulaici di paragrafo: "In questo contesto…", "Per quanto riguarda…",
  "Nel panorama…", "Nell'ambito di…", "Nel mondo di oggi…".
- Transizioni meccaniche ripetute a inizio frase: "Inoltre", "Pertanto", "Dunque",
  "Tuttavia" usate in serie.
- Ritmo robotico: frasi tutte della stessa lunghezza. Varia la lunghezza in modo
  naturale (burstiness), come fa un autore umano.
- Parallelismi/tricolon e antitesi bilanciate ("non solo… ma anche", "da un lato…
  dall'altro") inseriti MECCANICAMENTE quando non sono nello stile dell'autore.
- Chiuse a effetto, massime o aforismi a fine paragrafo se l'autore non li usa.
- Artefatti di formattazione: titoli o elenchi markdown non richiesti, emoji,
  preamboli tipo "Ecco il testo:", "Certo,". Consegna solo il testo.
"""


def anti_ai_block() -> str:
    """Restituisce il blocco prompt anti-AI condiviso."""
    return ANTI_AI_PROMPT_BLOCK


# ═══════════════════════════════════════════════════════════════════════════
# POST-PROCESSING IN 3 STAGE
# ═══════════════════════════════════════════════════════════════════════════
def apply_anti_ai_pipeline(
    text: str,
    profile: str = 'academic',
    target_words: int = 0,
    seed=None,
    *,
    paraphrase_enabled: bool = True,
    paraphrase_rounds: int = 2,
    paraphrase_model=None,
    rewrite_enabled: bool = False,
    rewrite_model=None,
    algo_enabled: bool = True,
    label: str = 'testo',
) -> str:
    """
    Applica gli stage anti-rilevamento AI al testo:
      0) PARAFRASI CONTROLLATA ricorsiva (DIPPER-style) — leva principale.
      1) (opzionale, off di default) riscrittura de-AI via LLM.
      2) pass algoritmico (anti_ai_processor) col profilo dato.

    profile: 'academic' (register-safe, no colloquialismi — autori formali / tesi)
        oppure 'informal' (anti-AI completo con register-preserving paraphrase).
    Gli import dei moduli pesanti sono lazy (come nella pipeline Tesi originale)
    per evitare import circolari. Su InsufficientCreditsError rilancia; sugli altri
    errori degrada al testo dello stage precedente.
    """
    if not text or not text.strip():
        return text

    result = text
    original_words = len(text.split())

    # Stage 0: parafrasi controllata ricorsiva (leva principale)
    if paraphrase_enabled:
        try:
            from ai_client import controlled_paraphrase
            result = controlled_paraphrase(
                result,
                model_id=paraphrase_model,
                rounds=paraphrase_rounds,
                target_words=max(original_words, target_words),
                profile=profile,
            )
        except InsufficientCreditsError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Parafrasi controllata errore per '{label}': {e}; tengo il testo precedente")

    # Stage 1: riscrittura de-AI accademica (LLM) — opzionale, off di default
    if rewrite_enabled:
        try:
            from ai_client import academic_deai_rewrite
            rewritten = academic_deai_rewrite(result, model_id=rewrite_model)
            floor = int(max(original_words, target_words) * 0.9)
            if len(rewritten.split()) >= floor:
                result = rewritten
        except InsufficientCreditsError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Anti-AI rewrite errore per '{label}': {e}; uso il testo pre-rewrite")

    # Stage 2: pass algoritmico (anti_ai_processor)
    if algo_enabled:
        try:
            from anti_ai_processor import humanize_text_post_processing
            result = humanize_text_post_processing(result, profile=profile, seed=seed)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Anti-AI algo pass errore per '{label}': {e}")

    return result
