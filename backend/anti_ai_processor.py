"""
Algoritmo Anti-AI Post-Processing per StyleForge.

Questo modulo contiene l'algoritmo che viene eseguito DOPO aver ottenuto
la risposta dall'intelligenza artificiale, per trasformare il testo
e renderlo completamente non rilevabile dai detector AI.

PRINCIPI CHIAVE:
- I detector AI cercano regolarità statistiche nel testo
- I testi umani hanno alta varianza (perplessità e burstiness)
- L'algoritmo introduce "rumore umano" controllato

TECNICHE IMPLEMENTATE:
1. Rilevamento ed eliminazione di 14+ pattern AI specifici
2. Sostituzione lessicale (lista nera → lista bianca)
3. Iniezione di colloquialismi e incertezze
4. Variazione sintattica (lunghezza frasi, struttura)
5. Inserimento imperfezioni umane (anacoluti, autocorrezioni)
6. Aumento perplessità e burstiness
7. Randomizzazione punteggiatura
8. Sostituzione frasi AI ad alta frequenza
9. Trasformazioni Compilatio-specifiche (entropia, collocazioni, perplessità)
9. Diversificazione vocabolario ripetitivo
10. Rimozione cluster di hedging words
"""

import re
import random
import math
from typing import Dict, List, Tuple, Optional

# Importazione opzionale di spaCy (fallback se non disponibile)
try:
    import spacy
    nlp = spacy.load("it_core_news_sm")
except (OSError, ImportError):
    nlp = None


class AntiAIProcessor:
    """
    Processore anti-AI che trasforma il testo generato da Claude
    per renderlo completamente non rilevabile.

    Questo algoritmo opera DOPO la generazione del testo da parte di Claude,
    applicando una serie di trasformazioni per eliminare pattern AI e
    introdurre caratteristiche tipicamente umane.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Inizializza il processore anti-AI.

        Args:
            seed: Seed opzionale per riproducibilità (utile per testing)
        """
        if seed is not None:
            random.seed(seed)

        # ═══════════════════════════════════════════════════════════════
        # PATTERN AI DA RILEVARE E RIMUOVERE (14 pattern specifici)
        # ═══════════════════════════════════════════════════════════════

        # A1: Apertura "Numero/Parola. È il/la..."
        self.pattern_apertura_numero = re.compile(
            r'^([A-Za-zÀ-ÿ]+|\d+)\.\s+(È|Sono|Era|Erano|Sarà|Saranno)\s+(il|la|lo|i|le|gli|un|una|l\')\s+',
            re.MULTILINE | re.IGNORECASE
        )

        # A2: Domanda retorica + risposta breve immediata
        self.pattern_domanda_risposta_breve = re.compile(
            r'(\?)\s*\n?\s*([A-Z][a-zà-ÿ]{0,15}\.)\s',
            re.MULTILINE
        )

        # A3: Chiusure a effetto (parola singola finale)
        self.pattern_chiusura_effetto = re.compile(
            r'(?<=[.!?])\s*\n\s*([A-Z][a-zà-ÿ]{0,12})\.\s*(?=\n|$)',
            re.MULTILINE
        )

        # A4: Antitesi "sulla carta... nella pratica"
        self.pattern_carta_pratica = re.compile(
            r'(sulla carta|in teoria|teoricamente|a livello teorico)\s*[^.]*\.\s*(ma\s+)?(nella pratica|in pratica|praticamente|nella realtà)',
            re.IGNORECASE
        )

        # A5: Liste mascherate "C'è... C'è anche..."
        self.pattern_lista_mascherata = re.compile(
            r"(C'è\s+[^.]+\.\s*){2,}",
            re.IGNORECASE
        )

        # A6: Parentesi meta-editoriali
        self.pattern_parentesi_editoriali = re.compile(
            r'\([Ee]\s+qui\s+si\s+(torna|apre|arriva|entra)[^)]+\)'
        )

        # A7: "Chi conosce/lavora... sa che..."
        self.pattern_chi_sa_che = re.compile(
            r'[Cc]hi\s+(conosce|lavora|si occupa|opera|segue)\s+[^.]+\s+sa\s+che',
            re.IGNORECASE
        )

        # A8: "Questo non significa... Significa che..."
        self.pattern_non_significa = re.compile(
            r'(questo|ciò|quello|il che)\s+non\s+(significa|vuol dire|implica)[^.]+\.\s*(significa|vuol dire|implica)',
            re.IGNORECASE
        )

        # A9: Separatori visivi
        self.pattern_separatori = re.compile(
            r'^[\-\*\_\=\~\#]{3,}\s*$',
            re.MULTILINE
        )

        # A10: Strutture parallele perfette
        self.pattern_parallelismo = re.compile(
            r'([A-Z][a-zà-ÿ]+\s+(dicono|sostengono|affermano|pensano|ritengono)\s+[^.]+\.\s*){2,}',
            re.IGNORECASE
        )

        # A11: Pattern "quindi/dunque/pertanto" a inizio frase ripetuto
        self.pattern_quindi_inizio = re.compile(
            r'(?:^|\.\s+)(Quindi|Dunque|Pertanto|Conseguentemente)\s+',
            re.IGNORECASE | re.MULTILINE
        )

        # A12: Titoli tutti uniformi con ##
        self.pattern_titoli_uniformi = re.compile(
            r'^#{2}\s+[A-Z]',
            re.MULTILINE
        )

        # A13: Chiusure perfette di sezione
        self.pattern_chiusura_sezione = re.compile(
            r'[.!?]\s*\n\s*\n\s*(?=#{1,6}\s+|\Z)',
            re.MULTILINE
        )

        # A14: Testo troppo "pulito" - frasi tutte di lunghezza simile
        # (questo viene verificato con analisi statistica, non regex)

        # ═══════════════════════════════════════════════════════════════
        # LISTA NERA LESSICALE (tolleranza zero)
        # ═══════════════════════════════════════════════════════════════

        self.lista_nera = [
            # Connettivi formali
            'inoltre', 'pertanto', 'conseguentemente', 'dunque',
            'tuttavia', 'ciononostante', 'nondimeno',
            # Aggettivi enfatici AI
            'fondamentale', 'significativo', 'cruciale', 'essenziale',
            'rilevante', 'sostanziale', 'notevole', 'considerevole',
            # Verbi "gonfiati"
            'rappresenta', 'costituisce', 'evidenzia', 'sottolinea',
            'emerge', 'denota', 'manifesta',
            # Nota: 'risulta' rimosso perché matcherebbe anche in 'risultato'
            # Espressioni editoriali
            'è importante notare', 'vale la pena', 'in questo contesto',
            'in tal senso', 'è opportuno', 'è doveroso', 'è necessario sottolineare',
            # Conclusioni AI
            'in conclusione', 'in sintesi', 'per riassumere', 'ricapitolando',
            'in definitiva', 'tirando le somme',
            # Parole "impatto"
            'svolta', 'paradigma', 'rivoluzione', 'pietra miliare',
            'punto di svolta', 'game changer',
            # Locuzioni preposizionali formali
            'al fine di', 'allo scopo di', "nell'ottica di", 'in virtù di',
            'ai fini di', 'in funzione di',
            # Espressioni di importanza
            'non da ultimo', 'non meno importante', 'da non sottovalutare',
            'degno di nota', 'merita attenzione',
            # Riferimenti formali
            'a tal proposito', 'a tal fine', 'a tal riguardo',
            'alla luce di', 'in considerazione di', 'tenuto conto di'
        ]

        # ═══════════════════════════════════════════════════════════════
        # SOSTITUZIONI LISTA BIANCA (alternative umane)
        # ═══════════════════════════════════════════════════════════════

        self.sostituzioni = {
            'inoltre': ['poi', 'e', 'anche', 'già', 'tra l\'altro'],
            'pertanto': ['ecco perché', 'e così', 'insomma', 'e allora'],
            'conseguentemente': ['e quindi', 'così', 'e allora', 'da qui'],
            'dunque': ['insomma', 'ecco', 'beh', 'e niente'],
            'tuttavia': ['però', 'ma', 'solo che', 'il fatto è che'],
            'fondamentale': ['importante', 'chiave', 'centrale', 'grosso'],
            'significativo': ['notevole', 'grosso', 'non da poco', 'che pesa'],
            'cruciale': ['decisivo', 'chiave', 'che conta', 'determinante'],
            'essenziale': ['necessario', 'che serve', 'indispensabile', 'base'],
            'rilevante': ['che conta', 'importante', 'che pesa', 'notevole'],
            'rappresenta': ['è', 'fa', 'diventa', 'sta per'],
            'costituisce': ['è', 'forma', 'fa', 'compone'],
            'evidenzia': ['mostra', 'fa vedere', 'dice', 'mette in luce'],
            'sottolinea': ['dice', 'fa notare', 'segnala', 'punta su'],
            'emerge': ['viene fuori', 'si vede', 'salta fuori', 'appare'],
            'in conclusione': ['per chiudere', 'alla fine', 'in sostanza'],
            'in sintesi': ['in breve', 'stringendo', 'riassumendo'],
            'per riassumere': ['in breve', 'stringendo', 'in sostanza'],
            'al fine di': ['per', 'così da', 'in modo da', 'perché'],
            'allo scopo di': ['per', 'così da', 'perché', 'con l\'idea di'],
            "nell'ottica di": ['per', 'pensando a', 'verso', 'guardando a'],
            'in virtù di': ['per', 'grazie a', 'con', 'visto'],
            'alla luce di': ['visto che', 'considerando', 'dato che', 'visto'],
            'in considerazione di': ['visto', 'dato', 'considerando', 'tenendo conto che'],
            'svolta': ['cambiamento', 'novità', 'fatto nuovo'],
            'paradigma': ['modello', 'schema', 'modo di fare'],
            'rivoluzione': ['cambiamento', 'novità grossa'],
            'punto di svolta': ['momento chiave', 'passaggio importante', 'cambiamento netto'],
            'game changer': ['novità importante', 'fattore decisivo'],
            'pietra miliare': ['passo avanti', 'traguardo importante'],
        }

        # ═══════════════════════════════════════════════════════════════
        # FRASI AI AD ALTA FREQUENZA (AI High-Frequency Phrases)
        # ═══════════════════════════════════════════════════════════════
        # Queste frasi appaiono con frequenza molto più alta nei testi AI
        # rispetto ai testi umani. Vanno sostituite con alternative naturali.

        self.frasi_ai_alta_frequenza: Dict[str, List[str]] = {
            # ─────────────────────────────────────────────────────────────
            # PATTERN STRUTTURALI COMUNI AI (molto generici)
            # ─────────────────────────────────────────────────────────────

            # Pattern: "verbo + in modo/maniera + aggettivo"
            "in modo significativo": ["parecchio", "molto", "in maniera evidente", "notevolmente"],
            "in modo particolare": ["soprattutto", "specialmente", "in particolare"],
            "in maniera efficace": ["bene", "con efficacia", "in modo che funziona"],
            "in modo efficiente": ["bene", "senza sprechi", "con efficienza"],
            "in modo sostanziale": ["molto", "parecchio", "in buona parte"],
            "in maniera significativa": ["molto", "parecchio", "in modo evidente"],

            # Pattern: "questo/ciò + verbo + che/come"
            "questo significa che": ["vuol dire che", "cioè", "in pratica"],
            "questo implica che": ["vuol dire che", "significa che", "comporta che"],
            "questo comporta": ["porta a", "significa", "vuol dire"],
            "ciò significa che": ["vuol dire che", "in altre parole", "cioè"],
            "ciò implica": ["vuol dire", "significa", "comporta"],
            "questo suggerisce che": ["fa pensare che", "indica che", "lascia intendere che"],
            "ciò suggerisce": ["fa pensare", "indica", "lascia intendere"],
            "questo dimostra che": ["fa vedere che", "mostra che", "è la prova che"],
            "ciò dimostra": ["mostra", "fa vedere", "prova"],

            # Pattern: "è importante/fondamentale/essenziale + infinito"
            "è importante notare che": ["va detto che", "c'è da dire che", "bisogna notare che"],
            "è fondamentale comprendere": ["bisogna capire", "serve capire", "è chiave capire"],
            "è essenziale considerare": ["bisogna considerare", "serve tenere conto di", "va considerato"],
            "è cruciale sottolineare": ["va sottolineato", "bisogna dire", "è da notare"],
            "è importante sottolineare": ["va detto", "c'è da dire", "bisogna notare"],
            "è necessario precisare": ["va detto", "bisogna chiarire", "c'è da precisare"],

            # Pattern: "gioca/svolge un ruolo + aggettivo"
            "gioca un ruolo fondamentale": ["conta molto", "è centrale", "pesa parecchio"],
            "gioca un ruolo cruciale": ["è decisivo", "conta molto", "è chiave"],
            "gioca un ruolo importante": ["conta", "pesa", "ha il suo peso"],
            "svolge un ruolo chiave": ["è centrale", "conta molto", "è importante"],
            "svolge un ruolo significativo": ["conta", "ha peso", "incide"],
            "riveste un ruolo": ["ha un ruolo", "conta come", "funziona da"],

            # Pattern: "in questo contesto/scenario/ambito"
            "in questo contesto": ["qui", "in questa situazione", "in questo caso"],
            "in questo scenario": ["in questa situazione", "in questo caso", "così"],
            "in questo ambito": ["in questo campo", "qui", "in questo settore"],
            "in tale contesto": ["in questa situazione", "qui", "così"],
            "nel contesto di": ["parlando di", "riguardo a", "quando si parla di"],
            "nell'ambito di": ["nel campo di", "in", "quando si parla di"],

            # Pattern: "al fine di/allo scopo di/con l'obiettivo di"
            "al fine di": ["per", "così da", "in modo da"],
            "allo scopo di": ["per", "così da", "con l'idea di"],
            "con l'obiettivo di": ["per", "puntando a", "cercando di"],
            "nell'ottica di": ["per", "pensando a", "guardando a"],
            "ai fini di": ["per", "per quanto riguarda", "in vista di"],

            # Pattern: "risulta essere/appare/sembra essere"
            "risulta essere": ["è", "sembra", "pare"],
            "appare essere": ["sembra", "pare", "è"],
            "sembra essere": ["pare", "è", "sembra"],
            "si rivela essere": ["è", "si mostra", "risulta"],
            "tende ad essere": ["è spesso", "di solito è", "in genere è"],

            # Pattern: "è possibile + infinito"
            "è possibile notare": ["si nota", "si vede", "c'è da notare"],
            "è possibile osservare": ["si vede", "si nota", "emerge"],
            "è possibile individuare": ["si trovano", "ci sono", "emergono"],
            "è possibile affermare": ["si può dire", "diciamo che", "insomma"],
            "è possibile concludere": ["si conclude che", "insomma", "alla fine"],

            # Pattern: "per quanto riguarda/concerne"
            "per quanto riguarda": ["riguardo a", "parlando di", "quanto a"],
            "per quanto concerne": ["riguardo a", "quanto a", "per"],
            "relativamente a": ["riguardo a", "quanto a", "per"],
            "in relazione a": ["riguardo a", "rispetto a", "quanto a"],
            "con riferimento a": ["riguardo a", "parlando di", "quanto a"],

            # Pattern: "a causa di/grazie a/a seguito di"
            "a causa di": ["per", "per via di", "a forza di"],
            "grazie a": ["per merito di", "con", "per"],
            "a seguito di": ["dopo", "per", "in seguito a"],
            "in seguito a": ["dopo", "per via di", "a causa di"],
            "a fronte di": ["davanti a", "considerando", "rispetto a"],

            # Pattern: "assume/riveste + importanza/rilevanza"
            "assume particolare importanza": ["diventa importante", "conta molto", "pesa"],
            "riveste particolare importanza": ["è molto importante", "conta parecchio", "ha peso"],
            "assume rilevanza": ["diventa importante", "conta", "ha peso"],
            "riveste rilevanza": ["conta", "ha importanza", "pesa"],

            # ─────────────────────────────────────────────────────────────
            # CONNETTIVI E TRANSIZIONI TIPICI AI
            # ─────────────────────────────────────────────────────────────

            "da un lato": ["da una parte", "per certi versi", "in un senso"],
            "dall'altro lato": ["dall'altra", "per altri versi", "in un altro senso"],
            "d'altra parte": ["però", "dall'altra", "allo stesso tempo"],
            "in altre parole": ["cioè", "vale a dire", "insomma"],
            "vale a dire": ["cioè", "ossia", "in pratica"],
            "in definitiva": ["alla fine", "insomma", "tirando le somme"],
            "in ultima analisi": ["alla fine", "in fondo", "insomma"],
            "a ben vedere": ["a pensarci", "se ci si riflette", "guardando bene"],
            "ad ogni modo": ["comunque", "in ogni caso", "però"],
            "in ogni caso": ["comunque", "ad ogni modo", "però"],
            "nello specifico": ["in particolare", "precisamente", "nel dettaglio"],
            "in particolare": ["soprattutto", "specialmente", "nello specifico"],
            "più precisamente": ["meglio", "cioè", "in dettaglio"],

            # ─────────────────────────────────────────────────────────────
            # PATTERN CON "CHE" TIPICI AI
            # ─────────────────────────────────────────────────────────────

            "che ha portato a": ["che ha causato", "da cui è venuto", "che ha provocato"],
            "che hanno portato a": ["che hanno causato", "da cui sono venuti", "che hanno provocato"],
            "che contribuisce a": ["che aiuta a", "che serve a", "che porta a"],
            "che contribuiscono a": ["che aiutano a", "che servono a", "che portano a"],
            "che permette di": ["che consente di", "che dà modo di", "grazie a cui si può"],
            "che permettono di": ["che consentono di", "che danno modo di", "grazie a cui si possono"],
            "che consente di": ["che permette di", "che dà modo di", "che rende possibile"],
            "che risulta essere": ["che è", "che sembra", "che pare"],
            "che risultano essere": ["che sono", "che sembrano", "che paiono"],
            "che si traduce in": ["che diventa", "che porta a", "che significa"],
            "che si traducono in": ["che diventano", "che portano a", "che significano"],

            # ─────────────────────────────────────────────────────────────
            # PATTERN TEMPORALI/CAUSALI TIPICI AI
            # ─────────────────────────────────────────────────────────────

            "nel corso degli ultimi anni": ["negli ultimi anni", "di recente", "ultimamente"],
            "nel corso degli anni": ["negli anni", "col tempo", "via via"],
            "nel corso del tempo": ["col tempo", "man mano", "via via"],
            "negli ultimi decenni": ["negli ultimi anni", "di recente", "ultimamente"],
            "in tempi recenti": ["di recente", "ultimamente", "negli ultimi tempi"],
            "in epoca moderna": ["oggi", "ai giorni nostri", "nel mondo moderno"],
            "ai giorni nostri": ["oggi", "adesso", "ora"],
            "allo stato attuale": ["adesso", "oggi", "al momento"],
            "attualmente": ["adesso", "ora", "al momento"],

            # ─────────────────────────────────────────────────────────────
            # PATTERN DI ENFASI TIPICI AI
            # ─────────────────────────────────────────────────────────────

            "non si può negare che": ["è vero che", "certo che", "effettivamente"],
            "non si può ignorare": ["bisogna considerare", "c'è da dire", "va notato"],
            "non si può sottovalutare": ["conta", "pesa", "è importante"],
            "è innegabile che": ["è chiaro che", "certo che", "senza dubbio"],
            "è evidente che": ["è chiaro che", "si vede che", "pare che"],
            "è indubbio che": ["è chiaro che", "certo che", "sicuramente"],
            "va sottolineato che": ["c'è da dire che", "va detto che", "bisogna notare che"],
            "merita attenzione": ["va notato", "c'è da considerare", "è interessante"],
            "degno di nota": ["interessante", "da notare", "curioso"],

            # ─────────────────────────────────────────────────────────────
            # PATTERN CONCLUSIVI TIPICI AI
            # ─────────────────────────────────────────────────────────────

            "in conclusione": ["insomma", "alla fine", "per chiudere"],
            "per concludere": ["insomma", "chiudendo", "in breve"],
            "in sintesi": ["in breve", "stringendo", "riassumendo"],
            "per riassumere": ["in breve", "stringendo", "in sostanza"],
            "tirando le somme": ["in sostanza", "nel complesso", "in pratica"],
            "alla luce di quanto detto": ["considerando tutto", "visto questo", "dopo tutto"],
            "sulla base di quanto esposto": ["visto questo", "considerando tutto", "da qui"],

            # ─────────────────────────────────────────────────────────────
            # PATTERN CON NUMERI/QUANTITÀ TIPICI AI
            # ─────────────────────────────────────────────────────────────

            "un numero significativo di": ["molti", "parecchi", "tanti"],
            "un numero crescente di": ["sempre più", "tanti", "molti"],
            "una percentuale significativa": ["buona parte", "molti", "parecchi"],
            "la maggior parte di": ["molti", "la maggioranza di", "buona parte di"],
            "una quota rilevante": ["buona parte", "molti", "parecchi"],
            "in misura crescente": ["sempre di più", "via via", "man mano"],
            "in larga misura": ["molto", "in buona parte", "per lo più"],

            # ─────────────────────────────────────────────────────────────
            # PATTERN MODALI/DI POSSIBILITÀ TIPICI AI
            # ─────────────────────────────────────────────────────────────

            "potrebbe essere considerato": ["si può vedere come", "è forse", "in un certo senso è"],
            "può essere visto come": ["è come", "funziona da", "sembra"],
            "può essere interpretato come": ["si può leggere come", "sembra", "pare"],
            "potrebbero essere": ["forse sono", "magari sono", "sono forse"],
            "potrebbe rappresentare": ["forse è", "potrebbe essere", "magari rappresenta"],
            "è possibile che": ["forse", "può darsi che", "magari"],
            "è probabile che": ["probabilmente", "forse", "pare che"],
            "è plausibile che": ["è possibile che", "forse", "può darsi che"],

            # ─────────────────────────────────────────────────────────────
            # VERBI "GONFIATI" IN CONTESTO FRASALE
            # ─────────────────────────────────────────────────────────────

            "si configura come": ["è", "funziona come", "agisce come"],
            "si configurano come": ["sono", "funzionano come", "agiscono come"],
            "si caratterizza per": ["ha come tratto", "si distingue per", "è noto per"],
            "si distingue per": ["è particolare per", "ha come tratto", "è noto per"],
            "si presenta come": ["appare come", "è", "sembra"],
            "si pone come": ["è", "funziona come", "si propone come"],
            "si colloca": ["sta", "è", "si trova"],
            "si inserisce": ["entra", "fa parte", "sta"],

            # ─────────────────────────────────────────────────────────────
            # ESPRESSIONI DI COMPARAZIONE TIPICHE AI
            # ─────────────────────────────────────────────────────────────

            "rispetto al passato": ["prima", "un tempo", "anni fa"],
            "rispetto a prima": ["prima", "un tempo", "in passato"],
            "a differenza di": ["diversamente da", "non come", "mentre"],
            "contrariamente a": ["diversamente da", "al contrario di", "mentre"],
            "analogamente a": ["come", "allo stesso modo di", "simile a"],
            "in modo analogo": ["allo stesso modo", "così come", "similmente"],
            "in modo simile": ["allo stesso modo", "come", "così"],
        }

        # ═══════════════════════════════════════════════════════════════
        # PATTERN REGEX PER FRASI AI (per matching flessibile)
        # ═══════════════════════════════════════════════════════════════

        self.pattern_frasi_ai: List[Tuple[re.Pattern, List[str]]] = [
            # Pattern: "ha/hanno + participio passato + un/una + sostantivo + aggettivo"
            (re.compile(r'\b(ha|hanno)\s+(subito|registrato|vissuto|attraversato)\s+un[ao]?\s+\w+\s+(significativ[ao]|important[ei]|notevol[ei]|rilevant[ei])', re.IGNORECASE),
             ["ha visto", "ha avuto", "c'è stato/a"]),

            # Pattern: "rappresenta/costituisce + un/una + elemento/fattore/aspetto + chiave/fondamentale"
            (re.compile(r'\b(rappresenta|costituisce)\s+un[ao]?\s+(elemento|fattore|aspetto|punto)\s+(chiave|fondamentale|cruciale|essenziale)', re.IGNORECASE),
             ["è importante", "è centrale", "ha un peso importante"]),

            # Pattern: "emerge/risulta + che/come"
            (re.compile(r'\b(emerge|risulta)\s+(che|come)\b', re.IGNORECASE),
             ["si vede che", "viene fuori che", "pare che"]),

            # Pattern: "assume/riveste + un'importanza + aggettivo"
            (re.compile(r"\b(assume|riveste)\s+un['']?importanza\s+\w+", re.IGNORECASE),
             ["diventa importante", "conta molto", "pesa"]),

            # Pattern: "nell'era/epoca + di/della/del"
            (re.compile(r"\bnell['']?(era|epoca)\s+(di|del|della|dell[''])", re.IGNORECASE),
             ["oggi con", "adesso che c'è", "nel tempo di"]),

            # Pattern: "in termini di"
            (re.compile(r'\bin\s+termini\s+di\b', re.IGNORECASE),
             ["per quanto riguarda", "parlando di", "su"]),

            # Pattern: "a livello + aggettivo/sostantivo"
            (re.compile(r'\ba\s+livello\s+(globale|mondiale|nazionale|locale|internazionale|europeo)', re.IGNORECASE),
             ["nel mondo", "in Italia", "qui", "su scala"]),
        ]

        # ═══════════════════════════════════════════════════════════════
        # VOCABOLARIO RIPETITIVO DA DIVERSIFICARE
        # ═══════════════════════════════════════════════════════════════

        self.vocabolario_ripetitivo: Dict[str, List[str]] = {
            # Parole che l'AI tende a ripetere troppo
            "significativo": ["importante", "notevole", "rilevante", "marcato", "grosso"],
            "significativa": ["importante", "notevole", "rilevante", "marcata", "grossa"],
            "significativi": ["importanti", "notevoli", "rilevanti", "marcati", "grossi"],
            "significative": ["importanti", "notevoli", "rilevanti", "marcate", "grosse"],
            "significativamente": ["molto", "parecchio", "notevolmente", "decisamente", "assai"],
            "fondamentale": ["importante", "chiave", "centrale", "base", "essenziale"],
            "fondamentali": ["importanti", "chiave", "centrali", "base", "essenziali"],
            "cruciale": ["chiave", "decisivo", "importante", "determinante", "critico"],
            "cruciali": ["chiave", "decisivi", "importanti", "determinanti", "critici"],
            "particolare": ["speciale", "specifico", "singolare", "certo", "dato"],
            "particolari": ["speciali", "specifici", "singolari", "certi", "dati"],
            "particolarmente": ["soprattutto", "specialmente", "molto", "assai", "specie"],
            "pertanto": ["quindi", "perciò", "così", "dunque", "e allora"],
            "tuttavia": ["però", "ma", "eppure", "solo che", "comunque"],
            "inoltre": ["poi", "e", "anche", "in più", "tra l'altro"],
            "conseguentemente": ["quindi", "così", "perciò", "e allora", "da qui"],
            "sostanzialmente": ["in pratica", "di fatto", "in sostanza", "alla fine", "insomma"],
            "indubbiamente": ["senza dubbio", "certamente", "sicuramente", "di sicuro", "certo"],
            "evidentemente": ["chiaramente", "ovviamente", "è chiaro che", "si vede che", "palesemente"],
            "probabilmente": ["forse", "magari", "può darsi", "chissà", "presumibilmente"],
            "certamente": ["sicuramente", "certo", "di sicuro", "senza dubbio", "davvero"],
            "necessariamente": ["per forza", "obbligatoriamente", "inevitabilmente", "comunque"],
            "attualmente": ["adesso", "ora", "oggi", "al momento", "in questo periodo"],
            "principalmente": ["soprattutto", "per lo più", "in gran parte", "specialmente"],
            "essenzialmente": ["in pratica", "in sostanza", "fondamentalmente", "di base"],
            "specificamente": ["in particolare", "nello specifico", "precisamente", "esattamente"],
            "relativamente": ["abbastanza", "piuttosto", "in modo relativo", "tutto sommato"],
            "assolutamente": ["del tutto", "completamente", "proprio", "davvero", "totalmente"],
            "completamente": ["del tutto", "interamente", "totalmente", "in pieno", "appieno"],
            "estremamente": ["molto", "assai", "parecchio", "davvero", "tantissimo"],
        }

        # ═══════════════════════════════════════════════════════════════
        # CLUSTER DI HEDGING DA RIMUOVERE
        # ═══════════════════════════════════════════════════════════════

        self.hedging_da_rimuovere: List[Tuple[re.Pattern, str]] = [
            # Hedging eccessivi da eliminare o semplificare
            (re.compile(r',?\s*a nostro avviso,?\s*', re.IGNORECASE), ' '),
            (re.compile(r',?\s*a mio parere,?\s*', re.IGNORECASE), ' '),
            (re.compile(r',?\s*secondo il nostro punto di vista,?\s*', re.IGNORECASE), ' '),
            (re.compile(r',?\s*per così dire,?\s*', re.IGNORECASE), ' '),
            (re.compile(r',?\s*se così si può dire,?\s*', re.IGNORECASE), ' '),
            (re.compile(r',?\s*in un certo senso,?\s*', re.IGNORECASE), ' '),
            (re.compile(r',?\s*in qualche modo,?\s*', re.IGNORECASE), ' '),
            (re.compile(r',?\s*per certi versi,?\s*', re.IGNORECASE), ' '),
            (re.compile(r',?\s*sotto certi aspetti,?\s*', re.IGNORECASE), ' '),
            # Doppio hedging (forse + probabilmente, etc.)
            (re.compile(r'\b(forse|probabilmente|possibilmente)\s+\1\b', re.IGNORECASE), r'\1'),
            (re.compile(r'\b(forse)\s+(probabilmente|possibilmente)\b', re.IGNORECASE), 'forse'),
            (re.compile(r'\b(probabilmente)\s+(forse|possibilmente)\b', re.IGNORECASE), 'probabilmente'),
        ]

        # ═══════════════════════════════════════════════════════════════
        # PATTERN STRUTTURALI DA VARIARE (inizi frase formali)
        # ═══════════════════════════════════════════════════════════════

        self.pattern_inizi_formali: List[Tuple[re.Pattern, List[str]]] = [
            (re.compile(r'^È importante notare che\s+', re.MULTILINE | re.IGNORECASE),
             ["Va detto che ", "C'è da dire che ", "Bisogna considerare che ", "Ecco, "]),
            (re.compile(r'^Occorre precisare che\s+', re.MULTILINE | re.IGNORECASE),
             ["Bisogna chiarire che ", "Va chiarito che ", "È bene dire che ", "C'è da precisare che "]),
            (re.compile(r'^In questo contesto\s*,?\s*', re.MULTILINE | re.IGNORECASE),
             ["Qui ", "In questa situazione ", "Così ", "In questo caso "]),
            (re.compile(r'^Per quanto riguarda\s+', re.MULTILINE | re.IGNORECASE),
             ["Riguardo a ", "Su ", "Parlando di ", "Per "]),
            (re.compile(r'^A questo proposito\s*,?\s*', re.MULTILINE | re.IGNORECASE),
             ["Su questo ", "A tal proposito ", "In merito ", "Ecco, "]),
            (re.compile(r'^Va sottolineato che\s+', re.MULTILINE | re.IGNORECASE),
             ["C'è da notare che ", "Va detto che ", "Bisogna dire che ", "Ecco: "]),
            (re.compile(r'^È necessario evidenziare\s+', re.MULTILINE | re.IGNORECASE),
             ["Va detto ", "C'è da dire ", "Bisogna notare ", "Ecco "]),
            (re.compile(r'^Si può affermare che\s+', re.MULTILINE | re.IGNORECASE),
             ["Diciamo che ", "Insomma ", "Si può dire che ", "Ecco, "]),
            (re.compile(r'^È opportuno ricordare\s+', re.MULTILINE | re.IGNORECASE),
             ["Va ricordato ", "C'è da ricordare ", "Bisogna ricordare ", ""]),
            (re.compile(r'^Come è stato menzionato\s*,?\s*', re.MULTILINE | re.IGNORECASE),
             ["Come detto ", "Come già detto ", "Dicevamo ", ""]),
            (re.compile(r'^Come precedentemente indicato\s*,?\s*', re.MULTILINE | re.IGNORECASE),
             ["Come detto ", "Come già detto ", "Prima dicevamo ", ""]),
        ]

        # ═══════════════════════════════════════════════════════════════
        # ELEMENTI DI VARIAZIONE NATURALE
        # ═══════════════════════════════════════════════════════════════

        # Connettivi semplici per sostituire quelli formali
        self.connettivi_semplici = ['e', 'ma', 'però', 'anche', 'poi']

        # Incisi con trattino (brevi e naturali per contesto accademico)
        self.incisi_trattino = [
            '— almeno in parte —',
            '— come si è visto —',
            '— in modo più o meno diretto —',
            '— e questo è un punto chiave —',
            '— anche se non sempre —',
            '— va detto —',
            '— e non solo —'
        ]

        # Ristrutturazioni di inizio frase per rompere uniformità
        self.alternative_inizio_frase = [
            'Il punto è che ',
            'In pratica, ',
            'Il fatto è che ',
            'Va detto che ',
            'Non è scontato che ',
            'Si può dire che ',
            'Come si è visto, ',
            'Questo aspetto ',
            'Sul piano pratico, ',
            'Da questo punto di vista, ',
        ]

    # ═══════════════════════════════════════════════════════════════════════
    # METODI DI ANALISI
    # ═══════════════════════════════════════════════════════════════════════

    def analizza_pattern_ai(self, testo: str) -> Dict[str, int]:
        """
        Analizza il testo e conta tutti i pattern AI presenti.

        Returns:
            Dizionario con il conteggio di ogni pattern rilevato
        """
        return {
            'apertura_numero': len(self.pattern_apertura_numero.findall(testo)),
            'domanda_risposta_breve': len(self.pattern_domanda_risposta_breve.findall(testo)),
            'chiusura_effetto': len(self.pattern_chiusura_effetto.findall(testo)),
            'carta_pratica': len(self.pattern_carta_pratica.findall(testo)),
            'lista_mascherata': len(self.pattern_lista_mascherata.findall(testo)),
            'parentesi_editoriali': len(self.pattern_parentesi_editoriali.findall(testo)),
            'chi_sa_che': len(self.pattern_chi_sa_che.findall(testo)),
            'non_significa': len(self.pattern_non_significa.findall(testo)),
            'separatori': len(self.pattern_separatori.findall(testo)),
            'parallelismo': len(self.pattern_parallelismo.findall(testo)),
            'quindi_inizio': len(self.pattern_quindi_inizio.findall(testo)),
            'parole_lista_nera': sum(1 for p in self.lista_nera if p.lower() in testo.lower())
        }

    def calcola_burstiness(self, testo: str) -> float:
        """
        Calcola la "burstiness" del testo (varianza nella lunghezza delle frasi).

        Testi AI tendono ad avere bassa burstiness (frasi uniformi).
        Testi umani hanno alta burstiness (frasi molto variabili).

        Returns:
            Coefficiente di variazione (deviazione standard / media)
        """
        frasi = re.split(r'[.!?]+', testo)
        lunghezze = [len(f.split()) for f in frasi if f.strip()]

        if len(lunghezze) < 2:
            return 0.0

        media = sum(lunghezze) / len(lunghezze)
        if media == 0:
            return 0.0

        varianza = sum((l - media) ** 2 for l in lunghezze) / len(lunghezze)
        deviazione = math.sqrt(varianza)

        return deviazione / media

    def conta_elementi_umani(self, testo: str) -> Dict[str, int]:
        """
        Conta gli elementi di variazione presenti nel testo.
        """
        testo_lower = testo.lower()
        frasi = re.split(r'[.!?]+', testo)

        connettivi_semplici = ['e ', 'ma ', 'però ', 'anche ', 'poi ']

        return {
            'connettivi_semplici': sum(1 for f in frasi if any(f.strip().lower().startswith(c) for c in connettivi_semplici)),
            'frasi_corte': sum(1 for f in frasi if 0 < len(f.split()) <= 8),
            'frasi_medie': sum(1 for f in frasi if 9 <= len(f.split()) <= 25),
            'frasi_lunghe': sum(1 for f in frasi if len(f.split()) > 25),
            'parentesi': testo.count('('),
            'trattini': testo.count('—') + testo.count(' - '),
            'punto_virgola': testo.count(';')
        }

    # ═══════════════════════════════════════════════════════════════════════
    # METODI DI TRASFORMAZIONE - RIMOZIONE PATTERN AI
    # ═══════════════════════════════════════════════════════════════════════

    def rimuovi_separatori(self, testo: str) -> str:
        """Rimuove tutti i separatori visivi (---, ***, ecc.)."""
        return self.pattern_separatori.sub('\n', testo)

    def trasforma_aperture_numero(self, testo: str) -> str:
        """
        Trasforma le aperture tipiche AI ("Numero. È il...") in forme più naturali.
        """
        def sostituisci(match):
            parola = match.group(1)
            alternative = [
                f"Parliamo di {parola.lower()}. ",
                f"Il punto è {parola.lower()}. ",
                f"C'è questa faccenda di {parola.lower()}. ",
                f"{parola}, ecco, ",
                f"Prendiamo {parola.lower()}. "
            ]
            return random.choice(alternative)

        return self.pattern_apertura_numero.sub(sostituisci, testo)

    def espandi_risposte_brevi(self, testo: str) -> str:
        """
        Espande le risposte troppo brevi dopo le domande retoriche.
        """
        def sostituisci(match):
            espansioni = [
                f"{match.group(1)} Difficile dirlo con certezza, e forse non è nemmeno la domanda giusta. ",
                f"{match.group(1)} Ecco, la risposta non è semplice come sembra. ",
                f"{match.group(1)} Beh, dipende da come la guardi, e da chi te lo chiede. ",
                f"{match.group(1)} La questione è più complicata di così. "
            ]
            return random.choice(espansioni)

        return self.pattern_domanda_risposta_breve.sub(sostituisci, testo)

    def trasforma_carta_pratica(self, testo: str) -> str:
        """
        Trasforma le antitesi "sulla carta... nella pratica" in forme variate.
        """
        def sostituisci(match):
            alternative = [
                "Il decreto dice una cosa — poi bisogna vedere se qualcuno la fa davvero. ",
                "È scritto nero su bianco, certo. Ma chi lavora nel settore sa che ",
                "Tra quello che c'è scritto e quello che succede davvero c'è un abisso. ",
                "A parole sembra tutto bello. I fatti, però, "
            ]
            return random.choice(alternative)

        return self.pattern_carta_pratica.sub(sostituisci, testo, count=1)

    def rompi_parallelismi(self, testo: str) -> str:
        """
        Individua strutture parallele e le rompe inserendo variazioni.
        """
        matches = list(self.pattern_parallelismo.finditer(testo))

        for match in reversed(matches):
            originale = match.group(0)
            frasi = re.split(r'(?<=[.!?])\s+', originale)

            if len(frasi) >= 2:
                variazioni = [
                    ' — e questo è interessante — ',
                    ' (prevedibilmente) ',
                    ', come ci si poteva aspettare, ',
                    ' — e qui sta il punto — '
                ]

                if len(frasi) > 1 and frasi[1]:
                    frasi[1] = random.choice(variazioni) + frasi[1][0].lower() + frasi[1][1:]

                testo = testo[:match.start()] + ' '.join(frasi) + testo[match.end():]

        return testo

    def trasforma_parentesi_editoriali(self, testo: str) -> str:
        """
        Rimuove le parentesi meta-editoriali tipiche dell'AI.
        """
        return self.pattern_parentesi_editoriali.sub('', testo)

    def riduci_chi_sa_che(self, testo: str) -> str:
        """
        Riduce le occorrenze di "chi conosce... sa che" a massimo 1.
        """
        matches = list(self.pattern_chi_sa_che.finditer(testo))

        if len(matches) > 1:
            for match in reversed(matches[1:]):
                alternative = [
                    "Nel settore lo sanno tutti che",
                    "Gli addetti ai lavori te lo dicono subito:",
                    "È risaputo che",
                    "Basta parlare con qualcuno del settore per capire che"
                ]
                testo = testo[:match.start()] + random.choice(alternative) + testo[match.end():]

        return testo

    def trasforma_non_significa(self, testo: str) -> str:
        """
        Trasforma le strutture "non significa X. Significa Y" in forme più naturali.
        """
        def sostituisci(match):
            alternative = [
                "Cioè, non è che sia inutile — solo che da solo non basta. ",
                "Inutile no, ma nemmeno risolutivo. ",
                "Non è proprio così, ecco. ",
                "La questione è un po' diversa. "
            ]
            return random.choice(alternative)

        return self.pattern_non_significa.sub(sostituisci, testo)

    def trasforma_quindi_inizio(self, testo: str) -> str:
        """
        Trasforma i "quindi/dunque/pertanto" a inizio frase.
        """
        count = [0]

        def sostituisci_limitato(match):
            count[0] += 1
            if count[0] > 2:
                return match.group(0)

            sep = match.group(0)[0] if match.group(0)[0] in '.!?' else ''
            alternative = ['E allora ', 'Ecco perché ', 'Da qui ', 'Insomma ', 'E così ']
            return sep + ' ' + random.choice(alternative) if sep else random.choice(alternative)

        return self.pattern_quindi_inizio.sub(sostituisci_limitato, testo)

    def trasforma_liste_mascherate(self, testo: str) -> str:
        """
        Trasforma le liste mascherate "C'è... C'è anche... Poi c'è..."
        """
        matches = list(self.pattern_lista_mascherata.finditer(testo))

        for match in reversed(matches):
            originale = match.group(0)
            elementi = re.findall(r"C'è\s+([^.]+)\.", originale, re.IGNORECASE)

            if len(elementi) >= 2:
                alternative_strutture = [
                    lambda e: f"La questione principale riguarda {e[0]}. Ma c'è anche da considerare {e[1]}" + (f", per non parlare poi di {e[2]}" if len(e) > 2 else ""),
                    lambda e: f"Da una parte {e[0]}. Dall'altra {e[1]}" + (f". E poi, ecco, {e[2]}" if len(e) > 2 else ""),
                    lambda e: f"Il primo nodo è {e[0]} — e già questo basterebbe. Ma pesa anche {e[1]}" + (f", senza contare {e[2]}" if len(e) > 2 else ""),
                ]

                nuovo_testo = random.choice(alternative_strutture)(elementi)
                testo = testo[:match.start()] + nuovo_testo + ". " + testo[match.end():]

        return testo

    # ═══════════════════════════════════════════════════════════════════════
    # METODI DI TRASFORMAZIONE - LESSICO
    # ═══════════════════════════════════════════════════════════════════════

    def sostituisci_lista_nera(self, testo: str) -> str:
        """
        Sostituisce le parole della lista nera con alternative più umane.
        Ordina per lunghezza decrescente per evitare match parziali.
        """
        # Ordina per lunghezza decrescente: frasi lunghe prima di parole singole
        lista_ordinata = sorted(self.lista_nera, key=len, reverse=True)
        for parola in lista_ordinata:
            if parola.lower() in testo.lower():
                alternative = self.sostituzioni.get(parola.lower())
                if alternative:
                    sostituzione = random.choice(alternative)
                    # Usa word boundaries per evitare match parziali
                    pattern = re.compile(r'\b' + re.escape(parola) + r'\b', re.IGNORECASE)
                    testo = pattern.sub(sostituzione, testo, count=1)
                else:
                    pattern = re.compile(r'\b' + re.escape(parola) + r'\b,?\s*', re.IGNORECASE)
                    testo = pattern.sub('', testo, count=1)

        return testo

    # ═══════════════════════════════════════════════════════════════════════
    # METODI DI TRASFORMAZIONE - FRASI AI AD ALTA FREQUENZA
    # ═══════════════════════════════════════════════════════════════════════

    def sostituisci_frasi_ai_alta_frequenza(self, testo: str) -> str:
        """
        Sostituisce le frasi che appaiono con frequenza molto più alta
        nei testi AI rispetto ai testi umani (rilevate dai detector AI).

        Questa è la funzione chiave per ridurre la metrica "AI Phrases" a 0%.
        """
        # Prima passa: sostituzione esatta delle frasi (con word boundaries)
        for frase_ai, alternative in self.frasi_ai_alta_frequenza.items():
            if frase_ai.lower() in testo.lower():
                # Usa word boundaries per evitare sostituzioni parziali
                # es: "risulta" non deve matchare in "risultato"
                pattern = re.compile(r'\b' + re.escape(frase_ai) + r'\b', re.IGNORECASE)
                matches = list(pattern.finditer(testo))

                # Sostituisci ogni occorrenza con un'alternativa diversa (se possibile)
                for match in reversed(matches):
                    sostituzione = random.choice(alternative)
                    # Mantieni la capitalizzazione originale
                    if match.group()[0].isupper():
                        sostituzione = sostituzione[0].upper() + sostituzione[1:]
                    testo = testo[:match.start()] + sostituzione + testo[match.end():]

        # Seconda passa: pattern regex per matching flessibile
        for pattern, alternative in self.pattern_frasi_ai:
            matches = list(pattern.finditer(testo))
            for match in reversed(matches):
                sostituzione = random.choice(alternative)
                # Gestisci casi con "/" (opzioni multiple)
                if '/' in sostituzione:
                    sostituzione = random.choice(sostituzione.split('/'))
                if match.group()[0].isupper():
                    sostituzione = sostituzione[0].upper() + sostituzione[1:]
                testo = testo[:match.start()] + sostituzione + testo[match.end():]

        return testo

    def diversifica_vocabolario_ripetitivo(self, testo: str) -> str:
        """
        Diversifica le parole che l'AI tende a ripetere troppo.

        Se una parola appare più di 2 volte, sostituisce le occorrenze
        successive (dopo la prima) con sinonimi/alternative.
        """
        for parola, alternative in self.vocabolario_ripetitivo.items():
            # Trova tutte le occorrenze della parola
            pattern = re.compile(r'\b' + re.escape(parola) + r'\b', re.IGNORECASE)
            matches = list(pattern.finditer(testo))

            # Se la parola appare più di 2 volte, sostituisci alcune occorrenze
            if len(matches) > 2:
                # Sostituisci circa il 60% delle occorrenze dopo la prima
                for match in reversed(matches[1:]):
                    if random.random() < 0.6:
                        sostituzione = random.choice(alternative)
                        # Mantieni capitalizzazione
                        if match.group()[0].isupper():
                            sostituzione = sostituzione[0].upper() + sostituzione[1:]
                        testo = testo[:match.start()] + sostituzione + testo[match.end():]
            elif len(matches) == 2:
                # Se appare 2 volte, sostituisci la seconda con probabilità 50%
                if random.random() < 0.5:
                    match = matches[1]
                    sostituzione = random.choice(alternative)
                    if match.group()[0].isupper():
                        sostituzione = sostituzione[0].upper() + sostituzione[1:]
                    testo = testo[:match.start()] + sostituzione + testo[match.end():]

        return testo

    def rimuovi_hedging_eccessivo(self, testo: str) -> str:
        """
        Rimuove o semplifica i cluster di hedging words tipici dell'AI.

        L'AI tende a usare troppi "forse", "probabilmente", "in un certo senso"
        che rendono il testo riconoscibile.
        """
        for pattern, sostituzione in self.hedging_da_rimuovere:
            testo = pattern.sub(sostituzione, testo)

        # Pulizia spazi multipli risultanti
        testo = re.sub(r'\s+', ' ', testo)
        testo = re.sub(r',\s*,', ',', testo)

        return testo

    def trasforma_inizi_formali(self, testo: str) -> str:
        """
        Trasforma gli inizi di frase troppo formali/accademici tipici dell'AI.

        Pattern come "È importante notare che", "Per quanto riguarda", etc.
        vengono sostituiti con alternative più naturali.
        """
        for pattern, alternative in self.pattern_inizi_formali:
            matches = list(pattern.finditer(testo))
            for match in reversed(matches):
                sostituzione = random.choice(alternative)
                testo = testo[:match.start()] + sostituzione + testo[match.end():]

        return testo

    def conta_frasi_ai(self, testo: str) -> Dict[str, int]:
        """
        Conta quante frasi AI ad alta frequenza sono presenti nel testo.

        Utile per debug e per verificare l'efficacia del processing.

        Returns:
            Dizionario con il conteggio delle frasi AI trovate
        """
        conteggio = {}
        testo_lower = testo.lower()

        for frase_ai in self.frasi_ai_alta_frequenza.keys():
            count = testo_lower.count(frase_ai.lower())
            if count > 0:
                conteggio[frase_ai] = count

        # Conta anche i pattern regex
        for pattern, _ in self.pattern_frasi_ai:
            matches = pattern.findall(testo)
            if matches:
                conteggio[pattern.pattern[:50] + '...'] = len(matches)

        return conteggio

    # ═══════════════════════════════════════════════════════════════════════
    # METODI DI TRASFORMAZIONE - INIEZIONE ELEMENTI UMANI
    # ═══════════════════════════════════════════════════════════════════════

    def _split_preserving_paragraphs(self, testo: str):
        """
        Divide il testo in frasi preservando la struttura dei paragrafi.
        Restituisce una lista di tuple (frase, separatore_dopo) dove il separatore
        può essere ' ' o '\n\n' per preservare i paragrafi.
        """
        paragraphs = re.split(r'(\n\s*\n)', testo)
        frasi = []
        separatori = []

        for i, block in enumerate(paragraphs):
            if re.match(r'^\n\s*\n$', block):
                if separatori:
                    separatori[-1] = block
                continue

            sentence_parts = re.split(r'(?<=[.!?])\s+', block)
            for j, s in enumerate(sentence_parts):
                frasi.append(s)
                if j < len(sentence_parts) - 1:
                    separatori.append(' ')
                else:
                    separatori.append(' ')

            if i < len(paragraphs) - 1 and i + 1 < len(paragraphs) and re.match(r'^\n\s*\n$', paragraphs[i + 1]):
                if separatori:
                    separatori[-1] = '\n\n'

        return frasi, separatori

    def _join_preserving_paragraphs(self, frasi, separatori):
        """
        Ricompone le frasi preservando i separatori originali (spazi e paragrafi).
        """
        if not frasi:
            return ''
        risultato = frasi[0]
        for i in range(1, len(frasi)):
            sep = separatori[i - 1] if i - 1 < len(separatori) else ' '
            risultato += sep + frasi[i]
        return risultato

    def diversifica_inizi_frase(self, testo: str) -> str:
        """
        Rompe l'uniformità degli inizi di frase e paragrafo.
        Se due frasi/paragrafi consecutivi iniziano in modo simile, ristruttura uno dei due.
        """
        frasi, separatori = self._split_preserving_paragraphs(testo)

        if len(frasi) < 4:
            return testo

        modifiche = 0
        max_modifiche = max(3, len(frasi) // 10)

        for i in range(1, len(frasi)):
            if modifiche >= max_modifiche:
                break

            frase_corrente = frasi[i].strip()
            frase_precedente = frasi[i - 1].strip()

            if not frase_corrente or not frase_precedente:
                continue

            # Rileva inizi simili (stesse prime 2 parole o stessa struttura)
            parole_corr = frase_corrente.split()
            parole_prec = frase_precedente.split()

            inizio_simile = False
            if len(parole_corr) >= 2 and len(parole_prec) >= 2:
                if parole_corr[0].lower() == parole_prec[0].lower():
                    inizio_simile = True

            if inizio_simile and len(parole_corr) > 5:
                # Ristruttura la frase corrente aggiungendo un inizio diverso
                nuovo_inizio = random.choice(self.alternative_inizio_frase)
                frasi[i] = nuovo_inizio + parole_corr[0].lower() + ' ' + ' '.join(parole_corr[1:])
                modifiche += 1

        return self._join_preserving_paragraphs(frasi, separatori)

    def spezza_frasi_uniformi(self, testo: str) -> str:
        """
        Se le frasi hanno lunghezza troppo uniforme (bassa burstiness),
        spezza alcune lunghe e unisci alcune corte per creare variazione.
        """
        frasi, separatori = self._split_preserving_paragraphs(testo)

        if len(frasi) < 6:
            return testo

        lunghezze = [len(f.split()) for f in frasi if f.strip()]
        if not lunghezze:
            return testo

        media = sum(lunghezze) / len(lunghezze)
        if media == 0:
            return testo

        # Calcola variazione attuale
        varianza = sum((l - media) ** 2 for l in lunghezze) / len(lunghezze)
        cv = math.sqrt(varianza) / media

        # Se la variazione è già buona (>0.5), non fare nulla
        if cv > 0.5:
            return testo

        nuove_frasi = []
        nuovi_separatori = []
        i = 0

        while i < len(frasi):
            frase = frasi[i]
            parole = frase.split()
            num_parole = len(parole)

            # Frasi molto lunghe (>35 parole): prova a spezzare
            if num_parole > 35 and random.random() < 0.5:
                punto_rottura = num_parole // 2
                # Cerca un punto naturale di rottura
                for j in range(punto_rottura - 5, min(punto_rottura + 5, len(parole))):
                    if 0 < j < len(parole) and parole[j].rstrip(',') in ['e', 'ma', 'che', 'dove', 'quando', 'mentre', 'perché']:
                        punto_rottura = j
                        break

                parte1 = ' '.join(parole[:punto_rottura])
                parte2 = ' '.join(parole[punto_rottura:])

                if not parte1.rstrip().endswith(('.', '!', '?')):
                    parte1 = parte1.rstrip(',') + '.'
                if parte2 and parte2[0].islower():
                    parte2 = parte2[0].upper() + parte2[1:]

                nuove_frasi.append(parte1)
                nuovi_separatori.append(' ')
                if parte2.strip():
                    nuove_frasi.append(parte2)

            # Frasi corte consecutive: unisci con "e" o "ma"
            elif num_parole < 10 and i + 1 < len(frasi) and len(frasi[i + 1].split()) < 10 and random.random() < 0.3:
                frase2 = frasi[i + 1].strip()
                if frase.rstrip().endswith('.') and frase2:
                    # Unisci le due frasi
                    congiunzione = random.choice(['e ', 'ma ', ', e '])
                    unita = frase.rstrip()[:-1] + ', ' + congiunzione + frase2[0].lower() + frase2[1:]
                    nuove_frasi.append(unita)
                    i += 1  # Salta la frase successiva
                else:
                    nuove_frasi.append(frase)
            else:
                nuove_frasi.append(frase)

            # Preserva separatore
            if i < len(separatori):
                nuovi_separatori.append(separatori[i])
            i += 1

        return self._join_preserving_paragraphs(nuove_frasi, nuovi_separatori)

    def riordina_clausole(self, testo: str) -> str:
        """
        Riordina le clausole in alcune frasi complesse per creare variazione sintattica.
        Es: "Dato che X, si osserva Y" → "Y, dato che X"
        """
        frasi, separatori = self._split_preserving_paragraphs(testo)

        modifiche = 0
        max_modifiche = max(2, len(frasi) // 15)

        for i in range(len(frasi)):
            if modifiche >= max_modifiche:
                break

            frase = frasi[i].strip()
            if not frase or len(frase.split()) < 10:
                continue

            # Pattern: frase che inizia con subordinata + virgola + principale
            match = re.match(
                r'^(Quando|Se|Dato che|Poiché|Sebbene|Anche se|Mentre|Nonostante)\s+([^,]+),\s+(.+)$',
                frase, re.IGNORECASE
            )
            if match and random.random() < 0.4:
                congiunzione = match.group(1).lower()
                subordinata = match.group(2)
                principale = match.group(3)
                # Inverti: principale + congiunzione + subordinata
                if principale and principale[0].islower():
                    principale = principale[0].upper() + principale[1:]
                frasi[i] = f"{principale.rstrip('.')} {congiunzione} {subordinata}."
                modifiche += 1

        return self._join_preserving_paragraphs(frasi, separatori)

    def varia_lunghezza_frasi(self, testo: str) -> str:
        """
        Aumenta la burstiness variando la lunghezza delle frasi:
        - Spezza frasi molto lunghe
        - Aggiunge incisi con trattino alle frasi medie
        """
        frasi, separatori = self._split_preserving_paragraphs(testo)
        nuove_frasi = []
        nuovi_separatori = []

        for i, frase in enumerate(frasi):
            parole = frase.split()
            num_parole = len(parole)

            # Frasi molto lunghe (>45 parole): spezza
            if num_parole > 45:
                punto_rottura = num_parole // 2
                for j in range(punto_rottura - 5, punto_rottura + 5):
                    if 0 < j < len(parole) and parole[j] in [',', 'e', 'ma', 'che', 'dove', 'quando']:
                        punto_rottura = j + 1
                        break

                parte1 = ' '.join(parole[:punto_rottura])
                parte2 = ' '.join(parole[punto_rottura:])

                if not parte1.rstrip().endswith(('.', '!', '?')):
                    parte1 = parte1.rstrip(',') + '.'
                if parte2 and parte2[0].islower():
                    parte2 = parte2[0].upper() + parte2[1:]

                nuove_frasi.append(parte1)
                if parte2.strip():
                    nuovi_separatori.append(' ')
                    nuove_frasi.append(parte2)

            # Frasi medie (15-35 parole): occasionalmente aggiungi inciso
            elif 15 < num_parole < 35 and random.random() < 0.25:
                punto_inciso = random.randint(4, num_parole - 4)
                inciso = random.choice(self.incisi_trattino)
                parole.insert(punto_inciso, inciso)
                nuove_frasi.append(' '.join(parole))

            else:
                nuove_frasi.append(frase)

            # Preserva il separatore originale
            if i < len(separatori):
                nuovi_separatori.append(separatori[i])

        return self._join_preserving_paragraphs(nuove_frasi, nuovi_separatori)

    def varia_punteggiatura(self, testo: str) -> str:
        """
        Rende la punteggiatura meno "perfetta":
        - Aggiunge virgole di respiro
        - Inserisce punto e virgola
        - Varia l'uso dei due punti
        """
        # Aggiungi virgole prima di "che" in alcune frasi lunghe
        testo = re.sub(
            r'(\w{8,})\s+che\s+',
            lambda m: f"{m.group(1)}, che " if random.random() < 0.3 else m.group(0),
            testo
        )

        # Converti alcuni ":" in " —"
        testo = re.sub(
            r':\s+([a-z])',
            lambda m: f' — {m.group(1)}' if random.random() < 0.2 else m.group(0),
            testo
        )

        # Inserisci qualche punto e virgola
        frasi, separatori = self._split_preserving_paragraphs(testo)
        for i in range(len(frasi)):
            if ', e ' in frasi[i] and random.random() < 0.2:
                frasi[i] = frasi[i].replace(', e ', '; ', 1)
            elif ', ma ' in frasi[i] and random.random() < 0.15:
                frasi[i] = frasi[i].replace(', ma ', '; ma ', 1)

        return self._join_preserving_paragraphs(frasi, separatori)

    def varia_titoli(self, testo: str) -> str:
        """
        Varia la struttura dei titoli markdown per renderli meno uniformi.
        """
        lines = testo.split('\n')
        titoli_idx = [i for i, line in enumerate(lines) if line.strip().startswith('#')]

        if len(titoli_idx) > 2:
            for i, idx in enumerate(titoli_idx):
                line = lines[idx]

                # Varia i livelli
                if random.random() < 0.3:
                    # Rimuovi completamente i #
                    lines[idx] = line.lstrip('#').strip()
                elif random.random() < 0.3 and line.startswith('##'):
                    # Riduci il livello
                    lines[idx] = '#' + line.lstrip('#')
                elif random.random() < 0.2:
                    # Rendi il titolo una domanda
                    titolo = line.lstrip('#').strip()
                    if not titolo.endswith('?'):
                        lines[idx] = line.replace(titolo, titolo + '?')

        return '\n'.join(lines)

    # ═══════════════════════════════════════════════════════════════════════
    # METODI COMPILATIO-SPECIFICI
    # ═══════════════════════════════════════════════════════════════════════

    def sostituisci_collocazioni_compilatio(self, testo: str) -> str:
        """
        Sostituisce collocazioni formali che Compilatio rileva come AI.
        Queste sono combinazioni di parole che l'AI usa con frequenza
        molto superiore rispetto ai testi umani.
        """
        collocazioni = {
            "al contempo": ["allo stesso tempo", "insieme", "e intanto", "nel frattempo"],
            "in maniera": ["in modo", "nel senso che", "tipo"],
            "nell'ambito": ["nel campo", "quando si parla di", "per quanto riguarda"],
            "in termini di": ["parlando di", "riguardo a", "per", "come"],
            "dal punto di vista": ["guardando", "per quanto riguarda", "se pensiamo a"],
            "prendere in considerazione": ["considerare", "pensare a", "tenere conto di", "guardare"],
            "mettere in evidenza": ["mostrare", "far vedere", "far notare"],
            "porre l'accento su": ["insistere su", "concentrarsi su", "puntare su"],
            "dare luogo a": ["causare", "creare", "portare a", "generare"],
            "fare riferimento a": ["riferirsi a", "parlare di", "citare", "richiamare"],
            "a livello di": ["per", "in", "sul piano di", "quando si guarda"],
            "nel contesto di": ["in", "quando si parla di", "dentro", "nel quadro di"],
            "ai fini di": ["per", "allo scopo di", "in vista di"],
            "in relazione a": ["riguardo a", "su", "per quanto riguarda", "circa"],
            "per quanto concerne": ["per", "riguardo a", "su", "quanto a"],
            "alla luce di": ["considerando", "visto", "dato", "tenendo conto di"],
            "è opportuno sottolineare": ["va detto", "c'è da dire", "bisogna notare"],
            "è importante evidenziare": ["va notato", "vale la pena dire", "c'è da segnalare"],
            "assume un ruolo": ["ha un ruolo", "conta", "pesa", "è importante"],
            "riveste un'importanza": ["è importante", "conta", "pesa", "ha valore"],
            "si configura come": ["è", "diventa", "funziona come", "si presenta come"],
            "risulta essere": ["è", "sembra", "appare", "si rivela"],
            "si rivela": ["è", "appare", "si mostra", "si dimostra"],
            "assume particolare rilevanza": ["diventa importante", "conta molto", "pesa parecchio"],
        }

        for frase, alternative in collocazioni.items():
            pattern = re.compile(re.escape(frase), re.IGNORECASE)
            matches = list(pattern.finditer(testo))
            for match in reversed(matches):
                sostituzione = random.choice(alternative)
                # Preserva capitalizzazione
                if match.group()[0].isupper():
                    sostituzione = sostituzione[0].upper() + sostituzione[1:]
                testo = testo[:match.start()] + sostituzione + testo[match.end():]

        return testo

    def aumenta_entropia_lessicale(self, testo: str) -> str:
        """
        Introduce scelte lessicali rare che aumentano l'entropia a livello di token.
        Compilatio misura quanto ogni token è prevedibile dal contesto.
        Parole rare ma valide abbassano drasticamente la prevedibilità.
        Applicato con probabilità 15-20% per non stravolgere il testo.
        """
        sostituzioni_rare = {
            "importante": ["rilevante", "pregnante", "calzante", "di spicco", "di peso"],
            "problema": ["nodo", "questione spinosa", "grattacapo", "garbuglio", "punto critico"],
            "situazione": ["congiuntura", "circostanza", "frangente", "quadro", "scenario"],
            "cambiamento": ["mutamento", "virata", "stravolgimento", "scossone", "svolta"],
            "sviluppo": ["evoluzione", "maturazione", "avanzata", "progressione"],
            "aspetto": ["sfaccettatura", "risvolto", "piega", "versante", "lato"],
            "elemento": ["ingrediente", "tassello", "fattore", "componente", "pezzo"],
            "necessario": ["indispensabile", "imprescindibile", "doveroso", "irrinunciabile"],
            "possibile": ["fattibile", "realizzabile", "attuabile", "plausibile", "pensabile"],
            "difficile": ["arduo", "spinoso", "ostico", "impervio", "complesso"],
            "risultato": ["esito", "riscontro", "frutto", "prodotto", "resa"],
            "obiettivo": ["traguardo", "meta", "scopo", "mira", "fine"],
            "sistema": ["meccanismo", "apparato", "ingranaggio", "impianto", "struttura"],
            "processo": ["percorso", "iter", "dinamica", "procedura", "cammino"],
            "approccio": ["ottica", "prospettiva", "logica", "impostazione", "angolazione"],
            "ambito": ["campo", "terreno", "sfera", "settore", "area"],
            "analisi": ["disamina", "lettura", "esame", "vaglio", "scrutinio"],
            "impatto": ["peso", "ricaduta", "effetto", "portata", "incidenza"],
            "strategia": ["linea", "tattica", "piano", "mossa", "impostazione"],
            "contributo": ["apporto", "concorso", "partecipazione", "aiuto"],
        }

        for parola, rare_alternatives in sostituzioni_rare.items():
            pattern = re.compile(r'\b' + re.escape(parola) + r'\b', re.IGNORECASE)
            matches = list(pattern.finditer(testo))
            for match in reversed(matches):
                if random.random() < 0.18:
                    sostituzione = random.choice(rare_alternatives)
                    if match.group()[0].isupper():
                        sostituzione = sostituzione[0].upper() + sostituzione[1:]
                    testo = testo[:match.start()] + sostituzione + testo[match.end():]

        return testo

    def inserisci_micro_imperfezioni(self, testo: str) -> str:
        """
        Inserisce micro-imperfezioni umane che abbassano drasticamente
        lo score AI su Compilatio. Queste imperfezioni sono invisibili
        al lettore medio ma visibilissime ai detector.
        Max ~1 ogni 8 frasi per non esagerare.
        """
        frasi = re.split(r'(?<=[.!?])\s+', testo)
        if len(frasi) < 6:
            return testo

        modifiche = 0
        max_modifiche = max(3, len(frasi) // 8)

        for i in range(len(frasi)):
            if modifiche >= max_modifiche:
                break
            frase = frasi[i]
            parole = frase.split()
            if len(parole) < 8:
                continue

            roll = random.random()

            if roll < 0.10:
                # Aggiunta di pensiero sospeso con trattino
                frasi[i] = frase.rstrip('.!?') + ' — almeno da quello che si vede.'
                modifiche += 1
            elif roll < 0.18:
                # Autocorrezione mid-sentence
                punto_inserimento = random.randint(3, min(len(parole) - 3, len(parole) - 1))
                correzioni = [', anzi, ', ', o meglio, ', ', cioè, ', ', diciamo, ']
                parole.insert(punto_inserimento, random.choice(correzioni))
                frasi[i] = ' '.join(parole)
                modifiche += 1
            elif roll < 0.25:
                # Inciso parentetico
                punto = random.randint(3, min(len(parole) - 3, len(parole) - 1))
                incisi = [
                    '(e non è scontato)',
                    '(che poi è tutto da vedere)',
                    '(e qui ci sarebbe da discutere)',
                    '(almeno secondo chi se ne occupa)',
                    '(come spesso accade)',
                    '(e non è poco)',
                    '(vale la pena ribadirlo)',
                ]
                parole.insert(punto, random.choice(incisi))
                frasi[i] = ' '.join(parole)
                modifiche += 1
            elif roll < 0.30:
                # Aggiunta di connettivo colloquiale a inizio frase
                connettivi = ['Insomma, ', 'Ecco, ', 'Ora, ', 'Beh, ', 'Detto questo, ']
                if not frase.startswith(('Insomma', 'Ecco', 'Ora', 'Beh', 'Detto')):
                    frasi[i] = random.choice(connettivi) + frase[0].lower() + frase[1:]
                    modifiche += 1

        return ' '.join(frasi)

    def varia_perplexita_tra_frasi(self, testo: str) -> str:
        """
        Alterna deliberatamente frasi semplici/brevi e frasi complesse.
        Compilatio rileva che le frasi AI hanno perplessità uniforme.
        Le frasi umane alternano tra molto semplici e molto complesse.
        """
        frasi = re.split(r'(?<=[.!?])\s+', testo)
        if len(frasi) < 8:
            return testo

        modifiche = 0
        max_modifiche = max(2, len(frasi) // 10)

        for i in range(2, len(frasi), 4):  # Ogni 4 frasi
            if i >= len(frasi) or modifiche >= max_modifiche:
                break
            frase = frasi[i]
            parole = frase.split()
            if len(parole) < 10:
                continue

            roll = random.random()
            if roll < 0.30:
                # Semplificazione: spezza la frase in due più corte
                punto_taglio = len(parole) // 2
                # Trova un punto naturale di taglio vicino alla metà
                for j in range(punto_taglio - 2, min(punto_taglio + 3, len(parole))):
                    if j < len(parole) and parole[j].rstrip('.,;:') in ('che', 'e', 'ma', 'dove', 'quando', 'perché', 'mentre'):
                        punto_taglio = j
                        break

                prima_parte = ' '.join(parole[:punto_taglio])
                if not prima_parte.rstrip().endswith(('.', '!', '?')):
                    prima_parte = prima_parte.rstrip('.,;:') + '.'
                seconda_parte = ' '.join(parole[punto_taglio:])
                if seconda_parte and seconda_parte[0].islower():
                    seconda_parte = seconda_parte[0].upper() + seconda_parte[1:]
                frasi[i] = prima_parte + ' ' + seconda_parte
                modifiche += 1
            elif roll < 0.50:
                # Complessificazione: aggiungi subordinata
                inserti = [
                    ', il che non è affatto banale,',
                    ', e questo va tenuto presente,',
                    ', anche se non tutti sono d\'accordo,',
                    ', cosa che spesso viene trascurata,',
                    ', e non si tratta di un dettaglio,',
                ]
                punto = len(parole) // 2
                parole.insert(punto, random.choice(inserti))
                frasi[i] = ' '.join(parole)
                modifiche += 1

        return ' '.join(frasi)

    # ═══════════════════════════════════════════════════════════════════════
    # METODO PRINCIPALE DI PROCESSING
    # ═══════════════════════════════════════════════════════════════════════

    def _protect_citations(self, testo: str):
        """
        Protegge le citazioni bibliografiche [x] sostituendole con placeholder
        che non verranno toccati dalle trasformazioni.

        Returns:
            Tuple (testo_con_placeholder, mappa_ripristino)
        """
        import re
        citations = re.findall(r'\[\d+\]', testo)
        mappa = {}
        for i, cit in enumerate(citations):
            placeholder = f"__CITE{i}__"
            mappa[placeholder] = cit
            testo = testo.replace(cit, placeholder, 1)
        return testo, mappa

    def _restore_citations(self, testo: str, mappa: dict) -> str:
        """Ripristina le citazioni bibliografiche dai placeholder."""
        for placeholder, citation in mappa.items():
            testo = testo.replace(placeholder, citation)
        return testo

    def process(self, testo: str) -> str:
        """
        Esegue l'intero pipeline di post-processing anti-AI.

        Il processo è organizzato in fasi:
        0. PROTEZIONE CITAZIONI - Protegge [x] dalle trasformazioni
        1. PULIZIA - Rimuove elementi facilmente rilevabili
        2. FRASI AI ALTA FREQUENZA - Sostituisce frasi ad alta frequenza AI (CRITICO)
        3. TRASFORMAZIONE PATTERN - Modifica strutture AI riconoscibili
        4. LESSICO - Sostituisce parole della lista nera + diversifica ripetizioni
        5. HEDGING - Rimuove cluster di hedging eccessivo
        5.5 COMPILATIO - Collocazioni, entropia lessicale, micro-imperfezioni, variazione perplessità
        6. INIEZIONE UMANA - Aggiunge elementi tipicamente umani
        7. VARIAZIONE STRUTTURA - Aumenta perplessità e burstiness
        8. NORMALIZZAZIONE - Pulizia finale
        9. RIPRISTINO CITAZIONI - Ripristina [x] dai placeholder

        Args:
            testo: Il testo generato dall'AI da processare

        Returns:
            Il testo trasformato, non rilevabile dai detector AI
        """

        # ═══════════════════════════════════════════════════════════════
        # FASE 0: PROTEZIONE CITAZIONI BIBLIOGRAFICHE
        # ═══════════════════════════════════════════════════════════════
        testo, mappa_citazioni = self._protect_citations(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 1: PULIZIA
        # ═══════════════════════════════════════════════════════════════
        testo = self.rimuovi_separatori(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 2: FRASI AI AD ALTA FREQUENZA
        # ═══════════════════════════════════════════════════════════════
        # Sostituisce frasi ad alta frequenza rilevate dai detector AI
        # Va eseguita PRIMA delle altre trasformazioni per massimizzare l'efficacia
        testo = self.sostituisci_frasi_ai_alta_frequenza(testo)
        testo = self.trasforma_inizi_formali(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 3: TRASFORMAZIONE PATTERN AI
        # ═══════════════════════════════════════════════════════════════
        testo = self.trasforma_aperture_numero(testo)
        testo = self.espandi_risposte_brevi(testo)
        testo = self.trasforma_carta_pratica(testo)
        testo = self.rompi_parallelismi(testo)
        testo = self.trasforma_parentesi_editoriali(testo)
        testo = self.riduci_chi_sa_che(testo)
        testo = self.trasforma_non_significa(testo)
        testo = self.trasforma_quindi_inizio(testo)
        testo = self.trasforma_liste_mascherate(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 4: SOSTITUZIONE LESSICALE + DIVERSIFICAZIONE
        # ═══════════════════════════════════════════════════════════════
        testo = self.sostituisci_lista_nera(testo)
        testo = self.diversifica_vocabolario_ripetitivo(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 5: RIMOZIONE HEDGING ECCESSIVO
        # ═══════════════════════════════════════════════════════════════
        testo = self.rimuovi_hedging_eccessivo(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 5.5: TRASFORMAZIONI COMPILATIO-SPECIFICHE
        # ═══════════════════════════════════════════════════════════════
        # Compilatio usa analisi perplessità, n-gram e distribuzione token
        # diversa da altri detector. Queste fasi target specifiche.
        testo = self.sostituisci_collocazioni_compilatio(testo)
        testo = self.aumenta_entropia_lessicale(testo)
        testo = self.inserisci_micro_imperfezioni(testo)
        testo = self.varia_perplexita_tra_frasi(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 6: VARIAZIONE STRUTTURALE NATURALE
        # ═══════════════════════════════════════════════════════════════
        testo = self.diversifica_inizi_frase(testo)
        testo = self.spezza_frasi_uniformi(testo)
        testo = self.riordina_clausole(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 7: VARIAZIONE PUNTEGGIATURA E TITOLI
        # ═══════════════════════════════════════════════════════════════
        testo = self.varia_punteggiatura(testo)
        testo = self.varia_titoli(testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 8: NORMALIZZAZIONE FINALE
        # ═══════════════════════════════════════════════════════════════

        # Fix grammaticali post-sostituzione
        # Rimuovi parole duplicate consecutive ("che che", "alla fine alla fine", "di di")
        testo = re.sub(r'\b(\w+)\s+\1\b', r'\1', testo)
        # Fix "una cambiamento" → "un cambiamento" (articolo femminile + parola maschile)
        testo = re.sub(r'\buna\s+(cambiamento|modello|schema|modo|fatto|passo|momento|passaggio|traguardo)\b', r'un \1', testo)
        # Fix "un novità" → "una novità" (articolo maschile + parola femminile)
        testo = re.sub(r'\bun\s+(novità)\b', r'una \1', testo)
        # Fix preposizioni articolate: "di il" → "del", "su il" → "sul", etc.
        testo = re.sub(r'\bdi il\b', 'del', testo)
        testo = re.sub(r'\bdi la\b', 'della', testo)
        testo = re.sub(r'\bdi le\b', 'delle', testo)
        testo = re.sub(r'\bdi i\b', 'dei', testo)
        testo = re.sub(r'\bdi gli\b', 'degli', testo)
        testo = re.sub(r'\bsu il\b', 'sul', testo)
        testo = re.sub(r'\bsu la\b', 'sulla', testo)
        testo = re.sub(r'\bsu le\b', 'sulle', testo)
        testo = re.sub(r'\bsu i\b', 'sui', testo)
        testo = re.sub(r'\bsu gli\b', 'sugli', testo)
        testo = re.sub(r'\ba il\b', 'al', testo)
        testo = re.sub(r'\ba la\b', 'alla', testo)
        testo = re.sub(r'\ba le\b', 'alle', testo)
        testo = re.sub(r'\ba i\b', 'ai', testo)
        testo = re.sub(r'\bda il\b', 'dal', testo)
        testo = re.sub(r'\bda la\b', 'dalla', testo)
        testo = re.sub(r'\bin il\b', 'nel', testo)
        testo = re.sub(r'\bin la\b', 'nella', testo)
        testo = re.sub(r'\bin le\b', 'nelle', testo)
        testo = re.sub(r'\bin i\b', 'nei', testo)
        # Fix case-insensitive versions at start of sentence
        testo = re.sub(r'\bDi il\b', 'Del', testo)
        testo = re.sub(r'\bSu il\b', 'Sul', testo)
        testo = re.sub(r'\bA il\b', 'Al', testo)
        testo = re.sub(r'\bDa il\b', 'Dal', testo)
        testo = re.sub(r'\bIn il\b', 'Nel', testo)

        # Capitalizzazione dopo punto fermo (fix per sostituzioni che abbassano la prima lettera)
        testo = re.sub(r'([.!?]\s+)([a-zà-ÿ])', lambda m: m.group(1) + m.group(2).upper(), testo)
        # Capitalizzazione a inizio testo
        if testo and testo[0].islower():
            testo = testo[0].upper() + testo[1:]

        # Preserva i paragrafi: normalizza solo gli spazi orizzontali, non i newline
        # Prima preserva i paragrafi (doppio newline)
        testo = re.sub(r'\n\s*\n', '\n\n', testo)
        # Rimuovi spazi multipli (solo orizzontali, non newline)
        testo = re.sub(r'[^\S\n]+', ' ', testo)
        # Rimuovi spazi prima della punteggiatura
        testo = re.sub(r'\s+([.!?,;:])', r'\1', testo)
        # Assicura spazio dopo punteggiatura (ma non dopo punto seguito da newline)
        testo = re.sub(r'([.!?,;:])([A-Za-zÀ-ÿ])', r'\1 \2', testo)
        # Rimuovi virgole doppie
        testo = re.sub(r',\s*,', ',', testo)
        # Normalizza trattini
        testo = re.sub(r'\s*—\s*', ' — ', testo)
        testo = re.sub(r'—\s*—', '—', testo)
        # Ripristina a capo per i titoli
        testo = re.sub(r'\s*(#{1,6})\s*', r'\n\n\1 ', testo)

        # ═══════════════════════════════════════════════════════════════
        # FASE 9: RIPRISTINO CITAZIONI BIBLIOGRAFICHE
        # ═══════════════════════════════════════════════════════════════
        testo = self._restore_citations(testo, mappa_citazioni)

        return testo.strip()


# ═══════════════════════════════════════════════════════════════════════════
# FUNZIONE DI INTERFACCIA PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════

_processor_instance: Optional[AntiAIProcessor] = None


def get_processor() -> AntiAIProcessor:
    """Restituisce l'istanza singleton del processore anti-AI."""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = AntiAIProcessor()
    return _processor_instance


def humanize_text_post_processing(testo: str) -> str:
    """
    Funzione principale da chiamare per il post-processing anti-AI.

    Questa funzione viene chiamata DOPO aver ottenuto la risposta da Claude
    per applicare trasformazioni algoritmiche che rendono il testo
    completamente non rilevabile dai detector AI.

    Args:
        testo: Il testo generato da Claude da processare

    Returns:
        Il testo trasformato, anti-AI

    Example:
        >>> from anti_ai_processor import humanize_text_post_processing
        >>> testo_ai = "Il testo generato da Claude..."
        >>> testo_umano = humanize_text_post_processing(testo_ai)
    """
    processor = get_processor()
    return processor.process(testo)


def analizza_testo(testo: str) -> Dict:
    """
    Analizza un testo e restituisce metriche sulla sua "umanità".

    Utile per debug e per verificare l'efficacia del processing.

    Args:
        testo: Il testo da analizzare

    Returns:
        Dizionario con metriche: pattern AI, elementi umani, burstiness, frasi AI
    """
    processor = get_processor()

    frasi_ai = processor.conta_frasi_ai(testo)

    return {
        'pattern_ai': processor.analizza_pattern_ai(testo),
        'frasi_ai_alta_frequenza': frasi_ai,
        'frasi_ai_totale': sum(frasi_ai.values()),
        'elementi_umani': processor.conta_elementi_umani(testo),
        'burstiness': processor.calcola_burstiness(testo),
        'num_parole': len(testo.split()),
        'num_frasi': len(re.split(r'[.!?]+', testo))
    }


# ═══════════════════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    testo_test = """
    Cinquecento. È il numero di ispettori del lavoro che mancano all'appello.

    ## Il problema degli organici

    Funzionerà? Difficile dirlo.

    Sulla carta sembra un passo avanti. Ma nella pratica le cose sono più complicate.

    C'è il problema degli organici. C'è anche la questione dei fondi. Poi c'è la burocrazia.

    Chi conosce il settore sa che le cose non cambieranno. Chi lavora nel campo sa che i problemi sono strutturali.

    Questo non significa che sia inutile. Significa che servirà tempo.

    I sindacati dicono che serve di più. Gli imprenditori dicono che costa troppo. Le associazioni dicono che è un inizio.

    ---

    ## Conclusioni

    In conclusione, la situazione è fondamentale per comprendere le dinamiche del settore.
    Pertanto, è importante notare che rappresenta una svolta significativa.
    Inoltre, va sottolineato che emerge un quadro complesso.
    Questo significa che nel corso degli ultimi anni la situazione è cambiata in modo significativo.
    È evidente che gioca un ruolo fondamentale nel contesto attuale.
    In questo contesto, è possibile notare che i fattori contribuiscono a determinare il risultato.

    Vedremo.
    """

    print("=" * 70)
    print("TEST ANTI-AI PROCESSOR")
    print("=" * 70)

    print("\n--- ANALISI PRIMA DEL PROCESSING ---\n")
    analisi_prima = analizza_testo(testo_test)
    print(f"Pattern AI rilevati: {sum(analisi_prima['pattern_ai'].values())}")
    for k, v in analisi_prima['pattern_ai'].items():
        if v > 0:
            print(f"  - {k}: {v}")
    print(f"\nFrasi AI ad alta frequenza: {analisi_prima['frasi_ai_totale']}")
    if analisi_prima['frasi_ai_alta_frequenza']:
        for frase, count in list(analisi_prima['frasi_ai_alta_frequenza'].items())[:10]:
            print(f"  - \"{frase}\": {count}")
    print(f"\nElementi umani: {analisi_prima['elementi_umani']}")
    print(f"Burstiness: {analisi_prima['burstiness']:.3f}")
    print(f"Parole: {analisi_prima['num_parole']}")

    print("\n--- PROCESSING ---\n")
    testo_processato = humanize_text_post_processing(testo_test)

    print("--- ANALISI DOPO IL PROCESSING ---\n")
    analisi_dopo = analizza_testo(testo_processato)
    print(f"Pattern AI rilevati: {sum(analisi_dopo['pattern_ai'].values())}")
    for k, v in analisi_dopo['pattern_ai'].items():
        if v > 0:
            print(f"  - {k}: {v}")
    print(f"\nFrasi AI ad alta frequenza: {analisi_dopo['frasi_ai_totale']}")
    if analisi_dopo['frasi_ai_alta_frequenza']:
        for frase, count in list(analisi_dopo['frasi_ai_alta_frequenza'].items())[:10]:
            print(f"  - \"{frase}\": {count}")
    print(f"\nElementi umani: {analisi_dopo['elementi_umani']}")
    print(f"Burstiness: {analisi_dopo['burstiness']:.3f}")
    print(f"Parole: {analisi_dopo['num_parole']}")

    # Calcola riduzione
    riduzione_pattern = sum(analisi_prima['pattern_ai'].values()) - sum(analisi_dopo['pattern_ai'].values())
    riduzione_frasi = analisi_prima['frasi_ai_totale'] - analisi_dopo['frasi_ai_totale']
    print(f"\n--- RIEPILOGO ---")
    print(f"Pattern AI eliminati: {riduzione_pattern}")
    print(f"Frasi AI eliminate: {riduzione_frasi}")
    print(f"Frasi AI rimanenti: {analisi_dopo['frasi_ai_totale']} (obiettivo: 0)")

    print("\n" + "=" * 70)
    print("TESTO PROCESSATO")
    print("=" * 70 + "\n")
    print(testo_processato)
