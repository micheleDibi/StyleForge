"""
Client per Claude Opus 4.8 con funzionalità di addestramento e generazione.

Questo modulo fornisce due funzionalità principali:
1. ADDESTRAMENTO: Invia un file con un prompt a Claude per "addestrare" il contesto
2. GENERAZIONE: Genera contenuto basandosi sul contesto dell'addestramento

Nota: Claude non viene realmente "addestrato" - il contesto viene mantenuto
nella conversazione per simulare un comportamento simile.
"""

import os
import re
import random
import fitz
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv, find_dotenv
from tqdm import tqdm
from ai_exceptions import InsufficientCreditsError, check_claude_error
from anti_ai_pipeline import ANTI_AI_PROMPT_BLOCK, apply_anti_ai_pipeline
from token_utils import cap_output_tokens

load_dotenv(find_dotenv())

MAX_TOKENS_TRAIN = 4096 # Numero di token utilizzati per la generazione di testo utilizzando Claude (4096 token sono circa 3000 parole in inglese, un po' meno in italiano)
MAX_TOKENS_TEST = 8192

API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Direttiva di imitazione dello stile, ri-iniettata in testa a ogni prompt di
# generazione/riscrittura per applicare in modo MARCATO il profilo appreso (il
# profilo resta in conversation_history ma va ri-enfatizzato a ogni chiamata).
STYLE_IMITATION_DIRECTIVE = """
═══════════════════════════════════════════════════════════════════════════════
IMITAZIONE DELLO STILE — PRIORITÀ ASSOLUTA
═══════════════════════════════════════════════════════════════════════════════
Applica in modo MARCATO e RICONOSCIBILE il profilo stilistico dell'autore che hai
prodotto durante l'addestramento: costruzione e lunghezza dei periodi, lessico e
parole-chiave ricorrenti, punteggiatura e ritmo, stilemi e costruzioni-firma. Se il
profilo include una SCHEDA OPERATIVA DI IMITAZIONE, applicala punto per punto.
NON fare modifiche leggere o caute: il risultato deve suonare INEQUIVOCABILMENTE come
scritto da quell'autore, non come una parafrasi neutra. Mantieni però INTATTI il
significato, i dati, le citazioni [x] e i marcatori di nota ⟦N…⟧.
"""

# Aggiunta usata nelle passate di rifinitura (intensify=True).
STYLE_INTENSIFY_NOTE = """
PASSATA DI RIFINITURA: il testo che ricevi è già una riscrittura. Intensifica
ULTERIORMENTE lo stile dell'autore (sintassi, lessico, ritmo, stilemi) rispetto a
questo testo, senza alterarne il significato, le citazioni [x] né i marcatori di nota.
"""

# Prompt MAP dell'addestramento: estrae osservazioni stilistiche da UN estratto.
OSSERVAZIONI_PROMPT = """Stai analizzando l'estratto __I__ di __N__ di un'unica opera dell'autore. Produci OSSERVAZIONI stilistiche STRUTTURATE e CONCRETE su QUESTO estratto (non un profilo finale, non conclusioni generali). Per ciascuna dimensione annota ciò che emerge QUI, con brevi esempi verbatim tratti dall'estratto:

- SINTASSI: lunghezza e costruzione dei periodi, subordinazione/coordinazione, incisi, posizione del verbo, costruzioni marcate.
- LESSICO: registro, parole-chiave ricorrenti, tecnicismi/latinismi/forestierismi, collocazioni personali.
- PUNTEGGIATURA E RITMO: uso di punto e virgola, due punti, trattini, virgolette; lunghezza dei paragrafi; ritmo.
- RETORICA E ARGOMENTAZIONE: figure preferite, modo di introdurre e sviluppare, gestione delle fonti.
- IDIOSINCRASIE: intercalari, attacchi di frase/paragrafo, modi di chiudere, vezzi, rapporto col lettore.
- COGNIZIONE: densità del pensiero, esplicitazione, livello di astrazione, gestione dell'incertezza.
- ESEMPLARI: 3-5 frasi-firma VERBATIM tratte da QUESTO estratto.

Sii sintetico ma specifico. Solo le osservazioni, nessun preambolo."""


def lettura_pdf(file_path: str, max_pagine=None) -> str:
    """Estrae il testo da un PDF. Se max_pagine è None legge TUTTE le pagine."""
    doc = fitz.open(file_path)
    pagine_da_leggere = len(doc) if max_pagine is None else min(max_pagine, len(doc))
    testo = ""
    for i in tqdm(range(pagine_da_leggere), desc="Lettura PDF"):
        testo += doc[i].get_text()
    doc.close()
    return testo


def _read_full_document(file_path: Path) -> str:
    """Legge l'INTERO documento (nessun cap). PDF via fitz (tutte le pagine);
    docx/txt via attachment_processor."""
    ext = file_path.suffix.lower()
    if ext == '.pdf':
        return lettura_pdf(str(file_path), max_pagine=None)
    try:
        from attachment_processor import extract_text
        return extract_text(file_path)
    except Exception:  # noqa: BLE001
        return lettura_pdf(str(file_path), max_pagine=None)

class ClaudeClient:
    """Client per interagire con Claude Opus 4.8 mantenendo il contesto della sessione."""

    MODEL_ID = "claude-opus-4-8"

    def __init__(self):
        """
        Inizializza il client Claude.
        """

        self.client = Anthropic(api_key=API_KEY)
        self.conversation_history: list[dict] = []
        self.system_prompt: str = """
            Sei un analista linguistico e redattore di altissimo livello. Riceverai in
            allegato una o più fonti di un autore (libri, articoli, saggi, pubblicazioni
            scientifiche). Il tuo compito è interiorizzarne fedelmente la voce — registro,
            sintassi, lessico, ritmo, punteggiatura, idiosincrasie — qualunque ne sia il
            registro (formale o informale, accademico o colloquiale), senza normalizzarla
            né giudicarla, e, quando richiesto, produrre testi indistinguibili dai suoi.
        """
        self.is_trained: bool = False

    def addestramento(self, file_path: str, progress_cb=None) -> str:
        """
        Addestramento: analizza l'INTERO documento (nessun cap di pagine) e produce un
        PROFILO STILISTICO completo. Per documenti lunghi usa un'analisi iterativa
        map-reduce (osservazioni per blocco → sintesi). Salva nella sessione SOLO il
        profilo distillato (non il testo sorgente), così le generazioni restano leggere.
        """
        import config
        from document_humanizer import split_into_chunks

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Il file non esiste: {file_path}")

        full_text = _read_full_document(file_path)
        if not full_text.strip():
            raise ValueError(f"Il file è vuoto: {file_path}")

        prompt_addestramento = (Path(__file__).parent / "prompt_addestramento.txt").read_text(encoding="utf-8")
        profile_max = getattr(config, 'TRAIN_PROFILE_MAX_TOKENS', 16000)
        chunk_words = getattr(config, 'TRAIN_CHUNK_WORDS', 6000)
        chunks = split_into_chunks(full_text, target_words=chunk_words, max_words=int(chunk_words * 1.2))

        if progress_cb:
            try:
                progress_cb(5)
            except Exception:  # noqa: BLE001
                pass

        if len(chunks) <= 1:
            # Documento piccolo: sintesi diretta sull'intero testo.
            synth_msg = (
                f"{prompt_addestramento}\n\n"
                f"--- INIZIO MATERIALE DELL'AUTORE: {file_path.name} ---\n"
                f"{full_text}\n--- FINE MATERIALE ---\n"
            )
            profile = self._train_call(synth_msg, profile_max)
        else:
            # MAP: osservazioni stilistiche per ogni blocco.
            map_max = getattr(config, 'TRAIN_MAP_MAX_TOKENS', 4000)
            observations = []
            n = len(chunks)
            for i, chunk in enumerate(chunks):
                obs = self._train_call(
                    OSSERVAZIONI_PROMPT.replace("__I__", str(i + 1)).replace("__N__", str(n))
                    + f"\n\n--- ESTRATTO {i + 1}/{n} ---\n{chunk}\n--- FINE ESTRATTO ---\n",
                    map_max,
                )
                observations.append(f"=== OSSERVAZIONI ESTRATTO {i + 1}/{n} ===\n{obs}")
                if progress_cb:
                    try:
                        progress_cb(5 + int((i + 1) / n * 80))
                    except Exception:  # noqa: BLE001
                        pass

            # REDUCE (gerarchico se le osservazioni sono troppo lunghe per il contesto).
            merged_obs = self._reduce_observations(observations)
            synth_msg = (
                f"{prompt_addestramento}\n\n"
                "Il \"materiale\" qui sotto NON è il testo originale ma le OSSERVAZIONI "
                "stilistiche raccolte analizzando l'INTERA opera dell'autore, estratto per "
                "estratto. Sulla loro base produci il PROFILO STILISTICO SINTETICO completo "
                "con la SCHEDA OPERATIVA DI IMITAZIONE, fondendo e deduplicando le osservazioni "
                "e riportando gli esemplari più rappresentativi raccolti da tutta l'opera.\n\n"
                f"--- INIZIO OSSERVAZIONI (INTERA OPERA) ---\n{merged_obs}\n--- FINE OSSERVAZIONI ---\n"
            )
            profile = self._train_call(synth_msg, profile_max)

        if progress_cb:
            try:
                progress_cb(100)
            except Exception:  # noqa: BLE001
                pass

        # Salva SOLO il profilo distillato (non il testo sorgente): generazioni leggere.
        self.conversation_history = [
            {"role": "user", "content": (
                "Analizza a fondo le opere dell'autore e produci il suo PROFILO STILISTICO "
                "SINTETICO completo, con la SCHEDA OPERATIVA DI IMITAZIONE."
            )},
            {"role": "assistant", "content": profile},
        ]
        self.is_trained = True
        return profile

    def _train_call(self, user_content: str, max_tokens: int) -> str:
        """Chiamata LLM one-shot per l'addestramento (stateless, streaming, output capped).
        NON tocca self.conversation_history."""
        try:
            with self.client.messages.stream(
                model=self.MODEL_ID,
                max_tokens=cap_output_tokens(max_tokens),
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_content}],
            ) as stream:
                msg = stream.get_final_message()
        except InsufficientCreditsError:
            raise
        except Exception as e:
            check_claude_error(e)
            raise
        return msg.content[0].text

    def _reduce_observations(self, observations, _depth: int = 0) -> str:
        """Fonde le osservazioni dei blocchi. Se troppo lunghe per il contesto, le riduce
        in modo GERARCHICO (sintesi per gruppi) finché stanno sotto la soglia. Cap di
        profondità per garantire la terminazione."""
        import config
        threshold = getattr(config, 'TRAIN_REDUCE_MAX_OBS_WORDS', 40000)
        joined = "\n\n".join(observations)
        if len(joined.split()) <= threshold or _depth >= 3:
            return joined
        map_max = getattr(config, 'TRAIN_MAP_MAX_TOKENS', 4000)
        groups, cur, cur_words = [], [], 0
        for obs in observations:
            w = len(obs.split())
            if cur and cur_words + w > threshold // 2:
                groups.append(cur); cur, cur_words = [], 0
            cur.append(obs); cur_words += w
        if cur:
            groups.append(cur)
        if len(groups) <= 1:
            return joined  # non riducibile ulteriormente: evita ricorsione infinita
        summaries = []
        for g in groups:
            summaries.append(self._train_call(
                "Unisci e DEDUPLICA queste osservazioni stilistiche di più estratti della "
                "stessa opera in un riassunto compatto ma completo, mantenendo gli esemplari "
                "più rappresentativi:\n\n" + "\n\n".join(g),
                map_max,
            ))
        return self._reduce_observations(summaries, _depth + 1)

    def generazione(self, argomento: str, numero_parole: int, destinatario : str = "Pubblico Generale", profile: str = 'academic') -> str:
        """
        Fase di generazione: genera contenuto basandosi sul contesto dell'addestramento.

        Args:
            argomento: L'argomento su cui generare il contenuto.
            numero_parole: Il numero approssimativo di parole desiderate.
            destinatario: Pubblico destinatario del contenuto

        Returns:
            Il contenuto generato da Claude.

        Raises:
            RuntimeError: Se non è stato effettuato l'addestramento.
        """
        if not self.is_trained:
            raise RuntimeError(
                "Devi prima eseguire l'addestramento prima di generare contenuto. "
                "Chiama il metodo addestramento() prima."
            )

        # Costruisci il messaggio di generazione: framing del compito + blocco
        # anti-AI condiviso (identico a quello iniettato in umanizzazione()).
        generation_message = (
            STYLE_IMITATION_DIRECTIVE
            + f"""
═══════════════════════════════════════════════════════════════
GENERA RELAZIONE
═══════════════════════════════════════════════════════════════
ARGOMENTO: {argomento}
PAROLE: {numero_parole}
DESTINATARIO: {destinatario}
═══════════════════════════════════════════════════════════════
Scrivi un testo di circa {numero_parole} parole sull'argomento indicato, applicando
fedelmente lo stile dell'autore appreso durante l'addestramento. Consegna SOLO il
testo, senza commenti né premesse.
"""
            + ANTI_AI_PROMPT_BLOCK
        )

        # Aggiungi il messaggio alla cronologia
        self.conversation_history.append({
            "role": "user",
            "content": generation_message
        })

        # Invia la richiesta a Claude (stessa sessione, mantiene il contesto)
        try:
            with self.client.messages.stream(
                model=self.MODEL_ID,
                max_tokens=MAX_TOKENS_TEST,
                system=self.system_prompt,
                messages=self.conversation_history
            ) as stream:
                response = stream.get_final_message()
        except InsufficientCreditsError:
            self.conversation_history.pop()
            raise
        except Exception as e:
            self.conversation_history.pop()
            check_claude_error(e)
            raise

        # Estrai la risposta
        assistant_message = response.content[0].text

        # Aggiungi la risposta alla cronologia
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        # Post-processing anti-AI: stessa identica pipeline di umanizzazione()/Tesi
        import config
        final_text = apply_anti_ai_pipeline(
            assistant_message,
            profile=profile,
            target_words=numero_parole,
            paraphrase_enabled=getattr(config, 'ANTI_AI_PARAPHRASE_ENABLED', True),
            paraphrase_rounds=getattr(config, 'ANTI_AI_PARAPHRASE_ROUNDS', 2),
            paraphrase_model=getattr(config, 'ANTI_AI_PARAPHRASE_MODEL', None),
            rewrite_enabled=getattr(config, 'ANTI_AI_REWRITE_ENABLED', False),
            rewrite_model=getattr(config, 'ANTI_AI_REWRITE_MODEL', None),
            algo_enabled=getattr(config, 'ANTI_AI_ALGO_ENABLED', True),
            label='generazione',
        )

        return final_text

    def umanizzazione(self, testo_originale: str, profile: str = 'informal') -> str:
        """
        Riscrive un testo generato da AI per renderlo non rilevabile dai detector AI,
        applicando lo stile appreso durante l'addestramento.

        Questa funzione RICHIEDE addestramento precedente - usa il profilo stilistico
        appreso per riscrivere il testo mantenendo lo stile dell'autore.

        PROCESSO IN DUE FASI:
        1. Claude riscrive il testo applicando lo stile dell'autore appreso
        2. Algoritmo di post-processing anti-AI trasforma ulteriormente il testo:
           - Elimina pattern AI riconoscibili
           - Inserisce imperfezioni umane
           - Varia lunghezza frasi e punteggiatura
           - Aggiunge colloquialismi e incertezze
           - Aumenta perplessità e burstiness

        Args:
            testo_originale: Il testo generato da AI da riscrivere.
            profile: Profilo del post-processing anti-AI ('informal' o 'academic').

        Returns:
            Il testo riscritto nello stile appreso e completamente anti-AI.

        Raises:
            RuntimeError: Se non è stato effettuato l'addestramento.
        """
        if not self.is_trained:
            raise RuntimeError(
                "Devi prima eseguire l'addestramento prima di umanizzare un testo. "
                "Chiama il metodo addestramento() prima."
            )

        # Calcola il numero di parole del testo originale per mantenere la lunghezza
        word_count = len(testo_originale.split())
        # Target: almeno lo stesso numero di parole, con margine del 10%
        min_words = word_count
        max_words = int(word_count * 1.15)

        # Prompt di umanizzazione: framing del compito (citazioni + lunghezza) +
        # blocco anti-AI condiviso (IDENTICO a quello iniettato in generazione()).
        humanize_prompt = (
            STYLE_IMITATION_DIRECTIVE
            + f"""
═══════════════════════════════════════════════════════════════════════════════
RISCRITTURA — APPLICA LO STILE APPRESO
═══════════════════════════════════════════════════════════════════════════════

Riscrivi il testo seguente applicando fedelmente lo stile dell'autore che hai appreso
durante l'addestramento. Il testo originale contiene {word_count} parole. La riscrittura
DEVE contenere ALMENO {min_words} parole.

⚠️ CITAZIONI BIBLIOGRAFICHE: MANTIENI INTATTE tutte le citazioni [x] (es. [1], [2], [3]).
NON rimuoverle, NON spostarle. Se una frase contiene [3], la riscrittura DEVE contenere [3].

---
{testo_originale}
---
"""
            + ANTI_AI_PROMPT_BLOCK
            + f"""
═══════════════════════════════════════════════════════════════════════════════
REGOLE DEL COMPITO
═══════════════════════════════════════════════════════════════════════════════
- Riscrivi davvero il testo con parole tue, applicando lo stile dell'autore appreso.
- ALMENO {min_words} parole. NON abbreviare, NON sintetizzare.
- Mantieni INTATTE tutte le citazioni [x].
- SOLO il testo riscritto, NESSUN commento o premessa.
"""
        )

        # Aggiungi il messaggio alla cronologia (usa il contesto dell'addestramento)
        self.conversation_history.append({
            "role": "user",
            "content": humanize_prompt
        })

        # Calcola max_tokens in base alla lunghezza del testo (~2.5 token per parola italiana + margine)
        estimated_tokens = int(word_count * 2.5) + 2000
        dynamic_max_tokens = cap_output_tokens(max(estimated_tokens, MAX_TOKENS_TEST))

        # Invia la richiesta a Claude (stessa sessione, mantiene il contesto dell'addestramento)
        try:
            with self.client.messages.stream(
                model=self.MODEL_ID,
                max_tokens=dynamic_max_tokens,
                system=self.system_prompt,
                messages=self.conversation_history
            ) as stream:
                response = stream.get_final_message()
        except InsufficientCreditsError:
            self.conversation_history.pop()
            raise
        except Exception as e:
            self.conversation_history.pop()
            check_claude_error(e)
            raise

        # Estrai la risposta
        assistant_message = response.content[0].text

        # Aggiungi la risposta alla cronologia
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        # Post-processing anti-AI: stessa identica pipeline di generazione()/Tesi
        # (profilo selezionabile: informal/academic).
        import config
        final_text = apply_anti_ai_pipeline(
            assistant_message,
            profile=profile,
            target_words=min_words,
            paraphrase_enabled=getattr(config, 'ANTI_AI_PARAPHRASE_ENABLED', True),
            paraphrase_rounds=getattr(config, 'ANTI_AI_PARAPHRASE_ROUNDS', 2),
            paraphrase_model=getattr(config, 'ANTI_AI_PARAPHRASE_MODEL', None),
            rewrite_enabled=getattr(config, 'ANTI_AI_REWRITE_ENABLED', False),
            rewrite_model=getattr(config, 'ANTI_AI_REWRITE_MODEL', None),
            algo_enabled=getattr(config, 'ANTI_AI_ALGO_ENABLED', True),
            label='umanizzazione',
        )

        return final_text

    def _rewrite_stateless(self, user_content: str, dynamic_max_tokens: int) -> str:
        """
        Invia una richiesta usando il contesto di addestramento in SOLA LETTURA:
        NON muta self.conversation_history (essenziale per elaborare molti chunk/
        batch senza far esplodere il contesto né corrompere la sessione salvata).
        Streaming. Ritorna il testo della risposta.
        """
        if not self.is_trained:
            raise RuntimeError(
                "Devi prima eseguire l'addestramento. Chiama il metodo addestramento() prima."
            )
        messages = self.conversation_history + [{"role": "user", "content": user_content}]
        try:
            with self.client.messages.stream(
                model=self.MODEL_ID,
                max_tokens=dynamic_max_tokens,
                system=self.system_prompt,
                messages=messages
            ) as stream:
                response = stream.get_final_message()
        except InsufficientCreditsError:
            raise
        except Exception as e:
            check_claude_error(e)
            raise
        return response.content[0].text

    def umanizzazione_chunk(self, testo: str, profile: str = 'informal', intensify: bool = False) -> str:
        """
        Riscrive UN chunk nello stile appreso, SENZA mutare la history e SENZA
        post-processing (lo applica il chiamante). Usata da humanize_long_text per
        umanizzare testi lunghi a blocchi. Il blocco anti-AI condiviso è
        register-respecting, quindi il `profile` qui non cambia il prompt.
        """
        word_count = len(testo.split())
        min_words = word_count
        prompt = (
            STYLE_IMITATION_DIRECTIVE
            + (STYLE_INTENSIFY_NOTE if intensify else "")
            + f"""
═══════════════════════════════════════════════════════════════════════════════
RISCRITTURA — APPLICA LO STILE APPRESO
═══════════════════════════════════════════════════════════════════════════════

Riscrivi il testo seguente applicando fedelmente lo stile dell'autore che hai appreso
durante l'addestramento. Questo è un BLOCCO di un testo più lungo: riscrivilo per
intero senza introdurre né conclusioni né aperture generali. Il blocco contiene
{word_count} parole; la riscrittura DEVE contenere ALMENO {min_words} parole.

⚠️ CITAZIONI BIBLIOGRAFICHE: MANTIENI INTATTE tutte le citazioni [x] (es. [1], [2]).
⚠️ MARCATORI DI NOTA: MANTIENI INTATTI i marcatori di nota ⟦N0⟧, ⟦N1⟧, … esattamente
dove si trovano: non rimuoverli, non modificarli, non rinumerarli.

---
{testo}
---
"""
            + ANTI_AI_PROMPT_BLOCK
            + f"""
═══════════════════════════════════════════════════════════════════════════════
REGOLE DEL COMPITO
═══════════════════════════════════════════════════════════════════════════════
- Riscrivi davvero il testo con parole tue, applicando lo stile dell'autore appreso.
- ALMENO {min_words} parole. NON abbreviare, NON sintetizzare.
- Mantieni INTATTE tutte le citazioni [x].
- SOLO il testo riscritto, NESSUN commento o premessa.
"""
        )
        dynamic_max_tokens = cap_output_tokens(max(int(word_count * 2.5) + 2000, MAX_TOKENS_TEST))
        return self._rewrite_stateless(prompt, dynamic_max_tokens)

    def umanizzazione_segments(self, joined: str, n_segments: int, profile: str = 'academic', intensify: bool = False) -> str:
        """
        Riscrive N paragrafi (segmenti marcati con <<<Sk>>>) PRESERVANDO i confini,
        per il round-trip docx (corrispondenza 1:1 coi paragrafi). Ritorna il testo
        coi marcatori, SENZA mutare la history. Il chiamante valida il numero di
        segmenti e applica il pass algoritmico per-paragrafo.
        """
        word_count = len(joined.split())
        last = n_segments - 1
        prompt = (
            STYLE_IMITATION_DIRECTIVE
            + (STYLE_INTENSIFY_NOTE if intensify else "")
            + f"""
═══════════════════════════════════════════════════════════════════════════════
RISCRITTURA A SEGMENTI — APPLICA LO STILE APPRESO
═══════════════════════════════════════════════════════════════════════════════

Ricevi {n_segments} segmenti di testo, ciascuno preceduto dal proprio marcatore
<<<Sk>>> (con k da 0 a {last}). Riscrivi OGNI segmento applicando fedelmente lo stile
dell'autore appreso durante l'addestramento.

REGOLE TASSATIVE DI STRUTTURA (NON VIOLARLE):
- Restituisci ESATTAMENTE {n_segments} segmenti, ognuno preceduto dal SUO marcatore
  <<<Sk>>> invariato, nello stesso ordine (<<<S0>>> ... <<<S{last}>>>).
- NON unire né dividere segmenti; NON aggiungere né togliere marcatori; non lasciare
  un segmento vuoto.
- Mantieni INTATTE tutte le citazioni [x] all'interno di ogni segmento.
- Mantieni INTATTI i marcatori di nota ⟦N…⟧ (es. ⟦N0⟧) dentro ogni segmento: non
  rimuoverli né modificarli.

---
{joined}
---
"""
            + ANTI_AI_PROMPT_BLOCK
            + f"""
═══════════════════════════════════════════════════════════════════════════════
REGOLE DEL COMPITO
═══════════════════════════════════════════════════════════════════════════════
- ESATTAMENTE {n_segments} segmenti, coi marcatori <<<S0>>> ... <<<S{last}>>>.
- SOLO i segmenti riscritti, nessun commento o premessa.
"""
        )
        dynamic_max_tokens = cap_output_tokens(max(int(word_count * 2.5) + 2000, MAX_TOKENS_TEST))
        return self._rewrite_stateless(prompt, dynamic_max_tokens)

    def reset_session(self) -> None:
        """Resetta la sessione, cancellando la cronologia della conversazione."""
        self.conversation_history = []
        self.is_trained = False

    def get_conversation_history(self) -> list[dict]:
        """Restituisce la cronologia della conversazione."""
        return self.conversation_history.copy()


# ============================================================================
# ESEMPIO DI UTILIZZO
# ============================================================================
if __name__ == "__main__":
    
    client = ClaudeClient()

    # ============================================
    # FASE 1: ADDESTRAMENTO
    # ============================================

    try:
        risposta_addestramento = client.addestramento(
            file_path="Daniel Goleman - Intelligenza emotiva.pdf"
        )
        print("=== RISPOSTA ADDESTRAMENTO ===")
        print(risposta_addestramento)
        print()
    except FileNotFoundError as e:
        print(f"Errore: {e}")
        exit(1)

    # ============================================
    # FASE 2: GENERAZIONE
    # ============================================

    risposta_generazione = client.generazione(
        argomento="Psicopatologia",
        numero_parole=1000
    )

    # ============================================
    # FASE 3 BETA: SALVATAGGIO
    # ============================================
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_file = Path("results") / f"contenuto_generato_{timestamp}.txt"

    with open(nome_file, "w") as f:
        f.write(risposta_generazione)

    print(f"Contenuto generato salvato in {nome_file}")
    print()

