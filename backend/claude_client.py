"""
Client per Claude Opus 4.5 con funzionalità di addestramento e generazione.

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

load_dotenv(find_dotenv())

MAX_TOKENS_TRAIN = 4096 # Numero di token utilizzati per la generazione di testo utilizzando Claude (4096 token sono circa 3000 parole in inglese, un po' meno in italiano)
MAX_TOKENS_TEST = 8192

API_KEY = os.getenv("ANTHROPIC_API_KEY")

def lettura_pdf(file_path: str, max_pagine: int = 50) -> str:
    doc = fitz.open(file_path)
    testo = ""
    
    pagine_da_leggere = min(max_pagine, len(doc))
    
    for i in tqdm(range(pagine_da_leggere), desc="Lettura PDF"):
        testo += doc[i].get_text()
    
    doc.close()
    return testo

class ClaudeClient:
    """Client per interagire con Claude Opus 4.5 mantenendo il contesto della sessione."""

    MODEL_ID = "claude-opus-4-5-20251101"

    def __init__(self):
        """
        Inizializza il client Claude.
        """

        self.client = Anthropic(api_key=API_KEY)
        self.conversation_history: list[dict] = []
        self.system_prompt: str = """
            Sei un redattore. Riceverai fonti in allegato. 
            Devi scrivere come l'autore, ma soprattutto devi scrivere come un umano vero — con le sue esitazioni, 
            le sue ridondanze, i suoi momenti meno brillanti.

            Sei anche un analista linguistico e stilista editoriale di altissimo livello. 
            Riceverai in allegato una o più fonti di un autore (libri, articoli, saggi, pubblicazioni scientifiche). 
            Il tuo compito è interiorizzare profondamente la sua voce attraverso lo studio di questi materiali, 
            fino a poter produrre testi indistinguibili dai suoi originali.
        """
        self.is_trained: bool = False

    def addestramento(self, file_path: str) -> str:
        """
        Fase di addestramento: invia un file con un prompt a Claude.

        Questa funzione legge il contenuto del file e lo invia insieme al prompt
        per stabilire il contesto della conversazione.

        Args:
            file_path: Percorso del file da inviare a Claude.

        Returns:
            La risposta di Claude dopo l'addestramento.

        Raises:
            FileNotFoundError: Se il file non esiste.
            ValueError: Se il file è vuoto.
        """
        # Leggi il contenuto del file
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Il file non esiste: {file_path}")

        file_content = lettura_pdf(file_path=file_path) #file_path.read_text(encoding="utf-8") #TODO - controllare che prenda in input correttamente i file  PDF
        if not file_content.strip():
            raise ValueError(f"Il file è vuoto: {file_path}")
        
        prompt_addestramento = Path("prompt_addestramento.txt").read_text(encoding="utf-8")

        training_message = f"""{prompt_addestramento}

        --- INIZIO CONTENUTO FILE: {file_path.name} ---
        {file_content}
        --- FINE CONTENUTO FILE ---
        """

        # Aggiungi il messaggio alla cronologia
        self.conversation_history.append({
            "role": "user",
            "content": training_message
        })

        # Invia la richiesta a Claude
        try:
            response = self.client.messages.create(
                model=self.MODEL_ID,
                max_tokens=MAX_TOKENS_TRAIN,
                system=self.system_prompt,
                messages=self.conversation_history
            )
        except InsufficientCreditsError:
            # Rimuovi il messaggio dalla cronologia se la chiamata fallisce
            self.conversation_history.pop()
            raise
        except Exception as e:
            self.conversation_history.pop()
            check_claude_error(e)
            raise

        # Estrai la risposta
        assistant_message = response.content[0].text

        # Aggiungi la risposta alla cronologia per mantenere il contesto
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        self.is_trained = True
        return assistant_message

    def generazione(self, argomento: str, numero_parole: int, destinatario : str = "Pubblico Generale") -> str:
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

        # Costruisci il messaggio di generazione
        # ==========================================
        # INSERISCI QUI IL TUO PROMPT DI GENERAZIONE
        # ==========================================
        generation_message = f"""
            ═══════════════════════════════════════════════════════════════
            GENERA RELAZIONE
            ═══════════════════════════════════════════════════════════════
            ARGOMENTO: {argomento}
            PAROLE: {numero_parole}
            DESTINATARIO: {destinatario}
            ═══════════════════════════════════════════════════════════════
            Scrivi.
            Applica tutto. Ogni regola. Ogni divieto.
            Se una frase ti sembra riuscita, probabilmente è sbagliata. Sporcala.
            Consegna solo quando il testo sembra scritto da una persona vera, stanca, che ha poco tempo, non da una macchina che vuole impressionare.
        """

        # Aggiungi il messaggio alla cronologia
        self.conversation_history.append({
            "role": "user",
            "content": generation_message
        })

        # Invia la richiesta a Claude (stessa sessione, mantiene il contesto)
        try:
            response = self.client.messages.create(
                model=self.MODEL_ID,
                max_tokens=MAX_TOKENS_TEST,
                system=self.system_prompt,
                messages=self.conversation_history
            )
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

        # ═══════════════════════════════════════════════════════════════
        # POST-PROCESSING ANTI-AI
        # ═══════════════════════════════════════════════════════════════
        # Applica l'algoritmo di post-processing per rendere il testo
        # generato meno rilevabile dai detector AI
        # ═══════════════════════════════════════════════════════════════

        from anti_ai_processor import humanize_text_post_processing

        # Applica trasformazioni anti-AI
        final_text = humanize_text_post_processing(assistant_message)

        return final_text

    def umanizzazione(self, testo_originale: str) -> str:
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

        # Prompt di umanizzazione che sfrutta il contesto dell'addestramento
        humanize_prompt = f"""
═══════════════════════════════════════════════════════════════════════════════
RISCRITTURA — APPLICA LO STILE APPRESO
═══════════════════════════════════════════════════════════════════════════════

Riscrivi il testo seguente applicando lo stile dell'autore che hai appreso durante
l'addestramento. Il testo originale contiene {word_count} parole. La riscrittura
DEVE contenere ALMENO {min_words} parole.

⚠️ CITAZIONI BIBLIOGRAFICHE: MANTIENI INTATTE tutte le citazioni [x] (es. [1], [2], [3]).
NON rimuoverle, NON spostarle. Se una frase contiene [3], la riscrittura DEVE contenere [3].

---
{testo_originale}
---

═══════════════════════════════════════════════════════════════════════════════
COME RISCRIVERE
═══════════════════════════════════════════════════════════════════════════════

Riscrivi come se fossi lo studente autore di questa tesi che rielabora il materiale
con le proprie parole. Hai letto e capito il contenuto; ora lo riscrivi nel tuo stile.

VOCABOLARIO:
- Usa parole semplici e dirette: "usa" non "utilizza", "mostra" non "evidenzia",
  "aiuta" non "contribuisce a", "serve" non "risulta necessario"
- Preferisci verbi concreti: "cresce", "cala", "cambia", "funziona", "dipende"
- NON usare MAI: "fondamentale", "significativo", "cruciale", "rilevante",
  "sottolineare", "evidenziare", "emergere", "inoltre", "pertanto", "dunque",
  "tuttavia", "rappresenta", "costituisce", "in questo contesto", "paradigma",
  "in definitiva", "in ultima analisi", "è importante notare", "vale la pena"

FRASI:
- Lunghezze MOLTO variabili: corte (8-12 parole), medie (18-25), lunghe (30-40)
- NON iniziare due paragrafi consecutivi allo stesso modo
- NON usare strutture simmetriche ("da un lato... dall'altro", "non solo... ma anche")
- NON usare domande retoriche seguite dalla risposta
- A volte collega frasi con "e" o "ma" semplici

STRUTTURA:
- Paragrafi di lunghezze diverse (da 3-4 frasi a 8-10 frasi)
- NON chiudere paragrafi con frasi a effetto, massime o aforismi
- Le transizioni tra paragrafi sono a volte esplicite, a volte implicite
- Il discorso è accademico ma naturale, come lo scriverebbe uno studente preparato

REGOLE:
- ALMENO {min_words} parole
- NON abbreviare, NON sintetizzare
- NON aggiungere interiezioni artificiali ("anzi no", "o meglio", "cioè no")
- NON inserire frasi incomplete o sospese a caso
- Scrivi testo accademico naturale, non testo con "errori finti"
- SOLO il testo riscritto, NESSUN commento o premessa
"""

        # Aggiungi il messaggio alla cronologia (usa il contesto dell'addestramento)
        self.conversation_history.append({
            "role": "user",
            "content": humanize_prompt
        })

        # Calcola max_tokens in base alla lunghezza del testo (~2.5 token per parola italiana + margine)
        estimated_tokens = int(word_count * 2.5) + 2000
        dynamic_max_tokens = max(estimated_tokens, MAX_TOKENS_TEST)

        # Invia la richiesta a Claude (stessa sessione, mantiene il contesto dell'addestramento)
        try:
            response = self.client.messages.create(
                model=self.MODEL_ID,
                max_tokens=dynamic_max_tokens,
                system=self.system_prompt,
                messages=self.conversation_history
            )
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

        # ═══════════════════════════════════════════════════════════════
        # POST-PROCESSING ANTI-AI
        # ═══════════════════════════════════════════════════════════════
        # DOPO aver ottenuto la risposta da Claude, applica l'algoritmo
        # di post-processing per rendere il testo COMPLETAMENTE anti-AI
        # ═══════════════════════════════════════════════════════════════

        from anti_ai_processor import humanize_text_post_processing

        # Applica trasformazioni anti-AI
        final_text = humanize_text_post_processing(assistant_message)

        return final_text

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
   
    # ============================================
    # FASE 4: CONTROLLO AI DETECTION
    # ============================================
    from detector import BinocularsDetector, format_detection_result

    print("=== CONTROLLO AI DETECTION ===")
    print("Inizializzazione del detector...")

    detector = BinocularsDetector(
        model_name="qwen2-1.5b",  # Consigliato per Mac (~6GB totali)
        threshold=0.9
    )

    risultato_detection = detector.detect(Path("/Users/micheledibisceglia/Developer/StyleForge/backend/results/contenuto_generato_20251220_181937.txt").read_text("utf-8"))
    print(format_detection_result(risultato_detection))

    if risultato_detection["is_ai_generated"]:
        print("ATTENZIONE: Il testo potrebbe essere rilevato come generato da AI.")
        print(f"Score: {risultato_detection['score']} (soglia: {risultato_detection['threshold']})")
    else:
        print("OK: Il testo sembra sufficientemente 'umano'.")
        print(f"Score: {risultato_detection['score']} (soglia: {risultato_detection['threshold']})")

