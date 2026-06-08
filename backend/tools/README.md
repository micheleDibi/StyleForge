# tools/ — Strumenti interni

## compilatio_harness.py — misura del "Rilevamento AI" Compilatio

Harness per misurare l'effetto degli stage anti-AI delle tesi sul punteggio
"Rilevamento AI" di Compilatio, e per fare confronti before/after e A/B di modello.

Riusa l'integrazione esistente (`compilatio_service.scan_text`) e gli stage
anti-AI (`ai_client.academic_deai_rewrite`, `anti_ai_processor` profilo
`academic`). NON deduce crediti applicativi (consuma solo quota Compilatio).

### Uso (dalla cartella `backend/`)

```bash
# solo trasformazioni, nessuna scansione (validazione rapida)
python -m tools.compilatio_harness --text-file campione.txt --variants raw,algo --dry-run

# misura reale (richiede COMPILATIO_USERNAME/PASSWORD in env)
COMPILATIO_USERNAME=... COMPILATIO_PASSWORD=... \
python -m tools.compilatio_harness --text-file campione.txt --variants raw,algo,rewrite+algo

# A/B modello generando un campione nuovo
python -m tools.compilatio_harness --generate --providers openai,claude \
  --topic "..." --words 1200 --variants raw,algo
```

Varianti: `raw | rewrite | algo | rewrite+algo`. Input: `--text-file`,
`--thesis-id <uuid>`, o `--generate`. Le credenziali Compilatio NON sono nel
`.env` del progetto: passale come variabili d'ambiente.

## Risultati empirici (giugno 2026) e limiti — IMPORTANTE

Misure reali su Compilatio (sezione tesi generata con o3, ~1385 parole):

| Pipeline | AI% osservato |
|---|---|
| raw (o3, generazione attuale) | ~33% (stabile) |
| solo riscrittura LLM (Claude) | ~42% (peggiora) |
| pass algoritmico (profilo academic) | 28% … 33% … 11% (alta varianza) |
| rewrite + algo | 11% e 28% (stesso pipeline, run diversi) |

Conclusioni:
- Il baseline ~33% conferma il report Compilatio fornito (~34%).
- Il prompt di generazione già elimina i marcatori AI lessicali: Compilatio
  rileva **a livello statistico/strutturale** (perplessità/n-gram), non da
  keyword. Per questo la perturbazione lessicale ha effetto limitato.
- **La riscrittura LLM non abbassa** il punteggio Compilatio (spesso lo alza):
  è quindi **OFF di default** (`THESIS_REWRITE_ENABLED=false`). Resta
  attivabile perché migliora la prosa percepita da un lettore umano.
- Il **pass algoritmico register-safe** (profilo `academic`) riduce il punteggio
  *in media* ma con **forte varianza** e nessuna garanzia di scendere sotto una
  soglia fissa. Restando in registro accademico, **<10% non è garantibile**.

Decisione di prodotto adottata: **default register-safe** — pass algoritmico
academic ON, riscrittura LLM OFF. Abbassa il punteggio senza rischi di registro,
senza garanzia di soglia. Per spingere oltre servirebbe perturbazione aggressiva
(degrada il testo) o un loop "misura-e-ritenta" su Compilatio a generazione
(lento/costoso).

## Flag di configurazione (config.py)

- `THESIS_ANTI_AI_ENABLED` (default `true`) — master switch degli stage anti-AI.
- `THESIS_REWRITE_ENABLED` (default `false`) — riscrittura LLM de-AI.
- `THESIS_ALGO_ENABLED` (default `true`) — pass algoritmico academic.
- `THESIS_REWRITE_MODEL` (default `claude-opus-4-8`).
- `THESIS_ANTI_AI_PROFILE` (default `academic`).
