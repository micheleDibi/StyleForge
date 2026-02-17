"""
Client AI unificato per la generazione di tesi.

Supporta sia OpenAI (o1, o3) che Claude (Anthropic) come provider,
con interfaccia comune per la generazione di contenuti.
"""

import os
import json
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Configurazione
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL_ID", "o1-preview")
DEFAULT_CLAUDE_MODEL = os.getenv("THESIS_CLAUDE_MODEL", "claude-sonnet-4-20250514")
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "16000"))


class BaseAIClient(ABC):
    """Interfaccia base per i client AI."""

    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Genera testo dal prompt."""
        pass

    def _clean_json_text(self, text: str) -> str:
        """Rimuove markdown code blocks e spazi dal testo JSON."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _try_repair_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Tenta di riparare JSON malformato (troncato o con errori di sintassi).
        Gestisce i casi comuni: JSON troncato, virgole mancanti, bracket non chiusi.
        """
        import logging
        logger = logging.getLogger(__name__)

        # 1. Prova a estrarre il JSON più esterno
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 2. Prova a chiudere JSON troncato
        # Trova l'inizio del JSON
        start = text.find('{')
        if start == -1:
            return None

        json_text = text[start:]

        # Conta bracket aperti e chiudi quelli mancanti
        open_braces = 0
        open_brackets = 0
        in_string = False
        escape_next = False
        last_valid_pos = 0

        for i, char in enumerate(json_text):
            if escape_next:
                escape_next = False
                continue
            if char == '\\' and in_string:
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue

            if char == '{':
                open_braces += 1
            elif char == '}':
                open_braces -= 1
            elif char == '[':
                open_brackets += 1
            elif char == ']':
                open_brackets -= 1

            if open_braces >= 0 and open_brackets >= 0:
                last_valid_pos = i

        # Tronca alla posizione dell'ultimo valore valido e chiudi
        json_text = json_text[:last_valid_pos + 1]

        # Rimuovi virgola finale prima di chiudere
        json_text = re.sub(r',\s*$', '', json_text)

        # Chiudi brackets e braces mancanti
        # Riconta dopo il troncamento
        open_braces = json_text.count('{') - json_text.count('}')
        open_brackets = json_text.count('[') - json_text.count(']')

        json_text += ']' * max(0, open_brackets)
        json_text += '}' * max(0, open_braces)

        try:
            result = json.loads(json_text)
            logger.info("JSON riparato con successo (chiusura bracket mancanti)")
            return result
        except json.JSONDecodeError:
            pass

        # 3. Prova rimuovendo l'ultimo elemento incompleto prima di chiudere
        # Cerca l'ultima virgola seguita da un oggetto/array incompleto
        last_comma = json_text.rfind(',')
        if last_comma > 0:
            truncated = json_text[:last_comma]
            open_braces = truncated.count('{') - truncated.count('}')
            open_brackets = truncated.count('[') - truncated.count(']')
            truncated += ']' * max(0, open_brackets)
            truncated += '}' * max(0, open_braces)

            try:
                result = json.loads(truncated)
                logger.info("JSON riparato con successo (rimosso ultimo elemento incompleto)")
                return result
            except json.JSONDecodeError:
                pass

        return None

    def generate_json(self, prompt: str, max_tokens: Optional[int] = None, retries: int = 2) -> Dict[str, Any]:
        """
        Genera una risposta JSON dal modello con meccanismo di retry e repair.

        Args:
            prompt: Il prompt che richiede output JSON
            max_tokens: Numero massimo di token
            retries: Numero di tentativi in caso di JSON malformato

        Returns:
            Dizionario Python parsato dal JSON generato
        """
        import logging
        logger = logging.getLogger(__name__)
        last_error = None

        for attempt in range(retries + 1):
            if attempt > 0:
                logger.warning(f"Tentativo {attempt + 1}/{retries + 1} per generazione JSON")

            response_text = self.generate_text(prompt, max_tokens)
            cleaned_text = self._clean_json_text(response_text)

            # Tentativo 1: parse diretto
            try:
                return json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"JSON parse fallito (tentativo {attempt + 1}): {str(e)}")

            # Tentativo 2: repair del JSON
            repaired = self._try_repair_json(cleaned_text)
            if repaired is not None:
                return repaired

        raise ValueError(
            f"Impossibile parsare la risposta come JSON dopo {retries + 1} tentativi: {str(last_error)}\n"
            f"Risposta ricevuta: {response_text[:500]}..."
        )

    def generate_chapters(
        self,
        thesis_data: Dict[str, Any],
        attachments_context: str = ""
    ) -> Dict[str, Any]:
        """Genera i titoli dei capitoli per una tesi."""
        from thesis_prompts import build_chapters_prompt
        prompt = build_chapters_prompt(thesis_data, attachments_context)
        return self.generate_json(prompt)

    def generate_sections(
        self,
        thesis_data: Dict[str, Any],
        chapters: list,
        attachments_context: str = ""
    ) -> Dict[str, Any]:
        """Genera i titoli delle sezioni per ogni capitolo."""
        from thesis_prompts import build_sections_prompt
        prompt = build_sections_prompt(thesis_data, chapters, attachments_context)
        # Stima token necessari: più capitoli e sezioni = più token
        sections_per_chapter = thesis_data.get('sections_per_chapter', 3)
        num_chapters = len(chapters)
        # ~200 token per sezione (titolo + key_points) + overhead JSON
        estimated_tokens = num_chapters * sections_per_chapter * 200 + 1000
        max_tokens = max(estimated_tokens, MAX_TOKENS)
        return self.generate_json(prompt, max_tokens=max_tokens)

    def generate_section_content(
        self,
        thesis_data: Dict[str, Any],
        chapter: Dict[str, Any],
        section: Dict[str, Any],
        previous_sections_summary: str = "",
        attachments_context: str = "",
        author_style_context: str = ""
    ) -> str:
        """Genera il contenuto di una singola sezione."""
        from thesis_prompts import build_section_content_prompt

        prompt = build_section_content_prompt(
            thesis_data=thesis_data,
            chapter=chapter,
            section=section,
            previous_sections_summary=previous_sections_summary,
            attachments_context=attachments_context,
            author_style_context=author_style_context
        )

        # Calcola max_tokens in base alle parole richieste
        # ~2.5 token per parola italiana + margine
        words_per_section = thesis_data.get('words_per_section', 5000)
        estimated_tokens = int(words_per_section * 2.5) + 2000
        max_tokens = max(estimated_tokens, MAX_TOKENS)

        return self.generate_text(prompt, max_tokens=max_tokens)


class OpenAIClient(BaseAIClient):
    """
    Client per OpenAI con supporto per modelli di reasoning (o1, o3).
    """

    def __init__(self, model_id: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY non configurata. "
                "Aggiungi la chiave al file .env o come variabile d'ambiente."
            )

        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)
        self.model_id = model_id or DEFAULT_OPENAI_MODEL
        self.max_tokens = MAX_TOKENS
        self.provider = "openai"

    def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=max_tokens or self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Errore nella generazione OpenAI: {str(e)}")


class ClaudeClient(BaseAIClient):
    """
    Client per Claude (Anthropic) per la generazione di tesi.
    """

    def __init__(self, model_id: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY non configurata. "
                "Aggiungi la chiave al file .env o come variabile d'ambiente."
            )

        import anthropic
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model_id = model_id or DEFAULT_CLAUDE_MODEL
        self.max_tokens = MAX_TOKENS
        self.provider = "claude"

    def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        try:
            message = self.client.messages.create(
                model=self.model_id,
                max_tokens=max_tokens or self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            raise RuntimeError(f"Errore nella generazione Claude: {str(e)}")


# Singleton instances
_openai_client: Optional[OpenAIClient] = None
_claude_client: Optional[ClaudeClient] = None


def get_ai_client(provider: str = "openai") -> BaseAIClient:
    """
    Restituisce un'istanza del client AI per il provider specificato.

    Args:
        provider: "openai" o "claude"

    Returns:
        Istanza del client AI appropriato
    """
    global _openai_client, _claude_client

    if provider == "claude":
        if _claude_client is None:
            _claude_client = ClaudeClient()
        return _claude_client
    else:
        # Default: OpenAI
        if _openai_client is None:
            _openai_client = OpenAIClient()
        return _openai_client


def get_openai_client() -> OpenAIClient:
    """
    Restituisce un'istanza singleton del client OpenAI.
    Mantiene compatibilità con il codice esistente.
    """
    return get_ai_client("openai")


def get_claude_client() -> ClaudeClient:
    """
    Restituisce un'istanza singleton del client Claude.
    """
    return get_ai_client("claude")


def humanize_text_with_claude(text: str) -> str:
    """
    Umanizza il testo usando Claude senza necessità di sessione addestrata.
    Usa un prompt specifico per riscrivere il testo eliminando pattern AI.
    Dopo la riscrittura con Claude, applica anche l'algoritmo anti-AI.

    Args:
        text: Il testo da umanizzare

    Returns:
        Il testo umanizzato
    """
    # Calcola il numero approssimativo di parole nel testo originale
    word_count = len(text.split())

    humanize_prompt = f"""Sei un redattore esperto. Devi riscrivere questo testo come un umano vero — con esitazioni, ridondanze, momenti meno brillanti.

═══════════════════════════════════════════════════════════════
REQUISITO CRITICO - LUNGHEZZA
═══════════════════════════════════════════════════════════════
- Il testo originale contiene circa {word_count} parole
- La tua riscrittura DEVE contenere ALMENO {word_count} parole
- NON riassumere, NON abbreviare, NON sintetizzare
- Se necessario, espandi leggermente i concetti per mantenere la lunghezza

═══════════════════════════════════════════════════════════════
DIVIETI ASSOLUTI — TOLLERANZA ZERO
═══════════════════════════════════════════════════════════════

STRUTTURE MAI AMMESSE:
❌ "Non è X, ma Y" / "Non si tratta di X, ma di Y"
❌ "Non solo X, ma anche Y" / "Più che X, Y"
❌ "È qui che..." / "È proprio qui che..." / "È in questo X che Y"
❌ "Se da un lato... dall'altro..." / "Da una parte... dall'altra..."
❌ "Quanto più X, tanto più Y"
❌ "X, certo, ma Y" / "X. E non solo: Y"
❌ Qualsiasi frase con struttura speculare o bilanciata
❌ Parallelismi di qualsiasi tipo

PAROLE E FORMULE VIETATE:
❌ "Naturalmente", "Eppure", "Dunque", "Pertanto", "Inoltre", "Infine", "Infatti" a inizio frase
❌ "In definitiva", "In ultima analisi", "In questo senso", "In altre parole"
❌ "Vale la pena", "Non a caso", "Non è un caso", "A ben vedere"
❌ "Per così dire", "In qualche modo", "In un certo senso"
❌ "Quest'ultimo/a", "Tale/Tali", "Tutto ciò", "Tutto questo"
❌ "Appare evidente/chiaro", "È importante sottolineare/notare"
❌ "È bene ricordare", "Occorre precisare", "Va detto che"
❌ "Si potrebbe dire", "Potremmo affermare"
❌ "dinamiche", "meccanismi", "processi" usati genericamente
❌ "presenta", "emerge", "si manifesta" (troppo clinici)

INIZI PARAGRAFO VIETATI:
❌ "È" / "Sono" / "Si tratta"
❌ "Questo" / "Questa" / "Questi" / "Tale" / "Tali"
❌ "Un aspetto" / "Un punto" / "Un elemento"
❌ "La questione" / "Il problema" / "Il tema"
❌ "Sul piano" / "Dal punto di vista"
❌ "In questo contesto" / "A questo proposito" / "Per quanto riguarda"

PATTERN RETORICI VIETATI:
❌ Frasi brevi sentenziose a fine paragrafo
❌ Frasi a effetto, aforismi, massime
❌ Metafore elaborate o poetiche
❌ Chiasmi, triadi, anafore
❌ Domande retoriche seguite dalla risposta
❌ Chiusure "circolari" che riprendono l'inizio
❌ Similitudini eleganti ("è come...", "funziona come...")
❌ Trattini con definizione incorporata ("L'ansia — cioè la sensazione di —")

TERMINI COLLOQUIALI VIETATI:
❌ "bhe", "beh", "meh", "vabbè", "boh", "mah" — troppo informali per un testo accademico
❌ Interiezioni da chat o messaggistica
❌ Forme dialettali o gergali estreme

═══════════════════════════════════════════════════════════════
CITAZIONI BIBLIOGRAFICHE — PRESERVA OBBLIGATORIAMENTE
═══════════════════════════════════════════════════════════════

✓ MANTIENI INTATTE tutte le citazioni bibliografiche nel formato [x] (es. [1], [2], [3])
✓ NON rimuovere, NON modificare, NON riformulare le citazioni [x]
✓ Le citazioni devono restare nel testo — se il testo dice "secondo studi recenti [3]",
  la riscrittura DEVE contenere "[3]" nello stesso punto o posizione equivalente
✓ Se una frase contiene [x], riscrivi la frase ma MANTIENI [x] al suo interno

═══════════════════════════════════════════════════════════════
COSA DEVI FARE ATTIVAMENTE
═══════════════════════════════════════════════════════════════

INSERISCI OBBLIGATORIAMENTE:
✓ Almeno 4-5 frasi che iniziano con "E" o "Ma"
✓ Almeno 3 autocorrezioni: "o meglio", "anzi no", "cioè", "diciamo"
✓ Almeno 2 frasi incomplete o che si interrompono
✓ Almeno 3 ripetizioni lessicali ravvicinate (stessa parola 2-3 volte)
✓ Almeno 2 parentesi lunghe che interrompono il flusso
✓ Almeno 1 momento di incertezza ("forse", "non è chiaro", "probabilmente")
✓ Almeno 1 frase un po' meno fluida, come se stessi ancora pensando
✓ Almeno 1 passaggio dove ripeti un concetto già detto

ANCORAGGI CONCRETI:
✓ Dettagli specifici: date, percentuali, riferimenti temporali
✓ Numeri non tondi: "circa il 23%", "dopo 7-8 settimane"
✓ Casi o esempi concreti
✓ NON inventare riferimenti a studi o autori — le citazioni [x] nel testo sono già corrette

VARIAZIONI:
✓ Paragrafi di lunghezze MOLTO diverse
✓ Inizi paragrafo tutti diversi tra loro
✓ Almeno 1 cambio di tono (più colloquiale o più tecnico)

═══════════════════════════════════════════════════════════════
STRUTTURA COMPLESSIVA
═══════════════════════════════════════════════════════════════

Il testo deve sembrare scritto da qualcuno che pensa mentre scrive:
✓ A volte torna indietro su un punto
✓ A volte cambia argomento in modo brusco
✓ A volte un paragrafo non c'entra molto col precedente
✓ A volte una frase resta un po' appesa
✓ Transizioni non troppo fluide

I paragrafi umani spesso finiscono:
✓ A metà di un ragionamento
✓ Con un dubbio
✓ Con una frase lunga e faticosa
✓ Senza chiusura vera

═══════════════════════════════════════════════════════════════
TESTO DA RISCRIVERE ({word_count} parole)
═══════════════════════════════════════════════════════════════

{text}

═══════════════════════════════════════════════════════════════

RICORDA:
- ALMENO {word_count} parole nella risposta
- Ogni frase che ti sembra "ben riuscita" è probabilmente un segnale AI. Sporcala.
- Se suona "scritto bene", è un problema. Deve suonare come qualcuno che pensa.
- TUTTE le parole devono essere scritte per intero e correttamente — niente troncamenti, lettere mancanti o parole incomplete
- TUTTE le frasi devono essere grammaticalmente complete — ogni frase deve avere soggetto e verbo e terminare con la punteggiatura corretta
- NON usare termini troppo informali come "bhe", "meh", "vabbè", "boh", "mah" — il tono deve essere colloquiale ma non da chat
- Output SOLO il testo riscritto, senza commenti."""

    try:
        client = get_claude_client()
        # Calcola max_tokens necessari: ~1.5 token per parola italiana + margine
        estimated_tokens = int(word_count * 2.5) + 2000
        max_tokens = max(estimated_tokens, 20000)  # Minimo 20000 tokens
        rewritten = client.generate_text(humanize_prompt, max_tokens=max_tokens)

        # Applica anche l'algoritmo anti-AI post-processing
        from anti_ai_processor import humanize_text_post_processing
        return humanize_text_post_processing(rewritten)
    except Exception as e:
        # Fallback: solo algoritmo anti-AI
        from anti_ai_processor import humanize_text_post_processing
        return humanize_text_post_processing(text)


# ============================================================================
# TEST
# ============================================================================
if __name__ == "__main__":
    import sys

    provider = sys.argv[1] if len(sys.argv) > 1 else "openai"
    print(f"Testing AI Client with provider: {provider}")

    try:
        client = get_ai_client(provider)
        print(f"Model: {client.model_id}")

        response = client.generate_text(
            "Genera un breve titolo per una tesi sull'intelligenza artificiale. "
            "Rispondi solo con il titolo, senza spiegazioni."
        )
        print(f"Response: {response}")
    except Exception as e:
        print(f"Errore: {e}")
