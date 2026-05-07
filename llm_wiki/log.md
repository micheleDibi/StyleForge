# Log — Cronologia operazioni

Registro append-only di ogni operazione sul wiki. Formato fisso: `## [YYYY-MM-DD] tipo | descrizione`. Parseable con `grep "^## \[" log.md`.

Tipi: `ingest` | `query` | `lint` | `schema` | `setup`

---

## [2026-05-07] setup | inizializzazione del second brain
- Creato `CLAUDE.md` (schema operativo completo, sezioni 1–15).
- Creato `index.md` (catalogo content-oriented vuoto).
- Creato `log.md` (questo file).
- Strutturate cartelle: `raw/{articoli,libri,paper,note,trascrizioni,assets}` e `wiki/{fonti,entita,concetti,temi,sintesi,domande}`.
- Configurazione: dominio generico multi-uso, lingua italiana per schema e contenuti.
- Note: wiki pronto per la prima ingest. Nessuna fonte ancora presente in `raw/`.
