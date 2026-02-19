# StyleForge API

API scalabile per la generazione di contenuti utilizzando Claude Opus 4.5 con architettura basata su job e sessioni multiple.

## Caratteristiche

- **Architettura Scalabile**: Gestione di job multipli concorrenti con sistema di code
- **Session Management**: Supporto per sessioni multiple indipendenti
- **Background Processing**: Tutte le operazioni pesanti vengono eseguite in background
- **API RESTful**: Endpoints ben strutturati con documentazione OpenAPI
- **AI Detection**: Rilevamento integrato di testi generati da AI

## Installazione

### 1. Installa le dipendenze

```bash
pip install -r requirements.txt
```

### 2. Configura le variabili d'ambiente

Copia `.env.example` in `.env` e configura le tue chiavi:

```bash
cp .env.example .env
```

Modifica `.env` e aggiungi la tua API key di Anthropic:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### 3. Crea il file di prompt

Assicurati che il file `prompt_addestramento.txt` esista nella directory backend.

## Avvio del Server

### Modalità Sviluppo

```bash
python api.py
```

Oppure con uvicorn direttamente:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### Modalità Produzione

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

Con Gunicorn (consigliato per produzione):

```bash
gunicorn api:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Documentazione API

Una volta avviato il server, la documentazione interattiva è disponibile a:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Workflow Base

### 1. Crea una Sessione

```bash
curl -X POST "http://localhost:8000/sessions"
```

Response:
```json
{
  "session_id": "session_abc123",
  "is_trained": false,
  "conversation_length": 0,
  "created_at": "2025-12-20T10:00:00",
  "last_activity": "2025-12-20T10:00:00",
  "jobs": []
}
```

### 2. Addestra la Sessione con un PDF

```bash
curl -X POST "http://localhost:8000/train" \
  -F "file=@documento.pdf" \
  -F "session_id=session_abc123" \
  -F "max_pages=50"
```

Response:
```json
{
  "session_id": "session_abc123",
  "job_id": "job_xyz789",
  "status": "pending",
  "message": "Training avviato. Monitora lo stato con GET /jobs/job_xyz789",
  "created_at": "2025-12-20T10:01:00"
}
```

### 3. Monitora lo Stato del Job

```bash
curl "http://localhost:8000/jobs/job_xyz789"
```

Response (in corso):
```json
{
  "job_id": "job_xyz789",
  "session_id": "session_abc123",
  "status": "training",
  "progress": 50,
  "result": null,
  "error": null,
  "created_at": "2025-12-20T10:01:00",
  "updated_at": "2025-12-20T10:01:30",
  "completed_at": null
}
```

Response (completato):
```json
{
  "job_id": "job_xyz789",
  "session_id": "session_abc123",
  "status": "completed",
  "progress": 100,
  "result": "Risposta di Claude...",
  "error": null,
  "created_at": "2025-12-20T10:01:00",
  "updated_at": "2025-12-20T10:02:00",
  "completed_at": "2025-12-20T10:02:00"
}
```

### 4. Genera Contenuto

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_abc123",
    "argomento": "Psicopatologia",
    "numero_parole": 1000,
    "destinatario": "Pubblico Generale"
  }'
```

Response:
```json
{
  "session_id": "session_abc123",
  "job_id": "job_def456",
  "status": "pending",
  "message": "Generazione avviata. Monitora lo stato con GET /jobs/job_def456",
  "created_at": "2025-12-20T10:03:00"
}
```

### 5. Scarica il Risultato

```bash
curl "http://localhost:8000/results/job_def456" -O
```

## Endpoints Principali

### Sessions

- `POST /sessions` - Crea una nuova sessione
- `GET /sessions` - Elenca tutte le sessioni
- `GET /sessions/{session_id}` - Ottiene info su una sessione
- `DELETE /sessions/{session_id}` - Elimina una sessione

### Training

- `POST /train` - Addestra una sessione con un PDF

### Generation

- `POST /generate` - Genera contenuto da una sessione addestrata

### Jobs

- `GET /jobs/{job_id}` - Ottiene lo stato di un job
- `GET /jobs` - Elenca tutti i job (opzionalmente filtrati per sessione)
- `DELETE /jobs/{job_id}` - Elimina un job

### AI Detection (Copyleaks)

- `POST /detect/copyleaks` - Rileva testo AI con Copyleaks
- `POST /detect/copyleaks/report` - Genera report PDF AI detection

### Results

- `GET /results/{job_id}` - Scarica il risultato come file .txt

### Health

- `GET /health` - Health check e statistiche

## Configurazione Avanzata

### Limiti di Concorrenza

Modifica `MAX_CONCURRENT_JOBS` nel file `.env` per controllare quanti job possono essere eseguiti contemporaneamente:

```env
MAX_CONCURRENT_JOBS=10
```

### Cleanup Automatico

I job completati e le sessioni inattive vengono automaticamente rimossi dopo un periodo configurabile:

```env
JOB_CLEANUP_HOURS=24
SESSION_CLEANUP_HOURS=24
```

### CORS

Per permettere richieste da domini specifici:

```env
CORS_ORIGINS=http://localhost:3000,https://example.com
```

Per permettere da qualsiasi dominio (solo sviluppo):

```env
CORS_ORIGINS=*
```

## Esempio con Python

```python
import requests
import time

# URL base dell'API
BASE_URL = "http://localhost:8000"

# 1. Crea sessione
response = requests.post(f"{BASE_URL}/sessions")
session_id = response.json()["session_id"]
print(f"Sessione creata: {session_id}")

# 2. Addestra con PDF
with open("documento.pdf", "rb") as f:
    files = {"file": f}
    data = {"session_id": session_id, "max_pages": 50}
    response = requests.post(f"{BASE_URL}/train", files=files, data=data)
    train_job_id = response.json()["job_id"]
    print(f"Training job: {train_job_id}")

# 3. Attendi completamento training
while True:
    response = requests.get(f"{BASE_URL}/jobs/{train_job_id}")
    status = response.json()["status"]
    print(f"Status: {status}")

    if status == "completed":
        break
    elif status == "failed":
        print("Training fallito!")
        exit(1)

    time.sleep(5)

# 4. Genera contenuto
data = {
    "session_id": session_id,
    "argomento": "Psicopatologia",
    "numero_parole": 1000,
    "destinatario": "Pubblico Generale"
}
response = requests.post(f"{BASE_URL}/generate", json=data)
gen_job_id = response.json()["job_id"]
print(f"Generation job: {gen_job_id}")

# 5. Attendi completamento generazione
while True:
    response = requests.get(f"{BASE_URL}/jobs/{gen_job_id}")
    status = response.json()["status"]
    print(f"Status: {status}")

    if status == "completed":
        result = response.json()["result"]
        print(f"Contenuto generato: {result[:200]}...")
        break
    elif status == "failed":
        print("Generazione fallita!")
        exit(1)

    time.sleep(5)

# 6. Scarica risultato
response = requests.get(f"{BASE_URL}/results/{gen_job_id}")
with open("risultato.txt", "wb") as f:
    f.write(response.content)
print("Risultato salvato in risultato.txt")
```

## Architettura

```
┌─────────────────┐
│   FastAPI App   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──────┐  ┌──▼──────────┐
│ Session  │  │    Job      │
│ Manager  │  │  Manager    │
└───┬──────┘  └──┬──────────┘
    │            │
    │            │
┌───▼──────────┐ │
│   Claude     │ │
│   Clients    │ │
│  (Multiple)  │ │
└──────────────┘ │
                 │
         ┌───────▼──────────┐
         │  Background Jobs │
         │   (Async Queue)  │
         └──────────────────┘
```

### Componenti

1. **FastAPI App** (`api.py`): Server HTTP principale
2. **Session Manager** (`session_manager.py`): Gestisce sessioni Claude multiple
3. **Job Manager** (`job_manager.py`): Gestisce job asincroni con coda
4. **Claude Client** (`claude_client.py`): Wrapper per API Claude
5. **Models** (`models.py`): Modelli Pydantic per validazione
6. **Config** (`config.py`): Configurazione centralizzata

## Performance

### Scalabilità

- **Sessioni Concorrenti**: Illimitate (limitato solo dalla memoria)
- **Job Concorrenti**: Configurabile tramite `MAX_CONCURRENT_JOBS`
- **Workers Uvicorn**: Configurabile per sfruttare multi-core

### Ottimizzazioni

1. **Background Tasks**: Tutte le operazioni pesanti sono asincrone
2. **Semaphore**: Limita i job concorrenti per evitare sovraccarico
3. **Cleanup Automatico**: Libera risorse automaticamente
4. **Thread-Safe**: Gestione sicura di sessioni e job multipli

## Troubleshooting

### Il server non si avvia

Verifica che:
1. Tutte le dipendenze siano installate
2. `ANTHROPIC_API_KEY` sia configurata nel `.env`
3. Il file `prompt_addestramento.txt` esista

### Job rimane in pending

Controlla:
1. I log del server per errori
2. Che `MAX_CONCURRENT_JOBS` non sia troppo basso
3. Che ci sia spazio su disco per upload/results

### Errore 500 durante il training

Verifica:
1. Il file PDF sia valido e leggibile
2. Non superi i limiti di dimensione
3. I log del server per dettagli

## License

MIT
