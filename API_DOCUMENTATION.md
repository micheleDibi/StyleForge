# StyleForge - API Esterna v1

API REST per accesso programmatico alle funzionalita' di umanizzazione testo di StyleForge.

## Autenticazione

Tutte le richieste richiedono un header `X-API-Key` con una chiave API valida.

```
X-API-Key: sf_k_abc123...
```

Le API key vengono create dall'amministratore tramite il pannello admin.
La chiave completa viene mostrata **una sola volta** alla creazione.
Solo l'hash SHA-256 viene salvato nel database.

## Base URL

```
https://<your-domain>/api/v1
```

## Rate Limiting

Ogni API key ha un rate limit configurabile (default: 30 richieste/minuto).
Al superamento del limite, viene restituito HTTP `429 Too Many Requests` con header `Retry-After: 60`.

---

## Endpoint

### 1. Umanizzazione completa

Riscrive il testo nello stile appreso da una sessione addestrata.

**Richiede una sessione addestrata.**

```
POST /api/v1/humanize
```

**Headers:**
```
Content-Type: application/json
X-API-Key: sf_k_...
```

**Body:**
```json
{
  "session_id": "session_abc123def456",
  "text": "Il testo generato da AI da umanizzare. Minimo 50 caratteri."
}
```

**Risposta (202):**
```json
{
  "job_id": "job_abc123def456",
  "status": "pending",
  "message": "Job inviato. Usa GET /api/v1/jobs/{job_id} per ottenere il risultato."
}
```

**Esempio curl:**
```bash
curl -X POST https://<domain>/api/v1/humanize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sf_k_abc123..." \
  -d '{
    "session_id": "session_abc123def456",
    "text": "Il testo da umanizzare..."
  }'
```

---

### 2. Correzione Anti-AI

Applica micro-modifiche conservative per ridurre la rilevabilita' AI.
Non richiede sessione addestrata.

```
POST /api/v1/anti-ai-correct
```

**Headers:**
```
Content-Type: application/json
X-API-Key: sf_k_...
```

**Body:**
```json
{
  "text": "Il testo da correggere. Minimo 50 caratteri."
}
```

**Risposta (202):**
```json
{
  "job_id": "job_xyz789...",
  "status": "pending",
  "message": "Job inviato. Usa GET /api/v1/jobs/{job_id} per ottenere il risultato."
}
```

**Esempio curl:**
```bash
curl -X POST https://<domain>/api/v1/anti-ai-correct \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sf_k_abc123..." \
  -d '{
    "text": "Il testo da correggere con micro-modifiche anti-AI..."
  }'
```

---

### 3. Stato Job (Polling)

Controlla lo stato e il risultato di un job.

```
GET /api/v1/jobs/{job_id}
```

**Headers:**
```
X-API-Key: sf_k_...
```

**Risposta (in corso):**
```json
{
  "job_id": "job_abc123def456",
  "status": "generating",
  "progress": 50,
  "result": null,
  "error": null,
  "created_at": "2026-03-02T10:30:00",
  "completed_at": null
}
```

**Risposta (completato):**
```json
{
  "job_id": "job_abc123def456",
  "status": "completed",
  "progress": 100,
  "result": "Il testo umanizzato risultante...",
  "error": null,
  "created_at": "2026-03-02T10:30:00",
  "completed_at": "2026-03-02T10:31:15"
}
```

**Risposta (errore):**
```json
{
  "job_id": "job_abc123def456",
  "status": "failed",
  "progress": 0,
  "result": null,
  "error": "Descrizione dell'errore",
  "created_at": "2026-03-02T10:30:00",
  "completed_at": "2026-03-02T10:30:05"
}
```

**Esempio curl:**
```bash
curl -X GET https://<domain>/api/v1/jobs/job_abc123def456 \
  -H "X-API-Key: sf_k_abc123..."
```

---

## Stati dei Job

| Stato | Descrizione |
|-------|-------------|
| `pending` | Job in coda, non ancora iniziato |
| `generating` | Elaborazione in corso |
| `completed` | Completato con successo, il campo `result` contiene il testo |
| `failed` | Errore, il campo `error` contiene il messaggio |

---

## Flusso tipico

```
1. POST /api/v1/humanize (o /anti-ai-correct)
   -> Ricevi job_id

2. GET /api/v1/jobs/{job_id}  (polling ogni 3-5 secondi)
   -> status: "generating", progress: 50

3. GET /api/v1/jobs/{job_id}
   -> status: "completed", result: "testo umanizzato..."
```

---

## Codici di Errore

| Codice | Descrizione |
|--------|-------------|
| `401` | API key mancante o non valida |
| `403` | API key revocata, scaduta, o account disabilitato |
| `404` | Sessione o job non trovato |
| `422` | Parametri non validi (es. testo troppo corto) |
| `429` | Rate limit superato |
| `500` | Errore interno del server |

---

## Sicurezza

- Le API key usano hash SHA-256: la chiave completa non viene mai salvata
- Formato chiave: `sf_k_<40 caratteri hex>` (45 caratteri totali)
- Ogni chiave ha rate limiting configurabile
- Le chiavi possono avere scadenza temporale
- Le chiavi possono essere revocate istantaneamente
- I job sono isolati per utente: una chiave non puo' accedere ai job di altri utenti
- La documentazione Swagger e' disponibile a `/docs`
