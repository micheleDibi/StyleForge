# Setup Algoritmo Anti-AI - Istruzioni

## Installazione Dipendenze

L'algoritmo di post-processing anti-AI richiede la libreria **spaCy** e il modello linguistico italiano.

### 1. Installa le dipendenze Python

```bash
cd backend
pip install -r requirements.txt
```

Questo installerà tutte le dipendenze necessarie, incluso `spacy>=3.7.0`.

### 2. Scarica il modello linguistico italiano per spaCy

```bash
python -m spacy download it_core_news_sm
```

Questo scaricherà il modello `it_core_news_sm` (~15MB) necessario per l'analisi linguistica.

### 3. Verifica l'installazione

Testa che tutto funzioni correttamente:

```bash
python anti_ai_processor.py
```

Dovresti vedere un output con:
- Testo originale (con pattern AI)
- Testo trasformato (anti-AI)

Se vedi l'output senza errori, l'installazione è completata con successo!

## Come Funziona

Quando utilizzi la funzione di **umanizzazione** tramite l'API:

```
POST /humanize
{
  "session_id": "your-trained-session",
  "testo": "Il tuo testo AI da umanizzare..."
}
```

Il sistema applicherà automaticamente:

1. **Claude Opus 4.5** riscrive il testo con lo stile dell'autore appreso
2. **Algoritmo Anti-AI** trasforma ulteriormente il testo eliminando tutti i pattern riconoscibili

Il risultato finale è un testo completamente indistinguibile da uno scritto da un umano.

## Troubleshooting

### Errore: "Modello spaCy italiano non trovato"

Se vedi questo errore, significa che il modello non è installato. Esegui:

```bash
python -m spacy download it_core_news_sm
```

### Errore: "No module named 'spacy'"

La libreria spaCy non è installata. Esegui:

```bash
pip install spacy>=3.7.0
```

### Performance lente

L'algoritmo richiede qualche secondo per processare il testo. Questo è normale.
Per testi molto lunghi (>5000 parole), il tempo di elaborazione può arrivare a 10-15 secondi.

## Test Manuale

Puoi testare l'algoritmo manualmente con Python:

```python
from anti_ai_processor import humanize_text_post_processing

testo_ai = """
Quattrocento ispettori. È il numero che manca.
Inoltre, il sistema è complesso. Funzionerà? Difficile dirlo.
"""

testo_umanizzato = humanize_text_post_processing(testo_ai)
print(testo_umanizzato)
```

## Documentazione Completa

Per dettagli completi sull'algoritmo, leggi:
- `backend/ANTI_AI_ALGORITHM.md` - Documentazione tecnica completa

## Supporto

Per problemi o domande, apri un issue nel repository.
