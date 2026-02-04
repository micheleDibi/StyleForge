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
        response = self.client.messages.create(
            model=self.MODEL_ID,
            max_tokens=MAX_TOKENS_TRAIN,
            system=self.system_prompt,
            messages=self.conversation_history
        )

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
        response = self.client.messages.create(
            model=self.MODEL_ID,
            max_tokens=MAX_TOKENS_TEST,
            system=self.system_prompt,
            messages=self.conversation_history
        )

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
RISCRITTURA ANTI-DETECTION v5 — ELIMINAZIONE PATTERN SPECIFICI
═══════════════════════════════════════════════════════════════════════════════

Riscrivi questo testo AI mantenendo ALMENO {min_words} parole (target: {min_words}-{max_words} parole).
Il testo originale contiene {word_count} parole. NON accorciare, NON riassumere, NON sintetizzare.
Hai interiorizzato lo stile dell'autore. Applicalo.

---
{testo_originale}
---

═══════════════════════════════════════════════════════════════════════════════
SEZIONE A: PATTERN AI IDENTIFICATI — VIETATI COMPLETAMENTE
═══════════════════════════════════════════════════════════════════════════════

I seguenti pattern sono stati identificati nei testi precedenti e DEVONO
essere eliminati. Tolleranza ZERO.

─────────────────────────────────────────────────────────────────────────────
A1. APERTURA "NUMERO/PAROLA. È IL/LA..."
─────────────────────────────────────────────────────────────────────────────

VIETATO:
  "Quattrocento ispettori. È il numero che..."
  "Sicurezza. È la parola che..."
  "2026. È l'anno in cui..."

PERCHÉ: Pattern AI riconoscibile. Troppo "costruito" come incipit.

ALTERNATIVE:
  - Inizia con una scena o un fatto concreto
  - Inizia con una voce (qualcuno che parla/racconta)
  - Inizia in medias res, senza presentazione
  - Inizia con una domanda NON retorica

ESEMPI CORRETTI:
  "Il 7 gennaio, mentre la Gazzetta Ufficiale pubblicava l'ennesimo decreto..."
  "Un ispettore del lavoro in Puglia — uno dei pochi rimasti — raccontava..."
  "Nelle campagne del foggiano, alle cinque di mattina, i furgoni..."

─────────────────────────────────────────────────────────────────────────────
A2. DOMANDE RETORICHE + RISPOSTA IMMEDIATA
─────────────────────────────────────────────────────────────────────────────

VIETATO:
  "Funzionerà? Difficile dirlo."
  "Dove andranno? Il decreto non lo specifica."
  "Chi controlla? Nessuno, di fatto."
  "Cambierà le cose? Cambierà alcune cose."

PERCHÉ: Pattern AI classico. La struttura Q+A breve è un segnale forte.

REGOLA: MAX 1 domanda retorica in TUTTO il testo.
E se la usi, la risposta deve essere LUNGA (5+ frasi) o ASSENTE.

ALTERNATIVE:
  - Affermazione dubbiosa: "Se funzionerà è tutto da capire, e non solo per..."
  - Domanda senza punto interrogativo: "Viene da chiedersi dove andranno"
  - Domanda lasciata aperta, si passa ad altro
  - Trasforma in discorso indiretto: "Molti si chiedono se funzionerà"

─────────────────────────────────────────────────────────────────────────────
A3. CHIUSURE A EFFETTO (PAROLA SINGOLA O FRASE BREVE FINALE)
─────────────────────────────────────────────────────────────────────────────

VIETATO:
  "Dovrebbero." / "Prova." / "Vedremo." / "Ecco." / "Se." / "È così."
  "Tocca a tutti." / "Sempre lì si finisce." / "Punto."

PERCHÉ: Troppe chiusure "ad effetto" = pattern AI riconoscibile.

REGOLA: MAX 2 chiusure brevi ad effetto in TUTTO il testo.
Le altre chiusure devono essere:
  - Informative (finiscono con un dato, un fatto)
  - Aperte (il ragionamento continua nel paragrafo dopo)
  - Sospese (non concludono, lasciano in aria)

ESEMPI DI CHIUSURE NON-AI:
  "...e i soldi per farlo non si sa da dove arriveranno"
  "...ma questo lo capiremo solo quando usciranno i dati del prossimo anno"
  "...che poi è lo stesso problema che avevano segnalato già nel 2019"
  [nessuna chiusura — il paragrafo dopo inizia collegandosi]

─────────────────────────────────────────────────────────────────────────────
A4. ANTITESI "SULLA CARTA... NELLA PRATICA"
─────────────────────────────────────────────────────────────────────────────

VIETATO:
  "Sulla carta è/sembra... Ma nella pratica..."
  "In teoria funziona. In pratica..."
  "Tutto giusto sulla carta. Solo che..."

PERCHÉ: Struttura antitetica ripetuta = pattern AI.

REGOLA: Puoi usare questa struttura MAX 1 VOLTA. E in forma variata.

ALTERNATIVE:
  - "Il decreto dice X — poi bisogna vedere se qualcuno lo fa davvero"
  - "X è scritto nero su bianco, ma chi lavora nel settore sa che..."
  - "Tra quello che c'è scritto e quello che succede nelle aziende..."
  - Elimina l'antitesi e vai diretto alla critica

─────────────────────────────────────────────────────────────────────────────
A5. LISTE MASCHERATE "C'È... C'È ANCHE... POI C'È..."
─────────────────────────────────────────────────────────────────────────────

VIETATO:
  "C'è il capitolo su... C'è anche la questione di... Poi c'è..."
  "Il primo aspetto riguarda... Il secondo tocca... Il terzo..."

PERCHÉ: È una lista numerata mascherata. I detector la riconoscono.

REGOLA: MAI elencare temi in sequenza ordinata.

ALTERNATIVE:
  - Intreccia i temi invece di separarli
  - Parti da un tema, fai una digressione, torna
  - Anticipa qualcosa che approfondirai dopo
  - Inizia dal tema meno ovvio, non dal più importante

─────────────────────────────────────────────────────────────────────────────
A6. PARENTESI "META-EDITORIALI"
─────────────────────────────────────────────────────────────────────────────

VIETATO:
  "(E qui si torna al discorso ispettori. Sempre lì si finisce.)"
  "(Il che solleva un'altra questione, ma forse è un altro discorso.)"
  "(E qui si apre un altro discorso, quello sulla burocrazia che...)"

PERCHÉ: Parentesi usate per meta-commenti strutturati = pattern AI.

REGOLA: Le parentesi devono sembrare PENSIERI BUTTATI LÌ, non editoriali.

ESEMPI CORRETTI:
  "(o almeno così raccontano)"
  "(ammesso che sia vero)"
  "(tre, per la precisione)"
  "(ma chi lo sa)"
  "(e non è poco)"

─────────────────────────────────────────────────────────────────────────────
A7. "CHI... SA CHE..." RIPETUTO
─────────────────────────────────────────────────────────────────────────────

VIETATO usare più di 1 VOLTA:
  "Chi conosce il settore sa che..."
  "Chi lavora in questo campo sa che..."
  "Chi si occupa di queste cose sa che..."

ALTERNATIVE (da variare):
  - "Nel settore lo sanno tutti che..."
  - "I funzionari te lo dicono subito:"
  - "Basta parlare con un ispettore per capire che..."
  - "È risaputo, tra gli addetti ai lavori, che..."
  - Elimina e afferma direttamente

─────────────────────────────────────────────────────────────────────────────
A8. "QUESTO NON SIGNIFICA... SIGNIFICA CHE..."
─────────────────────────────────────────────────────────────────────────────

VIETATO:
  "Questo non significa X. Significa Y."
  "Non vuol dire X. Vuol dire Y."

PERCHÉ: Struttura di chiarificazione troppo pulita = pattern AI.

ALTERNATIVE:
  - "Cioè, non è che sia inutile — solo che da solo non basta"
  - "Inutile no, ma nemmeno risolutivo"
  - Elimina la negazione e afferma direttamente Y

─────────────────────────────────────────────────────────────────────────────
A9. SEPARATORI VISIVI
─────────────────────────────────────────────────────────────────────────────

VIETATO: ---, ***, ___, ===, ~~~, o qualsiasi linea di separazione.

ZERO ECCEZIONI. Solo stacchi di paragrafo e titoli.

─────────────────────────────────────────────────────────────────────────────
A10. STRUTTURE PARALLELE PERFETTE
─────────────────────────────────────────────────────────────────────────────

VIETATO:
  "I sindacati dicono X. Gli imprenditori dicono Y. Le associazioni dicono Z."
  "È A, è B, è C, è D."
  "Serve X, serve Y, serve Z."

PERCHÉ: Parallelismo perfetto = pattern AI.

REGOLA: Se elenchi prospettive o elementi, ROMPI il parallelismo.

ESEMPIO CORRETTO:
  "I sindacati parlano di passo avanti, anche se insufficiente. 
   Gli imprenditori — prevedibilmente — si lamentano dei costi. 
   Le associazioni per i disabili avrebbero voluto di più, e lo dicono."

─────────────────────────────────────────────────────────────────────────────
A11. "BE'" SEMPRE COME CONNETTIVO DI CONTRASTO
─────────────────────────────────────────────────────────────────────────────

VIETATO usare "be'" sempre nello stesso modo:
  "be', nella pratica..."
  "be', il rischio è..."
  "be', quella è..."

REGOLA: Se usi "be'", varialo:
  - "be', sì e no"
  - "be', come dire"
  - "e be', cosa ti aspettavi"
  - Oppure sostituisci con: "insomma", "diciamo", "ecco"

─────────────────────────────────────────────────────────────────────────────
A12. TITOLI UNIFORMI
─────────────────────────────────────────────────────────────────────────────

VIETATO: Tutti i titoli con ## e tutti dichiarativi/descrittivi.

OBBLIGATORIO variare:
  - 1 titolo con # (più grande)
  - 1 sezione SENZA titolo (solo stacco)
  - 1 titolo che è una domanda
  - 1 titolo lungo (8+ parole, quasi una frase)
  - 1 titolo secco (1-2 parole)
  - 1 titolo ironico o colloquiale

─────────────────────────────────────────────────────────────────────────────
A13. OGNI SEZIONE CHIUDE "BENE"
─────────────────────────────────────────────────────────────────────────────

VIETATO: Chiudere ogni sezione con riflessione/sintesi/frase ad effetto.

REGOLA: Almeno 2 sezioni devono finire "male":
  - A metà ragionamento (il paragrafo dopo riprende)
  - Con un dato/fatto secco, senza commento
  - Con una frase sospesa che non conclude
  - Bruscamente, cambiando argomento

─────────────────────────────────────────────────────────────────────────────
A14. ASSENZA DI IMPERFEZIONI
─────────────────────────────────────────────────────────────────────────────

Il testo è TROPPO PULITO. Gli umani fanno errori, ripetizioni, frasi che
"scappano". 

OBBLIGATORIO inserire:
  - 1 ripetizione di parola a breve distanza (non errore, stile)
  - 1 frase che parte in un modo e finisce in un altro (anacoluto)
  - 1 autocorrezione ("anzi", "cioè no", "o meglio")
  - 1 frase un po' contorta/lunga che si segue a fatica
  - 1 cambio brusco di argomento senza transizione

═══════════════════════════════════════════════════════════════════════════════
SEZIONE B: TECNICHE POSITIVE DA APPLICARE
═══════════════════════════════════════════════════════════════════════════════

▸ STRUTTURA NON LINEARE

  Non seguire: intro → tema 1 → tema 2 → tema 3 → conclusione
  
  Invece:
  - Inizia da un dettaglio, poi allarga
  - Intreccia i temi (parla di A, digressione su B, torna a A)
  - Anticipa qualcosa ("ma di questo parliamo dopo")
  - Torna indietro ("e qui bisogna fare un passo indietro")

▸ ESEMPI CHE ENTRANO NEL FLUSSO

  NON: "Immaginiamo un'azienda..." / "Prendiamo il caso di..."
  
  SÌ:
  - "Un'azienda agricola pugliese con venti stagionali che già fatica..."
    [entra diretto, senza annuncio]
  - "Tipo quello che è successo a Brescia l'anno scorso, quando..."
  - "C'era un caso — non ricordo se in Emilia o in Veneto — di..."

▸ VOCI E PROSPETTIVE (variate nella forma)

  NON: "I sindacati dicono X. Gli imprenditori dicono Y."
  
  SÌ:
  - "Un sindacalista della CGIL, qualche mese fa, raccontava che..."
  - "Gli imprenditori — quelli onesti, almeno — si lamentano di..."
  - "Nei centri per l'impiego te lo dicono subito: il problema è..."
  - "C'è chi sostiene che... ma altri ribattono che..."

▸ COLLOQUIALISMI (distribuiti, non concentrati)

  OBBLIGATORI almeno 6 di questi, sparsi nel testo:
  - "insomma", "cioè", "diciamo", "ecco", "be'", "già"
  - "tipo" (come "per esempio")
  - "roba", "faccenda", "storia", "giro"
  - "mica", "mica tanto", "non è che"
  - "magari", "boh", "mah"

▸ INCERTEZZE ESPLICITE

  OBBLIGATORI almeno 4:
  - "non è chiaro", "non si sa", "difficile capire"
  - "forse", "probabilmente", "può darsi"
  - "chi può dirlo", "dipende", "non ho la risposta"
  - "sembra che", "pare che", "a quanto dicono"

▸ FRASI SPECIFICHE

  OBBLIGATORI:
  - 8+ frasi SOTTO le 5 parole
  - 4+ frasi SOPRA le 50 parole
  - 6+ frasi che iniziano con "E" o "Ma"
  - 3+ frasi che iniziano con "Ora," / "Poi," / "Già," / "Certo,"
  - 3+ trattini lunghi — per incisi
  - 2+ punto e virgola
  - 1 frase nominale (senza verbo)
  - 2 frasi sospese/interrotte

▸ PUNTEGGIATURA IRREGOLARE

  - Virgole "di respiro" (dove si farebbe pausa parlando)
  - Punti che spezzano frasi che potrebbero continuare
  - Due punti usati in modo non scolastico
  - Trattini — anche doppi — per incisi lunghi

═══════════════════════════════════════════════════════════════════════════════
SEZIONE C: LESSICO
═══════════════════════════════════════════════════════════════════════════════

▸ LISTA NERA (tolleranza zero):

  inoltre, pertanto, conseguentemente, dunque, quindi (a inizio frase)
  fondamentale, significativo, cruciale, essenziale, rilevante
  rappresenta, costituisce, evidenzia, sottolinea, emerge, risulta
  è importante notare, vale la pena, in questo contesto, in tal senso
  in conclusione, in sintesi, per riassumere, ricapitolando
  svolta, paradigma, rivoluzione, pietra miliare (per norme)
  al fine di, allo scopo di, nell'ottica di, in virtù di
  non da ultimo, non meno importante, da non sottovalutare
  a tal proposito, a tal fine, a tal riguardo
  alla luce di, in considerazione di

▸ LISTA BIANCA (usare preferibilmente):

  Connettivi: "insomma", "cioè", "ecco", "già", "poi", "ora"
  Verbi: "tocca", "serve", "manca", "pesa", "conta", "regge", "tiene"
  Nomi: "faccenda", "storia", "giro", "roba", "nodo", "punto"
  Espressioni: "il punto è", "la faccenda sta così", "il nodo è"
  Negazioni: "mica", "non è che", "neanche", "non proprio"

═══════════════════════════════════════════════════════════════════════════════
SEZIONE D: CHECKLIST FINALE
═══════════════════════════════════════════════════════════════════════════════

Prima di restituire il testo, verifica OGNI punto:

PATTERN ELIMINATI:
□ Zero aperture "X. È il/la..."
□ Max 1 domanda retorica (con risposta lunga o assente)
□ Max 2 chiusure brevi ad effetto
□ Max 1 "sulla carta... nella pratica"
□ Zero liste mascherate
□ Parentesi solo "buttate lì", non editoriali
□ Max 1 "chi... sa che..."
□ Zero "questo non significa... significa..."
□ Zero separatori (---, ecc.)
□ Parallelismi rotti
□ "Be'" variato o sostituito
□ Titoli asimmetrici
□ Almeno 2 sezioni che finiscono "male"
□ Imperfezioni inserite (anacoluto, autocorrezione, ecc.)

TECNICHE APPLICATE:
□ Struttura non lineare
□ Esempi che entrano nel flusso (senza "immaginiamo")
□ Voci variate nella forma
□ 6+ colloquialismi
□ 4+ incertezze esplicite
□ 8+ frasi sotto 5 parole
□ 4+ frasi sopra 50 parole
□ 6+ frasi con E/Ma iniziale
□ 3+ trattini lunghi
□ Punteggiatura irregolare

LESSICO:
□ Zero parole dalla lista nera
□ Parole dalla lista bianca presenti

LUNGHEZZA:
□ ALMENO {min_words} parole (target: {min_words}-{max_words})

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Riscrivi applicando TUTTO quanto sopra.
Il testo deve sembrare scritto da un giornalista esperto che conosce il tema,
scrive velocemente per una deadline, non rilegge troppo, lascia imperfezioni,
cambia idea, divaga, torna sui suoi passi, a volte si perde, a volte ripete.

REQUISITO CRITICO: il testo riscritto DEVE contenere ALMENO {min_words} parole.
NON tagliare, NON abbreviare, NON sintetizzare. Se il testo originale ha {word_count} parole,
la riscrittura deve averne almeno lo stesso numero. Se necessario, espandi i concetti.

SOLO il testo riscritto.
NESSUN commento, NESSUNA introduzione, NESSUNA spiegazione.
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
        response = self.client.messages.create(
            model=self.MODEL_ID,
            max_tokens=dynamic_max_tokens,
            system=self.system_prompt,
            messages=self.conversation_history
        )

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

