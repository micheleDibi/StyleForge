"""
Helper Calcifer - Assistente AI interattivo per StyleForge

Questo modulo gestisce le conversazioni con Calcifer, l'assistente AI
che aiuta gli utenti a navigare e utilizzare StyleForge.
"""

from anthropic import Anthropic
from datetime import datetime
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Contesto e personalità di Calcifer
CALCIFER_SYSTEM_PROMPT = """Sei Calcifer 🔥, il demone del fuoco assistente di StyleForge.

StyleForge permette di:
- **Training**: caricare PDF per addestrare l'AI sul proprio stile
- **Generazione**: creare contenuti nello stile appreso
- **Sessioni**: contenitori per job di training/generazione
- **Dashboard**: visualizza sessioni e job attivi

Personalità: vivace, entusiasta, amichevole. Rispondi in italiano, in modo conciso (max 2-3 frasi) ma utile. Usa 🔥 occasionalmente.
"""

class CalciferHelper:
    """Gestisce le conversazioni con Calcifer."""

    def __init__(self):
        self.conversations: Dict[str, List[Dict]] = {}

    def get_response(
        self,
        user_message: str,
        conversation_id: str = "default",
        context: Optional[Dict] = None
    ) -> str:
        """
        Genera una risposta di Calcifer al messaggio dell'utente.

        Args:
            user_message: Il messaggio dell'utente
            conversation_id: ID univoco della conversazione
            context: Contesto opzionale (pagina corrente, sessioni, job, etc.)

        Returns:
            La risposta di Calcifer
        """
        # Inizializza la conversazione se non esiste
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        # Aggiungi il messaggio dell'utente alla cronologia
        self.conversations[conversation_id].append({
            "role": "user",
            "content": user_message
        })

        # Prepara il contesto aggiuntivo
        context_message = ""
        if context:
            context_parts = []

            if "current_page" in context:
                context_parts.append(f"Pagina corrente: {context['current_page']}")

            if "sessions_count" in context:
                context_parts.append(f"Numero di sessioni: {context['sessions_count']}")

            if "active_jobs" in context:
                context_parts.append(f"Job attivi: {context['active_jobs']}")

            if "trained_sessions" in context:
                context_parts.append(f"Sessioni addestrate: {context['trained_sessions']}")

            if context_parts:
                context_message = "\n\nContesto attuale:\n" + "\n".join(context_parts)

        # Prepara i messaggi per Claude
        messages = self.conversations[conversation_id].copy()

        # Aggiungi il contesto al messaggio dell'utente se presente
        if context_message:
            messages[-1]["content"] = user_message + context_message

        try:
            # Chiamata all'API di Claude (ottimizzata per velocità)
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=512,  # Ridotto per risposte più veloci
                system=CALCIFER_SYSTEM_PROMPT,
                messages=messages
            )

            assistant_message = response.content[0].text

            # Aggiungi la risposta alla cronologia
            self.conversations[conversation_id].append({
                "role": "assistant",
                "content": assistant_message
            })

            # Limita la cronologia alle ultime 10 interazioni (20 messaggi)
            if len(self.conversations[conversation_id]) > 20:
                self.conversations[conversation_id] = self.conversations[conversation_id][-20:]

            return assistant_message

        except Exception as e:
            return f"Ops! Le mie fiamme si sono un po' spente... 🔥 Errore: {str(e)}"

    def clear_conversation(self, conversation_id: str = "default"):
        """Cancella la cronologia di una conversazione."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

    def get_conversation_history(self, conversation_id: str = "default") -> List[Dict]:
        """Ottiene la cronologia di una conversazione."""
        return self.conversations.get(conversation_id, [])


# Istanza globale di CalciferHelper
calcifer = CalciferHelper()


def get_contextual_tip(page: str, context: Optional[Dict] = None) -> str:
    """
    Genera un suggerimento contestuale basato sulla pagina e il contesto.

    Args:
        page: La pagina corrente (dashboard, train, generate, session)
        context: Contesto opzionale

    Returns:
        Un suggerimento di Calcifer
    """
    prompt = f"Genera UN suggerimento breve e utile (max 2 frasi) per un utente che si trova sulla pagina '{page}' di StyleForge."

    if context:
        prompt += f" Contesto: {context}"

    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",  # Haiku per risposte veloci
            max_tokens=150,
            system=CALCIFER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    except Exception as e:
        # Fallback ai suggerimenti predefiniti
        default_tips = {
            "dashboard": "Ciao! 🔥 Dalla dashboard puoi vedere tutte le tue sessioni e job. Clicca su 'Nuova Sessione' per iniziare!",
            "train": "Perfetto! Carica un PDF con il tuo stile di scrittura e io lo analizzerò per te. Più pagine = migliore apprendimento! 🔥",
            "generate": "Pronto a creare qualcosa di fantastico! Scegli una sessione addestrata e dimmi cosa vuoi scrivere. 🔥✨",
            "session": "Qui puoi gestire questa sessione: fare training aggiuntivi o vedere tutti i job associati! 🔥"
        }

        return default_tips.get(page, "Ciao! Sono Calcifer, il tuo assistente personale! 🔥")
