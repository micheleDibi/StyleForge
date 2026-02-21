# StyleForge API - Architettura

## Panoramica

StyleForge API è un'applicazione FastAPI scalabile progettata per gestire job multipli concorrenti di addestramento e generazione di contenuti utilizzando Claude Opus 4.5.

## Componenti Principali

### 1. API Layer (`api.py`)

Il layer principale dell'applicazione che espone gli endpoint REST.

**Responsabilità:**
- Gestione delle richieste HTTP
- Validazione input tramite Pydantic
- Orchestrazione dei componenti sottostanti
- Gestione errori e response formatting

**Endpoints principali:**
- `/sessions` - CRUD per sessioni
- `/train` - Addestramento con PDF
- `/generate` - Generazione contenuti
- `/jobs` - Monitoraggio job
- `/health` - Health check

### 2. Session Manager (`session_manager.py`)

Gestisce multiple sessioni Claude indipendenti in modo thread-safe.

**Caratteristiche:**
- Creazione/eliminazione sessioni
- Isolamento completo tra sessioni
- Tracking metadata (created_at, last_activity, jobs)
- Cleanup automatico sessioni inattive
- Thread-safe con Lock

**Struttura dati:**
```python
{
    "session_id": {
        "client": ClaudeClient(),
        "metadata": {
            "created_at": datetime,
            "last_activity": datetime,
            "jobs": [job_ids]
        }
    }
}
```

### 3. Job Manager (`job_manager.py`)

Gestisce l'esecuzione asincrona di job con sistema di code.

**Caratteristiche:**
- Coda di job con semaforo per limitare concorrenza
- Esecuzione asincrona con asyncio
- Tracking stato job (pending, in_progress, completed, failed)
- Cleanup automatico job completati
- Thread-safe con Lock

**Tipi di job:**
- `TRAINING` - Addestramento sessione
- `GENERATION` - Generazione contenuto

**Stati job:**
```
PENDING → TRAINING/GENERATING → COMPLETED
                               ↓
                            FAILED
```

### 4. Claude Client (`claude_client.py`)

Wrapper per l'API Claude con gestione conversazione.

**Funzionalità:**
- Addestramento (carica PDF e context)
- Generazione (produce contenuto)
- Gestione cronologia conversazione
- Reset sessione

### 5. Models (`models.py`)

Modelli Pydantic per validazione e serializzazione.

**Modelli principali:**
- `TrainingRequest/Response`
- `GenerationRequest/Response`
- `JobStatusResponse`
- `SessionInfo`

### 6. Configuration (`config.py`)

Configurazione centralizzata con validazione.

**Variabili chiave:**
- API keys
- Limiti token
- Configurazione server
- Limiti concorrenza
- Path directories

## Flusso di Esecuzione

### Training Flow

```
1. Client → POST /train (PDF file)
              ↓
2. API → Salva file in uploads/
              ↓
3. API → Crea/recupera Session
              ↓
4. API → Crea Job TRAINING
              ↓
5. Job Manager → Esegue training in background
              ↓
6. Claude Client → Legge PDF + invia a Claude
              ↓
7. Job → Status = COMPLETED (o FAILED)
              ↓
8. Client ← Polling GET /jobs/{job_id}
```

### Generation Flow

```
1. Client → POST /generate (topic, words)
              ↓
2. API → Verifica session trained
              ↓
3. API → Crea Job GENERATION
              ↓
4. Job Manager → Esegue generation in background
              ↓
5. Claude Client → Genera contenuto
              ↓
6. Job → Status = COMPLETED + result
              ↓
7. Client ← GET /jobs/{job_id} o /results/{job_id}
```

## Scalabilità

### Concorrenza

**Livello 1: Sessioni Multiple**
- Ogni sessione è completamente isolata
- Limite: Memoria disponibile
- Thread-safe con Lock

**Livello 2: Job Paralleli**
- Semaforo controlla job concorrenti
- Default: 10 job simultanei
- Configurabile via `MAX_CONCURRENT_JOBS`

**Livello 3: Worker Uvicorn**
- Multiple istanze dell'app
- Sfrutta multi-core CPU
- Comando: `--workers N`

### Performance

**Ottimizzazioni implementate:**
1. Background tasks per operazioni lunghe
2. Semaphore per limitare carico
3. Cleanup automatico risorse
4. Asyncio per I/O non bloccante
5. Thread-safe data structures

**Bottleneck potenziali:**
- API Claude rate limits
- Memoria per sessioni multiple
- Disco per upload/results

## Sicurezza

### Validazione Input

- Pydantic models per tutti gli input
- Controllo dimensione file upload
- Sanitizzazione percorsi file
- Validazione estensioni (.pdf only)

### Rate Limiting

Configurabile tramite nginx o middleware FastAPI.

### CORS

Configurabile per ambiente (dev vs prod).

### Error Handling

- Try/catch globale
- Exception handlers custom
- Logging strutturato
- Messaggi errore informativi

## Deployment

### Opzione 1: Standalone

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Opzione 2: Con Workers

```bash
uvicorn api:app --workers 4 --host 0.0.0.0 --port 8000
```

### Opzione 3: Gunicorn + Uvicorn

```bash
gunicorn api:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Opzione 4: Docker

```bash
docker-compose up -d
```

### Opzione 5: Docker + Nginx

```bash
docker-compose --profile with-nginx up -d
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Response include:
- Status server
- Versione API
- Sessioni attive
- Job attivi

### Logs

- Uvicorn logs HTTP requests
- Application logs eventi importanti
- Job failures logged con stack trace

### Metrics (Future)

- Prometheus endpoint
- Grafana dashboard
- Alerting system

## Estensibilità

### Aggiungere Nuovi Job Types

1. Definisci nuovo `JobType` enum
2. Crea task function
3. Aggiungi endpoint API
4. Documenta in OpenAPI

### Aggiungere Storage Backend

Attualmente in-memory. Per persistenza:

1. Implementa `StorageBackend` interface
2. Sostituisci dict con storage
3. Opzioni: Redis, PostgreSQL, MongoDB

### Aggiungere Caching

Per risultati frequenti:

1. Implementa cache layer (Redis)
2. Cache key = hash(session + params)
3. TTL configurabile

### Aggiungere WebSocket

Per aggiornamenti real-time:

1. Aggiungi WebSocket endpoint
2. Broadcast job updates
3. Client subscribe a session/job

## Testing

### Unit Tests

```bash
pytest test_api.py -v
```

### Integration Tests

```bash
python example_client.py
```

### Load Testing

```bash
# Install locust
pip install locust

# Create locustfile.py
# Run: locust -f locustfile.py
```

## Troubleshooting

### Job rimane PENDING

**Cause:**
- Tutti i worker occupati
- Errore silenzioso nel task

**Soluzioni:**
- Aumenta `MAX_CONCURRENT_JOBS`
- Controlla logs
- Verifica Claude API key

### Memoria Alta

**Cause:**
- Troppe sessioni attive
- Job non rimossi

**Soluzioni:**
- Riduci `SESSION_CLEANUP_HOURS`
- Riduci `JOB_CLEANUP_HOURS`
- Elimina sessioni manualmente

### Claude API Errors

**Cause:**
- Rate limiting
- Token limit exceeded
- API key invalid

**Soluzioni:**
- Implementa retry logic
- Riduci `MAX_TOKENS_*`
- Verifica API key

## Roadmap

### v1.1
- [ ] WebSocket support
- [ ] Redis backend
- [ ] Prometheus metrics
- [ ] Rate limiting middleware

### v1.2
- [ ] User authentication
- [ ] API keys management
- [ ] Usage quotas
- [ ] Webhook notifications

### v2.0
- [ ] Multi-model support
- [ ] Streaming responses
- [ ] Result caching
- [ ] Advanced analytics

## License

MIT
