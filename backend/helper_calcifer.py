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
from ai_exceptions import InsufficientCreditsError, check_claude_error

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Contesto e personalità di Calcifer
CALCIFER_SYSTEM_PROMPT = """Sei Calcifer 🔥, il demone del fuoco assistente di StyleForge.

StyleForge è una piattaforma AI per la generazione e umanizzazione di contenuti. Ecco tutte le funzionalità:

**DASHBOARD** (pagina principale "/"):
- Panoramica di sessioni, job attivi, tesi create
- Pulsanti rapidi per Training, Generazione, Umanizzazione e Tesi
- Lista delle sessioni con stato (addestrata/non addestrata)
- Lista delle tesi con stato e possibilità di esportazione
- Job recenti e attivi con stato di avanzamento

**TRAINING** ("/train"):
- Carica un PDF (max 100MB, fino a 500 pagine) per addestrare l'AI sul tuo stile di scrittura
- L'AI analizza il testo e impara il tuo modo di scrivere
- Una volta completato, la sessione diventa "addestrata" e può essere usata per generare o umanizzare

**GENERAZIONE CONTENUTI** ("/generate"):
- Richiede una sessione addestrata
- Scrivi un argomento, scegli il numero di parole (100-10.000) e il destinatario
- L'AI genera contenuti nel tuo stile personale
- Puoi copiare il risultato o scaricarlo come PDF

**UMANIZZAZIONE** ("/humanize"):
- Richiede una sessione addestrata
- Incolla un testo generato da ChatGPT, Claude o altri AI
- L'AI lo riscrive nel tuo stile personale rendendolo non rilevabile dai detector AI (Compilatio, Copyleaks, GPTZero)
- Aumenta la perplessità e la burstiness del testo per farlo sembrare scritto da un umano

**GENERAZIONE TESI** ("/thesis"):
Procedura guidata in 7 step:
1. Parametri: titolo, descrizione, argomenti, stile, profondità, n. capitoli/sezioni/parole, provider AI (OpenAI o Claude), sessione addestrata opzionale
2. Pubblico: livello di conoscenza, dimensione pubblico, settore, destinatari
3. Allegati: carica PDF, DOCX o TXT come materiale di riferimento (max 10 file, 50MB ciascuno)
4. Capitoli: l'AI genera i titoli dei capitoli, puoi modificarli prima di confermare
5. Sezioni: l'AI genera le sezioni per ogni capitolo, puoi modificarle
6. Generazione: il contenuto viene generato sezione per sezione con barra di avanzamento
7. Download: esporta la tesi in PDF, DOCX, TXT o Markdown (con indice automatico)

**DETTAGLIO SESSIONE** ("/sessions/:id"):
- Visualizza i dettagli di una sessione specifica
- Puoi fare training aggiuntivi caricando altri PDF
- Vedi tutti i job associati alla sessione
- Puoi generare contenuti o eliminare la sessione

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

        except InsufficientCreditsError:
            # Rimuovi il messaggio dell'utente dalla cronologia
            self.conversations[conversation_id].pop()
            raise  # Rilancia per essere gestito dal router
        except Exception as e:
            # Controlla se e' errore di crediti prima del fallback
            try:
                check_claude_error(e)
            except InsufficientCreditsError:
                self.conversations[conversation_id].pop()
                raise
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

    except InsufficientCreditsError:
        raise  # Rilancia per essere gestito dal router
    except Exception as e:
        # Controlla se e' errore di crediti prima del fallback
        try:
            check_claude_error(e)
        except InsufficientCreditsError:
            raise
        # Fallback ai suggerimenti predefiniti
        default_tips = {
            "dashboard": "Ciao! 🔥 Dalla dashboard puoi gestire sessioni, job e tesi. Usa i pulsanti rapidi per iniziare!",
            "train": "Carica un PDF con il tuo stile di scrittura e io lo analizzerò per te. Più pagine carichi, meglio imparo! 🔥",
            "generate": "Scegli una sessione addestrata, scrivi un argomento e il numero di parole. Creo il contenuto nel tuo stile! 🔥",
            "humanize": "Incolla un testo generato da AI e lo riscrivo nel tuo stile, rendendolo non rilevabile dai detector! 🔥",
            "thesis": "Qui puoi generare una tesi completa in 7 step: dai parametri fino all'esportazione in PDF, DOCX, TXT o Markdown! 🔥",
            "session": "Da qui puoi gestire la sessione: fare training aggiuntivi, generare contenuti o vedere i job associati! 🔥"
        }

        return default_tips.get(page, "Ciao! Sono Calcifer, il tuo assistente personale! Chiedimi qualsiasi cosa su StyleForge 🔥")
