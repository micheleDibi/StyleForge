"""
Prompt per la generazione di tesi/relazioni.

Questo modulo contiene i prompt dettagliati per ogni fase
della generazione di tesi utilizzando OpenAI o1/o3.
"""

from typing import Dict, Any, List, Optional


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

DIMENSIONE PUBBLICO: {thesis_data.get('audience_size_name', 'Medio')}
SETTORE/INDUSTRIA: {thesis_data.get('industry_name', 'Generale')}
DESTINATARI: {thesis_data.get('target_audience_name', 'Pubblico Generale')}
  → Indicazione: {thesis_data.get('target_audience_hint', '')}

═══════════════════════════════════════════════════════════════════════════════
CONTESTO DAGLI ALLEGATI
═══════════════════════════════════════════════════════════════════════════════
{attachments_context if attachments_context else "Nessun allegato fornito."}

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
CONTESTO DAGLI ALLEGATI
═══════════════════════════════════════════════════════════════════════════════
{attachments_context if attachments_context else "Nessun allegato fornito."}

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
    author_style_context: str = ""
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
MATERIALE DI RIFERIMENTO (dagli allegati)
═══════════════════════════════════════════════════════════════════════════════
{attachments_context if attachments_context else "Nessun materiale allegato."}

═══════════════════════════════════════════════════════════════════════════════
STILE DELL'AUTORE
═══════════════════════════════════════════════════════════════════════════════
{author_style_context if author_style_context else "Nessuno stile specifico addestrato - usa lo stile richiesto nei parametri."}

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

6. CITAZIONI BIBLIOGRAFICHE — SOLO FONTI REALI:
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
   - Esempio: "Secondo Kahneman [1], i bias cognitivi influenzano..."
   - I numeri devono essere progressivi e coerenti all'interno della tesi
   - Quando citi, includi nel testo abbastanza contesto per identificare la fonte
     (es. nome autore, anno, titolo abbreviato) così la bibliografia sarà accurata

7. SCRIVI IN MODO NATURALE:
   - Evita frasi troppo lunghe o complesse
   - Usa variazione nella struttura delle frasi
   - Includi occasionali imperfezioni stilistiche che rendano il testo umano
   - Non usare strutture troppo "perfette" o ripetitive

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Scrivi SOLO il contenuto della sezione.

IMPORTANTE:
- NON includere il titolo della sezione (verrà aggiunto separatamente)
- NON includere meta-commenti o note per l'autore
- NON usare placeholder o [inserire qui]
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
MATERIALE DI RIFERIMENTO (dagli allegati)
═══════════════════════════════════════════════════════════════════════════════
{attachments_context if attachments_context else "Nessun materiale allegato."}

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

NON inserire citazioni bibliografiche [x] nell'introduzione.

SCRIVI IN MODO NATURALE:
- Evita frasi troppo lunghe o complesse
- Usa variazione nella struttura delle frasi
- Includi occasionali imperfezioni stilistiche che rendano il testo umano
- Non usare strutture troppo "perfette" o ripetitive

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Scrivi SOLO il contenuto dell'introduzione.
NON includere il titolo "Introduzione" (verrà aggiunto separatamente).
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

NON inserire citazioni bibliografiche [x] nella conclusione.
NON ripetere verbatim frasi dai capitoli precedenti — rielabora i concetti.

SCRIVI IN MODO NATURALE:
- Evita frasi troppo lunghe o complesse
- Usa variazione nella struttura delle frasi
- Il tono deve essere riflessivo e conclusivo
- Non usare strutture troppo "perfette" o ripetitive

═══════════════════════════════════════════════════════════════════════════════
OUTPUT
═══════════════════════════════════════════════════════════════════════════════

Scrivi SOLO il contenuto della conclusione.
NON includere il titolo "Conclusione" (verrà aggiunto separatamente).
NON includere meta-commenti o note.
Il testo deve essere pronto per la pubblicazione.
"""


def build_bibliography_prompt(
    thesis_data: Dict[str, Any],
    all_content: str
) -> str:
    """
    Costruisce il prompt per generare la Bibliografia della tesi.

    Analizza il contenuto generato per trovare le citazioni [x]
    e genera una bibliografia formale.

    Args:
        thesis_data: Parametri della tesi
        all_content: Tutto il contenuto generato (per trovare le citazioni [x])

    Returns:
        Prompt completo per la generazione della bibliografia
    """
    # Estrai le citazioni [x] dal testo
    import re
    citations = sorted(set(int(m) for m in re.findall(r'\[(\d+)\]', all_content)))
    citations_str = ", ".join([f"[{c}]" for c in citations]) if citations else "Nessuna citazione trovata"
    num_citations = len(citations)

    # Estrai contesto per ogni citazione (frase in cui appare)
    citation_contexts = []
    for c in citations:
        # Trova le frasi che contengono questa citazione
        pattern = rf'[^.]*\[{c}\][^.]*\.'
        matches = re.findall(pattern, all_content)
        if matches:
            context = matches[0].strip()[:300]
            citation_contexts.append(f"  [{c}] usata nel contesto: \"{context}\"")
        else:
            # Fallback: prendi 200 caratteri attorno alla citazione
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
   (es. per psicologia: Kahneman, Bandura, Piaget; per economia: Keynes, Stiglitz;
   per informatica: Tanenbaum, Cormen, Knuth; ecc.)
5. Se il testo menziona esplicitamente un autore o opera, usa QUELLA

Tipologie di fonti da usare:
- Libri accademici di autori noti (la tipologia più sicura)
- Manuali universitari classici del settore
- Report istituzionali (ISTAT, OMS/WHO, OCSE/OECD, Eurostat, Banca d'Italia, ecc.)
- Articoli da riviste scientifiche note (Nature, Science, The Lancet, ecc.)
- Normative e leggi (es. D.Lgs., Regolamenti UE)

FORMATO richiesto (APA italiano):
[x] Cognome, N. (Anno). Titolo dell'opera. Casa editrice.
[x] Cognome, N. & Cognome, N. (Anno). Titolo articolo. Nome Rivista, vol(num), pp-pp.
[x] Organizzazione. (Anno). Titolo report. URL (se noto)

REGOLE TASSATIVE:
1. Genera ESATTAMENTE {num_citations} voci, una per ogni citazione
2. Numeri in ordine crescente: [1], [2], [3]...
3. Ogni fonte deve essere pertinente al contesto in cui [x] appare
4. NON scrivere messaggi, scuse, avvertenze o disclaimer
5. NON dire che non puoi farlo — FALLO E BASTA
6. NON aggiungere note come "verificare", "controllare", "potrebbe non essere reale"
7. Output: SOLO la lista delle voci bibliografiche, nient'altro
8. NON includere il titolo "Bibliografia"

Inizia direttamente con [1] e prosegui fino a [{num_citations}].
"""
