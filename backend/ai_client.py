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
from ai_exceptions import InsufficientCreditsError, check_openai_error, check_claude_error

load_dotenv(find_dotenv())

# Configurazione
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL_ID", "o3")
DEFAULT_CLAUDE_MODEL = os.getenv("THESIS_CLAUDE_MODEL", "claude-sonnet-4-6")
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
        except InsufficientCreditsError:
            raise  # Rilancia direttamente senza wrapping
        except Exception as e:
            check_openai_error(e)  # Controlla se e' errore di crediti/quota
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
        except InsufficientCreditsError:
            raise  # Rilancia direttamente senza wrapping
        except Exception as e:
            check_claude_error(e)  # Controlla se e' errore di crediti/quota
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

    humanize_prompt = f"""Sei uno studente universitario italiano che sta scrivendo la propria tesi di laurea.
Devi RISCRIVERE il testo seguente con le TUE parole, come se lo stessi riformulando
dopo aver letto e capito il materiale. Scrivi come scrivi normalmente quando prepari
una relazione o un elaborato: con il tuo vocabolario, le tue costruzioni, il tuo ritmo.

═══════════════════════════════════════════════════════════════
REQUISITO CRITICO - LUNGHEZZA
═══════════════════════════════════════════════════════════════
- Il testo originale contiene circa {word_count} parole
- La tua riscrittura DEVE contenere ALMENO {word_count} parole
- NON riassumere, NON abbreviare, NON sintetizzare
- Se necessario, espandi leggermente i concetti per mantenere la lunghezza

═══════════════════════════════════════════════════════════════
CITAZIONI BIBLIOGRAFICHE — PRESERVA OBBLIGATORIAMENTE
═══════════════════════════════════════════════════════════════

✓ MANTIENI INTATTE tutte le citazioni nel formato [x] (es. [1], [2], [3])
✓ NON rimuovere, NON modificare, NON rinumerare le citazioni [x]
✓ Se una frase contiene [x], riscrivi la frase ma MANTIENI [x] al suo interno

═══════════════════════════════════════════════════════════════
COME SCRIVERE — IL TUO STILE NATURALE
═══════════════════════════════════════════════════════════════

Immagina di dover riscrivere questo testo per la tua tesi. Non stai copiando,
stai rielaborando. Ecco come scrivi normalmente:

VOCABOLARIO:
- Usa parole semplici e dirette: "usa" invece di "utilizza", "mostra" invece di
  "evidenzia", "aiuta" invece di "contribuisce a", "serve" invece di "risulta necessario"
- Preferisci verbi concreti: "cresce", "cala", "cambia", "funziona", "dipende"
- Evita sostantivi astratti: non "la problematica", ma "il problema"; non "le dinamiche",
  ma "i cambiamenti" o "come funziona"; non "le criticità", ma "i punti deboli"
- NON usare mai: "fondamentale", "significativo", "cruciale", "rilevante", "sottolineare",
  "evidenziare", "emergere", "inoltre", "pertanto", "dunque", "tuttavia", "ciononostante",
  "rappresenta", "costituisce", "in questo contesto", "in tal senso", "nell'ottica di",
  "al fine di", "paradigma", "svolta", "non da ultimo"

COSTRUZIONE FRASI:
- Frasi di lunghezza variabile: alcune corte (8-12 parole), altre medie (18-25), qualcuna
  lunga (30-40 parole con incisi e subordinate)
- NON iniziare mai due paragrafi consecutivi allo stesso modo
- NON usare strutture simmetriche ("da un lato... dall'altro", "non solo... ma anche")
- NON fare liste camuffate ("C'è X. C'è anche Y. Poi c'è Z")
- A volte una frase lunga è seguita da una molto corta, e viceversa
- Ogni tanto colleghi due frasi con un semplice "e" o "ma" invece di connettivi formali

TONO:
- Accademico ma non pomposo: scrivi come uno studente preparato, non come un professore
  che vuole impressionare
- Ogni tanto aggiungi un commento personale breve ("va detto che", "non è scontato",
  "il punto è che", "questo è importante perché")
- Usa "si può dire che", "in pratica", "il fatto è che" come connettivi naturali
- Non tutti i paragrafi devono concludersi con una frase riassuntiva o una conclusione;
  a volte il discorso semplicemente prosegue nel paragrafo dopo

STRUTTURA PARAGRAFI:
- I paragrafi devono avere lunghezze diverse tra loro (da 3-4 frasi a 8-10 frasi)
- Non ogni paragrafo ha una "frase topic" chiara all'inizio
- Le transizioni tra paragrafi sono a volte esplicite, a volte implicite (si cambia
  argomento senza annunciarlo)
- NON chiudere mai un paragrafo con una frase a effetto, una massima o un aforisma

ERRORI DA EVITARE (SEGNALI AI):
- NON usare frasi troppo equilibrate o retoricamente costruite
- NON usare domande retoriche seguite dalla risposta
- NON usare triadi ("X, Y e Z" ripetute come pattern)
- NON usare metafore elaborate
- NON fare chiusure "circolari" che riprendono l'inizio del paragrafo
- NON iniziare frasi con "È importante notare", "Va sottolineato", "Occorre precisare"
- NON iniziare paragrafi con "In questo contesto", "Per quanto riguarda", "Sul piano di"

═══════════════════════════════════════════════════════════════
TESTO DA RISCRIVERE ({word_count} parole)
═══════════════════════════════════════════════════════════════

{text}

═══════════════════════════════════════════════════════════════

REGOLE FINALI:
- ALMENO {word_count} parole nella risposta
- Il testo deve sembrare scritto da uno studente universitario, NON da un'intelligenza artificiale
- Ogni frase deve essere grammaticalmente corretta e completa
- Mantieni il registro accademico ma con naturalezza
- NON aggiungere interiezioni, esclamazioni o espressioni troppo colloquiali
- NON inserire autocorrezioni artificiali ("anzi no", "o meglio") — scrivi e basta
- Output SOLO il testo riscritto, senza commenti o premesse."""

    try:
        client = get_claude_client()
        # Calcola max_tokens necessari: ~1.5 token per parola italiana + margine
        estimated_tokens = int(word_count * 2.5) + 2000
        max_tokens = max(estimated_tokens, 20000)  # Minimo 20000 tokens
        rewritten = client.generate_text(humanize_prompt, max_tokens=max_tokens)

        # Applica anche l'algoritmo anti-AI post-processing
        from anti_ai_processor import humanize_text_post_processing
        return humanize_text_post_processing(rewritten)
    except InsufficientCreditsError:
        raise  # Non fare fallback per errori di crediti — l'utente deve saperlo
    except Exception as e:
        # Fallback: solo algoritmo anti-AI
        from anti_ai_processor import humanize_text_post_processing
        return humanize_text_post_processing(text)


def anti_ai_correction(text: str) -> str:
    """
    Correzione Anti-AI: applica SOLO micro-modifiche conservative al testo
    per ridurre la percentuale di rilevamento AI, senza riscriverlo da zero.
    Il testo originale viene mantenuto al 90%+.

    A differenza di humanize_text_with_claude() che riscrive completamente,
    questa funzione fa solo:
    - Sostituzioni sinonimiche mirate
    - Leggere variazioni sintattiche
    - Variazione punteggiatura
    - Inserimento di piccole imperfezioni naturali

    Args:
        text: Il testo da correggere

    Returns:
        Il testo con micro-correzioni anti-AI
    """
    word_count = len(text.split())

    correction_prompt = f"""Sei un correttore di testi specializzato nell'evasione dei detector AI.

Il tuo compito e' applicare SOLO micro-modifiche mirate al testo seguente per ridurre
la percentuale di rilevamento AI. NON devi riscrivere il testo, NON devi cambiare
la struttura, NON devi riformulare interi paragrafi.

═══════════════════════════════════════════════════════════════
REGOLA FONDAMENTALE
═══════════════════════════════════════════════════════════════
Il testo finale DEVE essere riconoscibile al 90% come l'originale.
L'utente deve rileggere il risultato e pensare "e' quasi identico, con
qualche piccola differenza qua e la".

═══════════════════════════════════════════════════════════════
CITAZIONI BIBLIOGRAFICHE — PRESERVA OBBLIGATORIAMENTE
═══════════════════════════════════════════════════════════════
✓ MANTIENI INTATTE tutte le citazioni nel formato [x] (es. [1], [2], [3])
✓ NON rimuovere, NON modificare, NON rinumerare le citazioni [x]

═══════════════════════════════════════════════════════════════
MICRO-MODIFICHE CONSENTITE (fai SOLO queste)
═══════════════════════════════════════════════════════════════

1. SINONIMI MIRATI (max 10-15% delle parole):
   - "fondamentale" → "importante" / "centrale" / "essenziale"
   - "evidenzia" → "mostra" / "indica"
   - "significativo" → "notevole" / "rilevante" / "importante"
   - "contribuisce" → "aiuta" / "concorre"
   - "rappresenta" → "e'" / "costituisce"
   - Sostituisci SOLO parole che i detector AI riconoscono come pattern tipici

2. VARIAZIONE PUNTEGGIATURA (leggera):
   - Aggiungi o rimuovi qualche virgola
   - Spezza occasionalmente una frase lunga con un punto
   - Unisci occasionalmente due frasi brevi con un punto e virgola o una virgola + congiunzione

3. MICRO-RISTRUTTURAZIONI (max 2-3 frasi su tutto il testo):
   - Inverti soggetto-verbo in una o due frasi
   - Sposta un avverbio in posizione diversa
   - Aggiungi un brevissimo inciso (es. "in pratica", "va detto", "del resto")

4. IMPERFEZIONI NATURALI (max 2-3 su tutto il testo):
   - Aggiungi un "cioe'" o un "in pratica" come collegamento
   - Usa "ma" invece di "tuttavia" in un paio di punti
   - Aggiungi un brevissimo commento personale ("il punto e' che", "non e' scontato")

═══════════════════════════════════════════════════════════════
COSA NON FARE (VIETATO)
═══════════════════════════════════════════════════════════════
✗ NON riscrivere interi paragrafi
✗ NON cambiare l'ordine dei paragrafi
✗ NON aggiungere o rimuovere concetti
✗ NON cambiare il registro o il tono generale
✗ NON sintetizzare o espandere il testo
✗ NON rimuovere o aggiungere frasi intere
✗ NON modificare dati, numeri, nomi o riferimenti

═══════════════════════════════════════════════════════════════
TESTO DA CORREGGERE ({word_count} parole)
═══════════════════════════════════════════════════════════════

{text}

═══════════════════════════════════════════════════════════════

REGOLE FINALI:
- La lunghezza DEVE essere quasi identica all'originale (tolleranza +/- 3%)
- Output SOLO il testo corretto, senza commenti, premesse o spiegazioni
- Il risultato deve sembrare lo STESSO testo con qualche piccola differenza"""

    try:
        client = get_claude_client()
        estimated_tokens = int(word_count * 2.5) + 2000
        max_tokens = max(estimated_tokens, 20000)
        corrected = client.generate_text(correction_prompt, max_tokens=max_tokens)

        # Applica anche l'algoritmo anti-AI post-processing (leggero)
        from anti_ai_processor import humanize_text_post_processing
        return humanize_text_post_processing(corrected)
    except InsufficientCreditsError:
        raise
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
