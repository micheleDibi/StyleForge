"""
Prompt per la generazione di tesi/relazioni.

Questo modulo contiene i prompt dettagliati per ogni fase
della generazione di tesi utilizzando OpenAI o1/o3.
"""

from typing import Dict, Any, List, Optional

import config


def _get_citation_instructions(citation_style: str = "footnotes") -> str:
    """Restituisce le istruzioni sulle citazioni in base allo stile scelto.

    Tutti i formati seguono lo stile APA italiano:
       Cognome, N. (Anno). *Titolo dell'opera*. Città: Casa editrice.
    Il titolo va in corsivo (Markdown: *titolo*) con la prima lettera maiuscola.
    """
    if citation_style == "bibliography":
        return """CITAZIONI BIBLIOGRAFICHE — SOLO FONTI REALI (stile APA italiano):
   - Inserisci almeno 3-5 citazioni bibliografiche nel testo usando il formato [x]
     dove x è un numero progressivo (es. [1], [2], [3], ecc.)
   - ⚠️ REQUISITO CRITICO: Cita ESCLUSIVAMENTE opere REALI e VERIFICABILI
   - Ogni citazione [x] DEVE riferirsi a un'opera che ESISTE REALMENTE:
     • Libri pubblicati da autori reali con ISBN verificabile
     • Articoli pubblicati su riviste scientifiche reali
     • Report di organizzazioni reali (OMS, ISTAT, UE, ecc.)
     • Pubblicazioni accademiche reali e verificabili
   - ⚠️ NON INVENTARE MAI fonti, autori, titoli o pubblicazioni
   - ⚠️ Se non sei sicuro che una fonte esista realmente, NON citarla
   - Usa le citazioni quando menzioni studi, ricerche, dati, teorie o opinioni di autori
   - Esempio inline: "Secondo Kahneman [1], i bias cognitivi influenzano..."
   - I numeri devono essere progressivi e coerenti all'interno della tesi
   - Quando citi, includi nel testo abbastanza contesto per identificare la fonte
     (es. nome autore, anno, titolo abbreviato) così la bibliografia sarà accurata
   - La voce bibliografica corrispondente seguirà il formato APA italiano:
     LIBRO:    Cognome, N. (Anno). *Titolo dell'opera*. Città: Casa editrice.
     ARTICOLO: Cognome, N. (Anno). Titolo articolo. *Nome Rivista*, vol(num), pp-pp.
     REPORT:   Organizzazione. (Anno). *Titolo report*. Città: Editore."""
    else:
        return """NOTE A PIÈ DI PAGINA — SOLO FONTI REALI (stile APA italiano):
   - Inserisci note bibliografiche nel testo usando il formato {{nota: riferimento completo}}
   - PRIMA CITAZIONE di un libro: {{nota: Cognome, N. (Anno). *Titolo dell'opera*. Città: Casa editrice. p.XX}}
   - PRIMA CITAZIONE di un articolo: {{nota: Cognome, N. (Anno). Titolo articolo. *Nome Rivista*, vol(num), pp.XX-XX}}
   - PRIMA CITAZIONE di un report: {{nota: Organizzazione. (Anno). *Titolo report*. Città: Editore. p.XX}}
   - STESSA OPERA, STESSA PAGINA della nota immediatamente precedente: {{nota: Ibidem.}}
   - STESSA OPERA, PAGINA DIVERSA della nota immediatamente precedente: {{nota: Ivi. p.XX}}
   - OPERA GIÀ CITATA IN PRECEDENZA (non immediatamente): {{nota: Op.cit. Cognome, Anno, p.XX}}
   - ⚠️ FORMATO APA OBBLIGATORIO: Cognome dell'autore, virgola, iniziale del nome puntata,
     anno tra parentesi, punto, *Titolo in corsivo* con prima lettera maiuscola, punto,
     città di pubblicazione, due punti, casa editrice, punto, eventuale numero di pagina.
   - ⚠️ Il titolo dell'opera (libro/report) va SEMPRE in corsivo (Markdown: *titolo*).
     Per gli articoli su rivista, il corsivo va sul *Nome Rivista*, NON sul titolo dell'articolo.
   - ⚠️ Cita ESCLUSIVAMENTE opere REALI e VERIFICABILI
   - ⚠️ NON INVENTARE MAI fonti, autori, titoli o pubblicazioni
   - Inserisci almeno 3-5 note per sezione
   - Esempio nel testo: "L'inclusione scolastica è un tema di prim'ordine{{nota: Bonura, A. (2021). *Legislazione e innovazioni normative*. Palermo: USR Sicilia. p.15}} e il numero degli alunni con BES aumenta{{nota: Ibidem.}}" """


def _get_no_citation_instruction(citation_style: str = "footnotes") -> str:
    """Istruzione per non inserire citazioni (introduzione/conclusione)."""
    if citation_style == "bibliography":
        return "NON inserire citazioni bibliografiche [x]"
    else:
        return "NON inserire note bibliografiche {{nota:...}}"


def _get_assets_instructions(citation_style: str = "footnotes") -> str:
    """
    Istruzioni per gli elementi visivi (tabelle, grafici, HINT) nel contenuto
    di sezione. La sintassi è quella riconosciuta da thesis_assets.parse_segments.
    Ritorna stringa vuota se THESIS_ASSETS_ENABLED è False.
    """
    if not getattr(config, 'THESIS_ASSETS_ENABLED', True):
        return ""
    citation_ban = "citazioni [x]" if citation_style == "bibliography" else "note {{nota:...}}"
    if getattr(config, 'THESIS_CHARTS_ENABLED', True):
        chart_block = '''   GRAFICO — SOLO con dati numerici CONCRETI e REALI presi dalla base di
   conoscenza (fonti, allegati, paper):
   ⚠️ NON INVENTARE MAI numeri, percentuali o serie storiche. Se nelle fonti
   non ci sono dati numerici concreti, NIENTE grafico: usa un HINT.
   [GRAFICO: <didascalia accademica descrittiva>]
   {"type": "bar|line|pie|scatter", "x_label": "...", "y_label": "...",
    "labels": ["..."], "series": [{"name": "...", "values": [numeri]}],
    "source": "<fonte reale dei dati>"}
   [/GRAFICO]
   - Un solo oggetto JSON tra i marcatori. Il campo "source" è OBBLIGATORIO
     e deve indicare la fonte reale da cui provengono i dati.'''
    else:
        chart_block = '''   GRAFICI: non generarli mai direttamente. Se un grafico sarebbe utile in un
   punto, inserisci un HINT che descriva quale grafico inserire e con quali dati.'''
    return f"""8. ELEMENTI VISIVI — TABELLE, GRAFICI, IMMAGINI (solo se DAVVERO utili):

   QUANDO USARLI (e quando NO):
   - MAI forzare un elemento visivo: nella maggior parte delle sezioni non
     serve nulla, e va benissimo così. Massimo 1-2 elementi per sezione.
   - TABELLA: solo per confronti strutturati, quadri sinottici o dati che in
     prosa risulterebbero pesanti da seguire.
   - GRAFICO: solo alle condizioni indicate sotto.
   - IMMAGINI, FOTO, SCHEMI che non puoi produrre: inserisci un HINT (vedi
     sotto), MAI descrizioni finte di immagini inesistenti.

   TABELLA — sintassi obbligatoria (ECCEZIONE ESPLICITA alla regola "niente
   elenchi/markdown": DENTRO i marcatori [TABELLA]...[/TABELLA] le righe
   | ... | sono AMMESSE e OBBLIGATORIE):
   [TABELLA: <didascalia accademica, eventualmente con la fonte>]
   | Intestazione 1 | Intestazione 2 |
   | valore | valore |
   Fonte: <fonte dei dati>
   (la riga "Fonte:" è opzionale)
   [/TABELLA]
   - La prima riga | ... | è l'intestazione. Celle brevi (max ~12 parole).
   - NIENTE {citation_ban} dentro le celle: la fonte va nella didascalia o
     nella riga "Fonte: ...".

{chart_block}

   HINT — segnaposto BEN VISIBILE per un elemento che NON puoi generare
   (fotografie, schemi, diagrammi, grafici senza dati). Riga isolata, tra due
   righe vuote:
   HINT: "<descrizione precisa di cosa inserire, perché è utile in quel punto, e dove l'autore può reperirlo>"

   REGOLE COMUNI:
   - Marcatori SEMPRE su righe isolate, con una riga vuota prima e dopo.
   - NON numerare tu tabelle e figure ("Tabella 1", "Figura 2.1"): la
     numerazione e le didascalie numerate vengono aggiunte automaticamente.
   - Didascalie professionali e descrittive, da tesi di laurea.
   - Il testo attorno deve introdurre e commentare l'elemento (es. "come
     mostra la tabella seguente, ..."), mai lasciarlo orfano."""


def build_chapters_prompt(thesis_data: Dict[str, Any], attachments_context: str = "") -> str:
    """
    Costruisce il prompt per la FASE 1: Generazione titoli capitoli.

    Args:
        thesis_data: Dizionario con tutti i parametri della tesi
        attachments_context: Contesto estratto dagli allegati

    Returns:
        Prompt completo per la generazione dei capitoli
    """
    key_topics_str = ", ".join(thesis_data.get('key_topics', [])) if thesis_data.get('key_topics') else "Non specificati"

    return f"""
═══════════════════════════════════════════════════════════════════════════════
GENERAZIONE INDICE TESI/RELAZIONE - FASE 1: CAPITOLI
═══════════════════════════════════════════════════════════════════════════════

Sei un esperto nella strutturazione di documenti accademici e professionali.
Il tuo compito è generare l'INDICE (titoli dei capitoli) per una tesi/relazione.

═══════════════════════════════════════════════════════════════════════════════
PARAMETRI DELLA TESI
═══════════════════════════════════════════════════════════════════════════════

TITOLO: {thesis_data.get('title', 'Non specificato')}
DESCRIZIONE: {thesis_data.get('description', 'Non specificata')}
ARGOMENTI CHIAVE: {key_topics_str}

═══════════════════════════════════════════════════════════════════════════════
PARAMETRI DI GENERAZIONE
═══════════════════════════════════════════════════════════════════════════════

STILE DI SCRITTURA: {thesis_data.get('writing_style_name', 'Non specificato')}
  → Indicazione: {thesis_data.get('writing_style_hint', '')}

LIVELLO DI PROFONDITÀ: {thesis_data.get('content_depth_name', 'Intermedio')}
NUMERO CAPITOLI RICHIESTI: {thesis_data.get('num_chapters', 5)}
SEZIONI PER CAPITOLO: {thesis_data.get('sections_per_chapter', 3)}
PAROLE PER SEZIONE: ~{thesis_data.get('words_per_section', 5000)}

═══════════════════════════════════════════════════════════════════════════════
CARATTERISTICHE DEL PUBBLICO
═══════════════════════════════════════════════════════════════════════════════

LIVELLO DI CONOSCENZA: {thesis_data.get('knowledge_level_name', 'Intermedio')}
  → Indicazione: {thesis_data.get('knowledge_level_hint', '')}

DIMENSIONE PUBBLICO: Commissione di laurea
SETTORE/INDUSTRIA: {thesis_data.get('industry_name', 'Generale')}
DESTINATARI: {thesis_data.get('target_audience_name', 'Pubblico Generale')}
  → Indicazione: {thesis_data.get('target_audience_hint', '')}

═══════════════════════════════════════════════════════════════════════════════
BASE DI CONOSCENZA (LLM WIKI)
═══════════════════════════════════════════════════════════════════════════════
{attachments_context if attachments_context else "Nessuna fonte caricata. Procedi con la struttura di tesi piu' standard per il tema dato."}

═══════════════════════════════════════════════════════════════════════════════
ISTRUZIONI
═══════════════════════════════════════════════════════════════════════════════

1. Genera esattamente {thesis_data.get('num_chapters', 5)} titoli di capitoli

2. I titoli devono essere:
   - INFORMATIVI e SPECIFICI (evita titoli generici come "Introduzione", "Conclusioni",
     "Panoramica" - se necessari, rendili specifici al tema)
   - COERENTI con lo stile di scrittura richiesto
   - In PROGRESSIONE LOGICA (dal generale al particolare, o dal problema alla soluzione,
     o dalla teoria alla pratica - scegli la struttura più appropriata)
   - ADATTI al pubblico target e al loro livello di conoscenza

3. Ogni capitolo deve avere:
   - Un titolo chiaro e descrittivo
   - Una breve descrizione (1-2 frasi) di cosa tratterà

4. Se sono stati forniti allegati, integra i temi rilevanti nella struttura

5. La struttura deve essere bilanciata: ogni capitolo dovrebbe avere
   importanza e dimensione simile

═══════════════════════════════════════════════════════════════════════════════
OUTPUT RICHIESTO
═══════════════════════════════════════════════════════════════════════════════

Restituisci SOLO un JSON valido con questa struttura esatta:
{{
  "chapters": [
    {{
      "index": 1,
      "title": "Titolo del primo capitolo",
      "brief_description": "Breve descrizione di cosa tratterà questo capitolo (1-2 frasi)"
    }},
    {{
      "index": 2,
      "title": "Titolo del secondo capitolo",
      "brief_description": "Breve descrizione di cosa tratterà questo capitolo (1-2 frasi)"
    }}
  ]
}}

IMPORTANTE:
- Restituisci SOLO il JSON, senza testo aggiuntivo
- Non usare markdown code blocks
- Assicurati che il JSON sia valido e parsabile
"""


def build_sections_prompt(
    thesis_data: Dict[str, Any],
    chapters: List[Dict[str, Any]],
    attachments_context: str = ""
) -> str:
    """
    Costruisce il prompt per la FASE 2: Generazione titoli sezioni.

    Args:
        thesis_data: Dizionario con i parametri della tesi
        chapters: Lista dei capitoli confermati
        attachments_context: Contesto estratto dagli allegati

    Returns:
        Prompt completo per la generazione delle sezioni
    """
    chapters_text = "\n".join([
        f"  Capitolo {c.get('index', i+1)}: {c.get('title', 'Senza titolo')}\n"
        f"    → {c.get('brief_description', 'Nessuna descrizione')}"
        for i, c in enumerate(chapters)
    ])

    return f"""
═══════════════════════════════════════════════════════════════════════════════
GENERAZIONE INDICE TESI/RELAZIONE - FASE 2: SEZIONI
═══════════════════════════════════════════════════════════════════════════════

Sei un esperto nella strutturazione di documenti accademici e professionali.
Il tuo compito è generare i TITOLI DELLE SEZIONI per ogni capitolo della tesi.

═══════════════════════════════════════════════════════════════════════════════
CONTESTO DELLA TESI
═══════════════════════════════════════════════════════════════════════════════

TITOLO: {thesis_data.get('title', 'Non specificato')}
DESCRIZIONE: {thesis_data.get('description', 'Non specificata')}
STILE: {thesis_data.get('writing_style_name', 'Non specificato')}
LIVELLO PROFONDITÀ: {thesis_data.get('content_depth_name', 'Intermedio')}

PUBBLICO: {thesis_data.get('target_audience_name', 'Generale')}
  (Livello: {thesis_data.get('knowledge_level_name', 'Intermedio')})

SEZIONI PER CAPITOLO: {thesis_data.get('sections_per_chapter', 3)}
PAROLE PER SEZIONE: ~{thesis_data.get('words_per_section', 5000)}

═══════════════════════════════════════════════════════════════════════════════
CAPITOLI CONFERMATI
═══════════════════════════════════════════════════════════════════════════════

{chapters_text}

═══════════════════════════════════════════════════════════════════════════════
BASE DI CONOSCENZA (LLM WIKI)
═══════════════════════════════════════════════════════════════════════════════
{attachments_context if attachments_context else "Nessuna fonte caricata. Procedi con la struttura di tesi piu' standard per il tema dato."}

═══════════════════════════════════════════════════════════════════════════════
ISTRUZIONI
═══════════════════════════════════════════════════════════════════════════════

Per OGNI capitolo, genera esattamente {thesis_data.get('sections_per_chapter', 3)} sezioni.

Le sezioni devono:
1. COPRIRE l'argomento del capitolo in modo completo e esaustivo
2. Avere una PROGRESSIONE LOGICA interna (dalla teoria alla pratica,
   dal generale al particolare, ecc.)
3. Essere sufficientemente AMPIE da giustificare ~{thesis_data.get('words_per_section', 5000)} parole
4. NON SOVRAPPORSI tra loro - ogni sezione deve coprire aspetti distinti
5. Essere SPECIFICHE e descrittive (evita titoli vaghi)
6. Avere 2-4 punti chiave che verranno sviluppati nella sezione

═══════════════════════════════════════════════════════════════════════════════
OUTPUT RICHIESTO
═══════════════════════════════════════════════════════════════════════════════

Restituisci SOLO un JSON valido con questa struttura esatta:
{{
  "chapters": [
    {{
      "chapter_index": 1,
      "chapter_title": "Titolo del primo capitolo (esattamente come fornito)",
      "sections": [
        {{
          "index": 1,
          "title": "Titolo della prima sezione",
          "key_points": [
            "Primo punto chiave da sviluppare",
            "Secondo punto chiave da sviluppare",
            "Terzo punto chiave da sviluppare"
          ]
        }},
        {{
          "index": 2,
          "title": "Titolo della seconda sezione",
          "key_points": [
            "Primo punto chiave",
            "Secondo punto chiave",
            "Terzo punto chiave"
          ]
        }}
      ]
    }}
  ]
}}

IMPORTANTE:
- Restituisci SOLO il JSON, senza testo aggiuntivo
- Mantieni i titoli dei capitoli ESATTAMENTE come forniti
- Ogni sezione deve avere 2-4 key_points
- Assicurati che il JSON sia valido e parsabile
"""


def build_section_content_prompt(
    thesis_data: Dict[str, Any],
    chapter: Dict[str, Any],
    section: Dict[str, Any],
    previous_sections_summary: str = "",
    attachments_context: str = "",
    author_style_context: str = "",
    human_style_examples: str = ""
) -> str:
    """
    Costruisce il prompt per la FASE 3: Generazione contenuto sezione.

    Args:
        thesis_data: Parametri della tesi
        chapter: Dati del capitolo corrente
        section: Dati della sezione da generare
        previous_sections_summary: Riassunto delle sezioni precedenti
        attachments_context: Contesto dagli allegati
        author_style_context: Contesto dello stile autore (se addestrato)

    Returns:
        Prompt completo per la generazione del contenuto
    """
    key_points = section.get('key_points', [])
    key_points_text = "\n".join([f"• {point}" for point in key_points]) if key_points else "Non specificati"

    assets_block = _get_assets_instructions(thesis_data.get('citation_style', 'footnotes'))
    hint_exception = (
        ' — UNICA ECCEZIONE ammessa: la riga HINT: "..." descritta al punto 8'
        if assets_block else ""
    )

    return f"""
═══════════════════════════════════════════════════════════════════════════════
GENERAZIONE CONTENUTO SEZIONE
═══════════════════════════════════════════════════════════════════════════════

TESI: "{thesis_data.get('title', 'Non specificato')}"
CAPITOLO {chapter.get('chapter_index', '?')}: {chapter.get('chapter_title', 'Non specificato')}
SEZIONE {section.get('index', '?')}: {section.get('title', 'Non specificato')}

═══════════════════════════════════════════════════════════════════════════════
PARAMETRI DI SCRITTURA
═══════════════════════════════════════════════════════════════════════════════

STILE: {thesis_data.get('writing_style_name', 'Non specificato')}
  → {thesis_data.get('writing_style_hint', '')}

LIVELLO PROFONDITÀ: {thesis_data.get('content_depth_name', 'Intermedio')}
PAROLE TARGET: ~{thesis_data.get('words_per_section', 5000)} parole

═══════════════════════════════════════════════════════════════════════════════
PUBBLICO TARGET
═══════════════════════════════════════════════════════════════════════════════

DESTINATARI: {thesis_data.get('target_audience_name', 'Pubblico Generale')}
  → {thesis_data.get('target_audience_hint', '')}

LIVELLO CONOSCENZA: {thesis_data.get('knowledge_level_name', 'Intermedio')}
  → {thesis_data.get('knowledge_level_hint', '')}

SETTORE: {thesis_data.get('industry_name', 'Generale')}

═══════════════════════════════════════════════════════════════════════════════
PUNTI CHIAVE DA SVILUPPARE
═══════════════════════════════════════════════════════════════════════════════
{key_points_text}

═══════════════════════════════════════════════════════════════════════════════
CONTESTO PRECEDENTE
═══════════════════════════════════════════════════════════════════════════════
{previous_sections_summary if previous_sections_summary else "Questa è la prima sezione della tesi."}

═══════════════════════════════════════════════════════════════════════════════
BASE DI CONOSCENZA (LLM WIKI)
═══════════════════════════════════════════════════════════════════════════════
{attachments_context if attachments_context else "Nessuna fonte caricata. Genera basandoti sulla conoscenza del modello."}

═══════════════════════════════════════════════════════════════════════════════
STILE DELL'AUTORE
═══════════════════════════════════════════════════════════════════════════════
{author_style_context if author_style_context else "Nessuno stile specifico addestrato - usa lo stile richiesto nei parametri."}
{(
'''
═══════════════════════════════════════════════════════════════════════════════
ESEMPI DI STILE UMANO (imita RITMO e LESSICO, NON i contenuti)
═══════════════════════════════════════════════════════════════════════════════
I brani qui sotto sono prosa accademica UMANA reale. Studiane il ritmo irregolare,
la varietà delle costruzioni e il lessico, e scrivi con uno stile simile.
NON copiare frasi né contenuti: prendi solo lo STILE (le Similitudini devono restare basse).

''' + human_style_examples) if human_style_examples else ""}

═══════════════════════════════════════════════════════════════════════════════
ISTRUZIONI DI SCRITTURA
═══════════════════════════════════════════════════════════════════════════════

1. REQUISITO CRITICO — LUNGHEZZA MINIMA:
   ⚠️ Devi scrivere ALMENO {thesis_data.get('words_per_section', 5000)} parole per questa sezione
   ⚠️ NON scrivere meno di {thesis_data.get('words_per_section', 5000)} parole — è un requisito OBBLIGATORIO
   ⚠️ Se il testo ti sembra lungo, VA BENE — deve essere lungo!
   ⚠️ Sviluppa OGNI punto in profondità con esempi, analisi, dati e riflessioni
   ⚠️ Ogni paragrafo deve avere almeno 150-200 parole
   ⚠️ NON riassumere, NON sintetizzare, NON abbreviare

2. STRUTTURA il contenuto in modo chiaro:
   - Introduzione al tema della sezione (1-2 paragrafi)
   - Sviluppo completo di ogni punto chiave
   - Esempi concreti e casi pratici dove appropriato
   - Eventuali riferimenti a fonti/studi (se rilevante per lo stile)
   - Transizione verso la sezione successiva (se non è l'ultima)

3. MANTIENI COERENZA con le sezioni precedenti:
   - Non ripetere concetti già trattati
   - Fai riferimento a quanto già discusso quando rilevante
   - Usa terminologia consistente

4. ADATTA il linguaggio al pubblico target:
   - Livello di tecnicità appropriato
   - Spiegazioni adeguate al livello di conoscenza
   - Esempi pertinenti al settore

5. Se sono stati forniti allegati:
   - Integra informazioni rilevanti
   - Fai riferimento ai materiali dove appropriato
   - Non copiare verbatim, rielabora

6. {_get_citation_instructions(thesis_data.get('citation_style', 'footnotes'))}

7. SCRIVI COME UNO STUDENTE UNIVERSITARIO REALE:
   Il testo DEVE sembrare scritto da uno studente preparato, NON da un'AI.
   Questo e' il requisito piu' importante. Segui TUTTE queste regole:

   ═══ VOCABOLARIO ═══
   - Usa parole normali: "usa" non "utilizza", "mostra" non "evidenzia",
     "aiuta" non "contribuisce a", "serve" non "risulta necessario",
     "molti" non "numerosi", "pochi" non "limitati", "grande" non "significativo"
   - PAROLE VIETATE (non usarle MAI): fondamentale, significativo, cruciale,
     rilevante, sottolineare, evidenziare, emergere, inoltre, pertanto, dunque,
     tuttavia, rappresenta, costituisce, paradigma, panorama, scenario,
     nell'ambito di, in questo contesto, in tal senso, in ultima analisi,
     a tal proposito, e' opportuno, occorre, risulta, si configura,
     assume un ruolo, riveste importanza, gioca un ruolo, e' doveroso,
     si evince, si denota, e' possibile affermare, appare evidente
   - Preferisci costruzioni dirette con soggetto-verbo-oggetto
   - Usa "questo", "quello", "qui" per riferimenti, non "suddetto", "il quale"

   ═══ STRUTTURA DELLE FRASI ═══
   - Lunghezze IRREGOLARI: alterna frasi da 6-10 parole con frasi da 25-40 parole
   - Alcune frasi siano deliberatamente piu' semplici del necessario
   - NON iniziare mai due frasi consecutive con la stessa struttura grammaticale
   - NON iniziare piu' di 2 frasi per paragrafo con articoli (Il, La, Lo, I, Le, Gli)
   - Inizia almeno 3 frasi per sezione con congiunzioni: "E", "Ma", "Pero'", "Anche"
   - Includi almeno 2 frasi per sezione che iniziano con un complemento spostato:
     "In Sicilia, ...", "Dopo il 2015, ...", "Con queste premesse, ..."
   - Spezza frasi lunghe: usa il punto e virgola o ricomincia con "Questo perche'..."

   ═══ STRUTTURA DEI PARAGRAFI ═══
   - Paragrafi MOLTO diversi tra loro: alcuni da 3 frasi, altri da 8-10
   - NON chiudere paragrafi con frasi riassuntive o a effetto
   - NON aprire paragrafi con "Per quanto riguarda", "In merito a", "Relativamente a"
   - A volte chiudi un paragrafo a meta' di un ragionamento e continua nel successivo
   - Lascia qualche passaggio logico implicito (non spiegare ogni collegamento)

   ═══ PATTERN DA EVITARE ASSOLUTAMENTE ═══
   - MAI liste di 3 elementi simmetrici ("X, Y e Z")
   - MAI coppie antitetiche ("da un lato... dall'altro", "non solo... ma anche")
   - MAI frasi del tipo "E' importante notare/sottolineare/evidenziare che..."
   - MAI domande retoriche seguite dalla risposta
   - MAI aprire con "In un contesto/mondo/scenario in cui..."
   - MAI chiudere sezioni con "In conclusione/In sintesi/Per concludere"
   - MAI usare piu' di 2 virgole nella stessa frase (spezza in frasi diverse)
   - MAI ripetere la stessa struttura di transizione tra paragrafi
   - MAI serie di 4 elementi paralleli né formule tipo "X senza Y, Z senza W"
     o "X, Y, Z e W" usate come schema ricorrente
   - MAI elenchi con lettere o numeri (a), b), c) — oppure 1., 2., 3.) per
     enumerare concetti: scrivi in prosa discorsiva, sciogliendo gli elenchi
   - MAI anafore: due o più frasi vicine che iniziano con le stesse parole
     ("Una scuola che... Una scuola che...", "Non bastano..., non bastano...")
   - MAI la formula "non X; è Y" oppure "non si tratta di X, ma di Y" come schema
   - MAI chiudere la sezione con una frase a effetto, una massima o un aforisma

   ═══ NATURALEZZA ═══
   - Ogni tanto una frase puo' essere leggermente meno precisa del necessario
   - Usa occasionalmente espressioni come "per certi versi", "in qualche modo"
   - Permetti qualche ripetizione di vocabolo a distanza (gli umani lo fanno)
   - Non tutte le affermazioni hanno bisogno di una fonte o giustificazione
   - Qualche volta fai un'osservazione personale breve senza citazioni
   - Varia il ritmo: dopo 2-3 paragrafi densi, inserisci uno piu' leggero

{assets_block}

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Scrivi SOLO il contenuto della sezione.

IMPORTANTE:
- NON includere il titolo della sezione (verrà aggiunto separatamente)
- NON includere meta-commenti o note per l'autore
- NON usare placeholder o [inserire qui]{hint_exception}
- Scrivi il contenuto completo e definitivo
- Il testo deve essere pronto per la pubblicazione
- RICORDA: ALMENO {thesis_data.get('words_per_section', 5000)} parole! Questo è NON negoziabile.
"""


def build_section_summary_prompt(section_content: str, max_words: int = 150) -> str:
    """
    Costruisce un prompt per riassumere una sezione.

    Usato per creare il contesto per le sezioni successive.

    Args:
        section_content: Contenuto della sezione da riassumere
        max_words: Numero massimo di parole per il riassunto

    Returns:
        Prompt per la generazione del riassunto
    """
    return f"""
Riassumi il seguente testo in massimo {max_words} parole, mantenendo i concetti chiave:

{section_content}

Rispondi SOLO con il riassunto, senza introduzioni o commenti.
"""


def build_thesis_title_enhancement_prompt(
    original_title: str,
    thesis_data: Dict[str, Any]
) -> str:
    """
    Prompt per migliorare il titolo della tesi se necessario.

    Args:
        original_title: Titolo originale
        thesis_data: Parametri della tesi

    Returns:
        Prompt per il miglioramento del titolo
    """
    return f"""
Valuta il seguente titolo per una tesi/relazione e, se necessario, suggerisci un miglioramento.

TITOLO ORIGINALE: {original_title}

CONTESTO:
- Stile: {thesis_data.get('writing_style_name', 'Non specificato')}
- Settore: {thesis_data.get('industry_name', 'Generale')}
- Pubblico: {thesis_data.get('target_audience_name', 'Generale')}
- Argomenti chiave: {', '.join(thesis_data.get('key_topics', []))}

Se il titolo è già efficace, rispondi con: {{"keep_original": true, "title": "{original_title}"}}

Se suggerisci un miglioramento, rispondi con:
{{"keep_original": false, "title": "Nuovo titolo migliorato", "reason": "Breve spiegazione"}}

Rispondi SOLO con il JSON, senza altro testo.
"""


def build_introduction_prompt(
    thesis_data: Dict[str, Any],
    chapters_titles: List[str],
    attachments_context: str = "",
    author_style_context: str = ""
) -> str:
    """
    Costruisce il prompt per generare l'Introduzione della tesi.

    Args:
        thesis_data: Parametri della tesi
        chapters_titles: Lista dei titoli dei capitoli
        attachments_context: Contesto dagli allegati
        author_style_context: Contesto dello stile autore

    Returns:
        Prompt completo per la generazione dell'introduzione
    """
    key_topics_str = ", ".join(thesis_data.get('key_topics', [])) if thesis_data.get('key_topics') else "Non specificati"
    chapters_list = "\n".join([f"  {i+1}. {title}" for i, title in enumerate(chapters_titles)])

    return f"""
═══════════════════════════════════════════════════════════════════════════════
GENERAZIONE INTRODUZIONE TESI
═══════════════════════════════════════════════════════════════════════════════

Sei un esperto nella scrittura di documenti accademici e professionali.
Il tuo compito è scrivere l'INTRODUZIONE della tesi.

═══════════════════════════════════════════════════════════════════════════════
PARAMETRI DELLA TESI
═══════════════════════════════════════════════════════════════════════════════

TITOLO: {thesis_data.get('title', 'Non specificato')}
DESCRIZIONE: {thesis_data.get('description', 'Non specificata')}
ARGOMENTI CHIAVE: {key_topics_str}

═══════════════════════════════════════════════════════════════════════════════
PARAMETRI DI SCRITTURA
═══════════════════════════════════════════════════════════════════════════════

STILE: {thesis_data.get('writing_style_name', 'Non specificato')}
  → {thesis_data.get('writing_style_hint', '')}

LIVELLO PROFONDITÀ: {thesis_data.get('content_depth_name', 'Intermedio')}
PAROLE TARGET: ~{thesis_data.get('words_per_section', 5000)} parole

═══════════════════════════════════════════════════════════════════════════════
PUBBLICO TARGET
═══════════════════════════════════════════════════════════════════════════════

DESTINATARI: {thesis_data.get('target_audience_name', 'Pubblico Generale')}
  → {thesis_data.get('target_audience_hint', '')}

LIVELLO CONOSCENZA: {thesis_data.get('knowledge_level_name', 'Intermedio')}
  → {thesis_data.get('knowledge_level_hint', '')}

SETTORE: {thesis_data.get('industry_name', 'Generale')}

═══════════════════════════════════════════════════════════════════════════════
STRUTTURA DEI CAPITOLI DELLA TESI
═══════════════════════════════════════════════════════════════════════════════

{chapters_list}

═══════════════════════════════════════════════════════════════════════════════
BASE DI CONOSCENZA (LLM WIKI)
═══════════════════════════════════════════════════════════════════════════════
{attachments_context if attachments_context else "Nessuna fonte caricata. Genera basandoti sulla conoscenza del modello."}

═══════════════════════════════════════════════════════════════════════════════
STILE DELL'AUTORE
═══════════════════════════════════════════════════════════════════════════════
{author_style_context if author_style_context else "Nessuno stile specifico addestrato - usa lo stile richiesto nei parametri."}

═══════════════════════════════════════════════════════════════════════════════
ISTRUZIONI
═══════════════════════════════════════════════════════════════════════════════

⚠️ REQUISITO CRITICO — LUNGHEZZA: Scrivi ALMENO {thesis_data.get('words_per_section', 5000)} parole.
NON scrivere meno di {thesis_data.get('words_per_section', 5000)} parole — è OBBLIGATORIO.
Sviluppa ogni punto in profondità con analisi, esempi e riflessioni dettagliate.

L'introduzione deve:
1. Presentare il TEMA GENERALE della tesi e il suo contesto
2. Spiegare la RILEVANZA e l'importanza dell'argomento
3. Definire gli OBIETTIVI della tesi
4. Descrivere brevemente la STRUTTURA del lavoro, menzionando cosa verrà trattato
   nei vari capitoli (senza entrare troppo nel dettaglio)
5. Contestualizzare il lavoro nel panorama attuale del settore
6. Essere COINVOLGENTE e motivare il lettore a proseguire

{_get_no_citation_instruction(thesis_data.get('citation_style', 'footnotes'))} nell'introduzione.

SCRIVI COME UNO STUDENTE UNIVERSITARIO REALE:
- Usa parole normali, evita vocabolario pomposo
- PAROLE VIETATE: fondamentale, significativo, cruciale, rilevante, sottolineare,
  evidenziare, emergere, inoltre, pertanto, dunque, tuttavia, rappresenta,
  costituisce, paradigma, panorama, scenario, nell'ambito di, in questo contesto,
  risulta, si configura, appare evidente, e' possibile affermare
- Frasi di lunghezze IRREGOLARI: alterna corte (6-10 parole) e lunghe (25-40)
- NON iniziare mai due frasi consecutive con la stessa struttura
- NON iniziare piu' di 2 frasi per paragrafo con articoli (Il, La, Lo)
- Inizia almeno 3 frasi con congiunzioni: "E", "Ma", "Pero'"
- NON usare strutture simmetriche ("da un lato... dall'altro", "non solo... ma anche")
- MAI liste di 3 o 4 elementi simmetrici ("X, Y e Z"; "X, Y, Z e W") né elenchi a), b), c)
- MAI anafore (frasi vicine che iniziano con le stesse parole) né la formula "non X; è Y"
- NON chiudere paragrafi con frasi a effetto o riassuntive
- Paragrafi di lunghezze MOLTO diverse (da 3 frasi a 10 frasi)
- Qualche passaggio logico puo' restare implicito

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Scrivi SOLO il contenuto dell'introduzione.
NON includere il titolo "Introduzione" (verra' aggiunto separatamente).
NON includere meta-commenti o note.
Il testo deve essere pronto per la pubblicazione.
"""


def build_conclusion_prompt(
    thesis_data: Dict[str, Any],
    content_summary: str,
    chapters_titles: List[str],
    author_style_context: str = ""
) -> str:
    """
    Costruisce il prompt per generare la Conclusione della tesi.

    Args:
        thesis_data: Parametri della tesi
        content_summary: Riassunto del contenuto generato
        chapters_titles: Lista dei titoli dei capitoli
        author_style_context: Contesto dello stile autore

    Returns:
        Prompt completo per la generazione della conclusione
    """
    chapters_list = "\n".join([f"  {i+1}. {title}" for i, title in enumerate(chapters_titles)])

    return f"""
═══════════════════════════════════════════════════════════════════════════════
GENERAZIONE CONCLUSIONE TESI
═══════════════════════════════════════════════════════════════════════════════

Sei un esperto nella scrittura di documenti accademici e professionali.
Il tuo compito è scrivere la CONCLUSIONE della tesi.

═══════════════════════════════════════════════════════════════════════════════
PARAMETRI DELLA TESI
═══════════════════════════════════════════════════════════════════════════════

TITOLO: {thesis_data.get('title', 'Non specificato')}
DESCRIZIONE: {thesis_data.get('description', 'Non specificata')}

═══════════════════════════════════════════════════════════════════════════════
PARAMETRI DI SCRITTURA
═══════════════════════════════════════════════════════════════════════════════

STILE: {thesis_data.get('writing_style_name', 'Non specificato')}
  → {thesis_data.get('writing_style_hint', '')}

LIVELLO PROFONDITÀ: {thesis_data.get('content_depth_name', 'Intermedio')}
PAROLE TARGET: ~{thesis_data.get('words_per_section', 5000)} parole

═══════════════════════════════════════════════════════════════════════════════
PUBBLICO TARGET
═══════════════════════════════════════════════════════════════════════════════

DESTINATARI: {thesis_data.get('target_audience_name', 'Pubblico Generale')}
LIVELLO CONOSCENZA: {thesis_data.get('knowledge_level_name', 'Intermedio')}

═══════════════════════════════════════════════════════════════════════════════
CAPITOLI DELLA TESI
═══════════════════════════════════════════════════════════════════════════════

{chapters_list}

═══════════════════════════════════════════════════════════════════════════════
RIASSUNTO DEI CONTENUTI DELLA TESI
═══════════════════════════════════════════════════════════════════════════════

{content_summary}

═══════════════════════════════════════════════════════════════════════════════
STILE DELL'AUTORE
═══════════════════════════════════════════════════════════════════════════════
{author_style_context if author_style_context else "Nessuno stile specifico addestrato - usa lo stile richiesto nei parametri."}

═══════════════════════════════════════════════════════════════════════════════
ISTRUZIONI
═══════════════════════════════════════════════════════════════════════════════

⚠️ REQUISITO CRITICO — LUNGHEZZA: Scrivi ALMENO {thesis_data.get('words_per_section', 5000)} parole.
NON scrivere meno di {thesis_data.get('words_per_section', 5000)} parole — è OBBLIGATORIO.
Sviluppa ogni punto in profondità con analisi dettagliate e riflessioni.

La conclusione deve:
1. RIASSUMERE i punti principali trattati nei vari capitoli
2. SINTETIZZARE i risultati e le scoperte chiave
3. Evidenziare il CONTRIBUTO del lavoro al campo di studio
4. Discutere le LIMITAZIONI del lavoro (se applicabile)
5. Suggerire possibili SVILUPPI FUTURI e direzioni di ricerca
6. Chiudere con una riflessione finale significativa

{_get_no_citation_instruction(thesis_data.get('citation_style', 'footnotes'))} nella conclusione.
NON ripetere verbatim frasi dai capitoli precedenti — rielabora i concetti.

SCRIVI COME UNO STUDENTE UNIVERSITARIO REALE:
- Usa parole normali, evita vocabolario pomposo
- PAROLE VIETATE: fondamentale, significativo, cruciale, rilevante, sottolineare,
  evidenziare, emergere, inoltre, pertanto, dunque, tuttavia, rappresenta,
  costituisce, paradigma, panorama, scenario, nell'ambito di, in questo contesto,
  risulta, si configura, appare evidente, e' possibile affermare
- Frasi di lunghezze IRREGOLARI: alterna corte (6-10 parole) e lunghe (25-40)
- NON iniziare mai due frasi consecutive con la stessa struttura
- Inizia almeno 2 frasi con "E", "Ma", "Pero'"
- MAI liste di 3 o 4 elementi simmetrici ("X, Y e Z"; "X, Y, Z e W") né elenchi a), b), c)
- MAI anafore né la formula "non X; è Y" / "non si tratta di X, ma di Y"
- NON aprire con "In conclusione/In sintesi/Per concludere" né chiudere con una massima
- NON chiudere paragrafi con frasi a effetto o riassuntive
- Paragrafi di lunghezze MOLTO diverse tra loro
- Il tono sia riflessivo ma naturale, non magniloquente

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Scrivi SOLO il contenuto della conclusione.
NON includere il titolo "Conclusione" (verra' aggiunto separatamente).
NON includere meta-commenti o note.
Il testo deve essere pronto per la pubblicazione.
"""


def build_bibliography_prompt(
    thesis_data: Dict[str, Any],
    all_content: str
) -> str:
    """
    Costruisce il prompt per generare la Bibliografia della tesi.

    Supporta due stili:
    - 'bibliography': citazioni [x] con bibliografia numerata
    - 'footnotes': note {{nota:...}} con bibliografia alfabetica

    Args:
        thesis_data: Parametri della tesi
        all_content: Tutto il contenuto generato

    Returns:
        Prompt completo per la generazione della bibliografia
    """
    import re

    citation_style = thesis_data.get('citation_style', 'footnotes')

    if citation_style == 'bibliography':
        # Stile classico [x]
        citations = sorted(set(int(m) for m in re.findall(r'\[(\d+)\]', all_content)))
        citations_str = ", ".join([f"[{c}]" for c in citations]) if citations else "Nessuna citazione trovata"
        num_citations = len(citations)

        citation_contexts = []
        for c in citations:
            pattern = rf'[^.]*\[{c}\][^.]*\.'
            matches = re.findall(pattern, all_content)
            if matches:
                context = matches[0].strip()[:300]
                citation_contexts.append(f"  [{c}] usata nel contesto: \"{context}\"")
            else:
                idx = all_content.find(f'[{c}]')
                if idx >= 0:
                    start = max(0, idx - 100)
                    end = min(len(all_content), idx + 100)
                    context = all_content[start:end].strip()
                    citation_contexts.append(f"  [{c}] usata nel contesto: \"{context}\"")

        contexts_text = "\n".join(citation_contexts) if citation_contexts else "Nessun contesto estratto."

        return f"""Sei un ricercatore accademico esperto. Il tuo compito è compilare la
bibliografia per una tesi, associando a ogni citazione [x] nel testo
un riferimento bibliografico appropriato.

TITOLO TESI: {thesis_data.get('title', 'Non specificato')}
DESCRIZIONE: {thesis_data.get('description', 'Non specificata')}
SETTORE: {thesis_data.get('industry_name', 'Generale')}

CITAZIONI DA RISOLVERE: {citations_str} (totale: {num_citations})

CONTESTO DI OGNI CITAZIONE:
{contexts_text}

CONTENUTO DELLA TESI:
{all_content[:15000]}
{"[...contenuto troncato...]" if len(all_content) > 15000 else ""}

ISTRUZIONI:

Per ogni citazione [x] trovata nel testo, genera UNA voce bibliografica.

Come selezionare le fonti:
1. Leggi il contesto in cui appare ogni [x] nel testo
2. Identifica l'argomento specifico trattato in quel punto
3. Dalla tua conoscenza, seleziona un'opera REALE pertinente a quell'argomento
4. Privilegia opere classiche e fondamentali del campo che CONOSCI CON CERTEZZA
5. Se il testo menziona esplicitamente un autore o opera, usa QUELLA

FORMATO richiesto — STILE APA ITALIANO (RIGOROSO):
Schema generale:
   Cognome, N. (Anno). *Titolo in corsivo con prima lettera maiuscola*. Città di pubblicazione: Casa editrice.

Casi specifici:
[x] LIBRO con un autore:
    Cognome, N. (Anno). *Titolo dell'opera*. Città: Casa editrice.
[x] LIBRO con due o più autori:
    Cognome, N. & Cognome, N. (Anno). *Titolo dell'opera*. Città: Casa editrice.
[x] ARTICOLO su rivista (titolo articolo NON in corsivo, *Nome Rivista* SI):
    Cognome, N. (Anno). Titolo dell'articolo. *Nome Rivista*, vol(num), pp-pp.
[x] CAPITOLO in libro a cura di:
    Cognome, N. (Anno). Titolo capitolo. In Cognome Curatore, N. (a cura di), *Titolo libro* (pp. XX-XX). Città: Casa editrice.
[x] REPORT istituzionale:
    Organizzazione. (Anno). *Titolo del report*. Città: Editore. URL (se noto)

REGOLE DI FORMATTAZIONE APA OBBLIGATORIE:
- Cognome dell'autore PRIMA, poi virgola, poi iniziale del nome puntata.
- Anno tra parentesi tonde, seguito da un punto.
- Titolo dei LIBRI / REPORT in corsivo Markdown (*titolo*) con SOLO prima lettera maiuscola
  (e nomi propri); NON usare maiuscolo a inizio di ogni parola.
- Per gli ARTICOLI: il titolo dell'articolo NON va in corsivo, va in corsivo *Nome Rivista*.
- Dopo il titolo: punto, città di pubblicazione, due punti, casa editrice, punto.
- Per autori italiani: usa la forma "Cognome, N." anche se nei dati il nome appare per esteso.
- Il punto finale è obbligatorio.

REGOLE TASSATIVE:
1. Genera ESATTAMENTE {num_citations} voci, una per ogni citazione
2. Numeri in ordine crescente: [1], [2], [3]...
3. Ogni fonte deve essere pertinente al contesto in cui [x] appare
4. La città di pubblicazione DEVE essere specificata per libri e report.
5. NON scrivere messaggi, scuse, avvertenze o disclaimer
6. NON dire che non puoi farlo — FALLO E BASTA
7. NON aggiungere note come "verificare", "controllare", "potrebbe non essere reale"
8. Output: SOLO la lista delle voci bibliografiche, nient'altro
9. NON includere il titolo "Bibliografia"

Inizia direttamente con [1] e prosegui fino a [{num_citations}].

Esempio della voce attesa:
   [1] Bonura, A. (2021). *Legislazione e innovazioni normative*. Palermo: USR Sicilia.
"""

    else:
        # Stile footnotes {{nota:...}}
        all_notes = re.findall(r'\{\{nota:\s*(.*?)\}\}', all_content)

        full_refs = []
        for note in all_notes:
            note_stripped = note.strip()
            if not note_stripped.lower().startswith(('ibidem', 'ivi.', 'op.cit')):
                full_refs.append(note_stripped)

        unique_refs = list(dict.fromkeys(full_refs))
        num_refs = len(unique_refs)

        refs_list = "\n".join([f"  {i+1}. {ref}" for i, ref in enumerate(unique_refs)]) if unique_refs else "Nessun riferimento trovato."

        return f"""Sei un ricercatore accademico esperto. Il tuo compito è compilare la
bibliografia finale per una tesi, a partire dalle note a piè di pagina
inserite nel testo.

TITOLO TESI: {thesis_data.get('title', 'Non specificato')}
DESCRIZIONE: {thesis_data.get('description', 'Non specificata')}
SETTORE: {thesis_data.get('industry_name', 'Generale')}

RIFERIMENTI TROVATI NELLE NOTE ({num_refs} unici):
{refs_list}

CONTENUTO DELLA TESI (per contesto):
{all_content[:15000]}
{"[...contenuto troncato...]" if len(all_content) > 15000 else ""}

ISTRUZIONI:

Compila la bibliografia finale ordinata ALFABETICAMENTE per cognome dell'autore.
Per ogni riferimento trovato nelle note:
1. Usa il riferimento ESATTAMENTE come appare nelle note (autore, anno, titolo, editore)
2. Completa eventuali informazioni mancanti (ISBN, città, ecc.) se le conosci
3. Ordina ALFABETICAMENTE per cognome del primo autore
4. Se un riferimento è un report istituzionale, ordina per nome organizzazione

FORMATO richiesto — STILE APA ITALIANO (RIGOROSO):
Schema generale:
   Cognome, N. (Anno). *Titolo in corsivo con prima lettera maiuscola*. Città di pubblicazione: Casa editrice.

Casi specifici:
LIBRO con un autore:
   Cognome, N. (Anno). *Titolo dell'opera*. Città: Casa editrice.
LIBRO con due o più autori:
   Cognome, N. & Cognome, N. (Anno). *Titolo dell'opera*. Città: Casa editrice.
ARTICOLO su rivista (titolo articolo NON in corsivo, *Nome Rivista* SI):
   Cognome, N. (Anno). Titolo dell'articolo. *Nome Rivista*, vol(num), pp-pp.
CAPITOLO in libro a cura di:
   Cognome, N. (Anno). Titolo capitolo. In Cognome Curatore, N. (a cura di), *Titolo libro* (pp. XX-XX). Città: Casa editrice.
REPORT istituzionale:
   Organizzazione. (Anno). *Titolo del report*. Città: Editore. URL (se noto)

REGOLE DI FORMATTAZIONE APA OBBLIGATORIE:
- Cognome dell'autore PRIMA, poi virgola, poi iniziale del nome puntata.
- Anno tra parentesi tonde, seguito da un punto.
- Titolo dei LIBRI / REPORT in corsivo Markdown (*titolo*) con SOLO prima lettera maiuscola
  (e nomi propri); NON usare maiuscolo a inizio di ogni parola.
- Per gli ARTICOLI: il titolo dell'articolo NON va in corsivo, va in corsivo *Nome Rivista*.
- Dopo il titolo: punto, città di pubblicazione, due punti, casa editrice, punto.
- Per autori italiani: usa la forma "Cognome, N." anche se nei dati il nome appare per esteso.
- Il punto finale è obbligatorio.

REGOLE TASSATIVE:
1. Includi SOLO i riferimenti completi che appaiono nelle note (non Op.cit./Ibidem/Ivi)
2. Mantieni il formato APA esatto: se una nota era già conforme APA, riportala così com'è;
   se era incompleta (manca città / editore), completala con dati REALI verificabili.
3. NON aggiungere fonti che non sono state citate nelle note
4. NON scrivere messaggi, scuse, avvertenze o disclaimer
5. NON dire che non puoi farlo — FALLO E BASTA
6. Output: SOLO la lista delle voci bibliografiche, nient'altro
7. NON includere il titolo "Bibliografia"

Esempio della voce attesa:
   Bonura, A. (2021). *Legislazione e innovazioni normative*. Palermo: USR Sicilia.

Inizia direttamente con la prima voce bibliografica.
"""
