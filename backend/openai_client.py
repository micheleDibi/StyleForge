"""
Client per OpenAI con supporto per modelli di reasoning (o1, o3).

Questo modulo fornisce un'interfaccia per interagire con i modelli OpenAI,
in particolare i modelli con capacità di reasoning avanzato.
"""

import os
import json
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Configurazione
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL_ID", "o1-preview")
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "16000"))


class OpenAIThinkingClient:
    """
    Client per interagire con i modelli OpenAI di reasoning.

    Supporta modelli come o1, o1-preview, o3 che hanno capacità
    di ragionamento avanzato per task complessi.
    """

    def __init__(self, model_id: Optional[str] = None, api_key: Optional[str] = None):
        """
        Inizializza il client OpenAI.

        Args:
            model_id: ID del modello da usare (default: o1-preview)
            api_key: API key OpenAI (default: da variabile d'ambiente)
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY non configurata. "
                "Aggiungi la chiave al file .env o come variabile d'ambiente."
            )

        self.client = OpenAI(api_key=self.api_key)
        self.model_id = model_id or DEFAULT_MODEL
        self.max_tokens = MAX_TOKENS

    def generate_with_thinking(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0
    ) -> str:
        """
        Genera una risposta utilizzando il modello di reasoning.

        I modelli o1/o3 sono ottimizzati per task di reasoning complesso
        e producono output più strutturati e ragionati.

        Args:
            prompt: Il prompt da inviare al modello
            max_tokens: Numero massimo di token (default: 16000)
            temperature: Temperatura per la generazione (default: 1.0)

        Returns:
            La risposta generata dal modello
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_completion_tokens=max_tokens or self.max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"Errore nella generazione OpenAI: {str(e)}")

    def generate_json(
        self,
        prompt: str,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Genera una risposta JSON dal modello.

        Utile per output strutturati come indici, capitoli, sezioni.

        Args:
            prompt: Il prompt che richiede output JSON
            max_tokens: Numero massimo di token

        Returns:
            Dizionario Python parsato dal JSON generato

        Raises:
            ValueError: Se la risposta non è un JSON valido
        """
        response_text = self.generate_with_thinking(prompt, max_tokens)

        # Pulisci la risposta (rimuovi markdown code blocks se presenti)
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()

        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            # Prova a estrarre JSON dalla risposta
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            raise ValueError(
                f"Impossibile parsare la risposta come JSON: {str(e)}\n"
                f"Risposta ricevuta: {response_text[:500]}..."
            )

    def generate_chapters(
        self,
        thesis_data: Dict[str, Any],
        attachments_context: str = ""
    ) -> Dict[str, Any]:
        """
        Genera i titoli dei capitoli per una tesi.

        Args:
            thesis_data: Dizionario con i parametri della tesi
            attachments_context: Contesto estratto dagli allegati

        Returns:
            Dizionario con la struttura dei capitoli
        """
        from thesis_prompts import build_chapters_prompt

        prompt = build_chapters_prompt(thesis_data, attachments_context)
        return self.generate_json(prompt)

    def generate_sections(
        self,
        thesis_data: Dict[str, Any],
        chapters: list,
        attachments_context: str = ""
    ) -> Dict[str, Any]:
        """
        Genera i titoli delle sezioni per ogni capitolo.

        Args:
            thesis_data: Dizionario con i parametri della tesi
            chapters: Lista dei capitoli confermati
            attachments_context: Contesto estratto dagli allegati

        Returns:
            Dizionario con la struttura completa (capitoli + sezioni)
        """
        from thesis_prompts import build_sections_prompt

        prompt = build_sections_prompt(thesis_data, chapters, attachments_context)
        return self.generate_json(prompt)

    def generate_section_content(
        self,
        thesis_data: Dict[str, Any],
        chapter: Dict[str, Any],
        section: Dict[str, Any],
        previous_sections_summary: str = "",
        attachments_context: str = "",
        author_style_context: str = ""
    ) -> str:
        """
        Genera il contenuto di una singola sezione.

        Args:
            thesis_data: Parametri della tesi
            chapter: Dati del capitolo corrente
            section: Dati della sezione da generare
            previous_sections_summary: Riassunto delle sezioni precedenti
            attachments_context: Contesto dagli allegati
            author_style_context: Contesto dello stile autore (se addestrato)

        Returns:
            Contenuto testuale della sezione
        """
        from thesis_prompts import build_section_content_prompt

        prompt = build_section_content_prompt(
            thesis_data=thesis_data,
            chapter=chapter,
            section=section,
            previous_sections_summary=previous_sections_summary,
            attachments_context=attachments_context,
            author_style_context=author_style_context
        )

        return self.generate_with_thinking(prompt)


# Singleton per riutilizzare la connessione
_client_instance: Optional[OpenAIThinkingClient] = None


def get_openai_client() -> OpenAIThinkingClient:
    """
    Restituisce un'istanza singleton del client OpenAI.

    Returns:
        Istanza di OpenAIThinkingClient
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = OpenAIThinkingClient()
    return _client_instance


# ============================================================================
# TEST
# ============================================================================
if __name__ == "__main__":
    # Test base
    client = OpenAIThinkingClient()

    print("Testing OpenAI Thinking Client...")
    print(f"Model: {client.model_id}")

    # Test semplice
    response = client.generate_with_thinking(
        "Genera un breve titolo per una tesi sull'intelligenza artificiale."
    )
    print(f"Response: {response}")
