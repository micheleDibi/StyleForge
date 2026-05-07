# StyleForge

Piattaforma AI per la generazione e umanizzazione di contenuti accademici e professionali. Addestra modelli sul tuo stile di scrittura, genera contenuti originali, umanizza testi AI e crea tesi complete tramite un'interfaccia web moderna.

---

## Indice

1. [Funzionalità](#funzionalità)
2. [Stack tecnologico](#stack-tecnologico)
3. [Architettura](#architettura)
4. [Setup sviluppo](#setup-sviluppo)
5. [Configurazione](#configurazione)
6. [Deployment in produzione](#deployment-in-produzione)
7. [API esterna](#api-esterna)
8. [Sicurezza](#sicurezza)
9. [Troubleshooting](#troubleshooting)

---

## Funzionalità

### Core
- **Addestramento stilistico** — carica un PDF di esempi e l'AI impara il tuo stile (struttura frasi, vocabolario, tono).
- **Generazione contenuti** — articoli, saggi, relazioni nel tuo stile, scegliendo argomento, lunghezza, destinatario.
- **Umanizzazione testi** — due modalità: correzione anti-AI conservativa (no sessione richiesta) o riscrittura completa con sessione addestrata.
- **Generazione tesi** — wizard in 7 step (parametri → pubblico → allegati → capitoli → sezioni → generazione → export PDF/DOCX/TXT/MD).
- **Detector AI** — scansione AI/plagio integrata via Compilatio con report PDF custom.
- **Ricerca accademica** — paper e riviste su un argomento.
- **Image to Video** (admin) — generazione video da immagini.

### Calcifer
Assistente AI integrato sempre disponibile in ogni pagina. Conosce tutte le funzionalità e guida gli utenti passo-passo. Protetto da prompt injection (system prompt blindato, sanitizzazione input).

### Pannello admin
- Gestione utenti, ruoli e permessi granulari
- Configurazione costi crediti per ogni operazione (admin-editable runtime)
- Parametro EUR/credito
- Template di esportazione PDF (header/footer/copertina personalizzabili)
- API key management
- **Pagamenti PagoPA** — dashboard completa: KPI revenue, ordini con filtri, CRUD pacchetti crediti, configurazione SolutionPA, riconciliazione estrcc
- Statistiche di utilizzo

### Sistema crediti
Ogni operazione ha un costo configurabile. Stima crediti in tempo reale prima dell'azione, costo API in EUR (solo admin), storico transazioni completo. Le tesi usano una **tariffa flat** per ente (privato/formazione) configurata in admin.

### Acquisto crediti via PagoPA
Integrazione con SolutionPA (Intesa Sanpaolo) come Partner Tecnologico per ERSAF. Modello 1 (Checkout online): pacchetti predefiniti, redirect a Checkout pagoPA, webhook idempotente per accreditare i crediti all'esito EXECUTED.

---

## Stack tecnologico

| Layer | Stack |
|---|---|
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, PostgreSQL (Supabase) |
| **AI** | Anthropic Claude Opus 4.6 (training/generate/humanize), OpenAI o3 (tesi), Claude Haiku 4.5 (Calcifer) |
| **Frontend** | React 19, Vite 7, Tailwind CSS 4, React Router 7, Axios |
| **Auth** | JWT (access 30min + refresh 7gg), ruoli e permessi |
| **Pagamenti** | PagoPA via SolutionPA (zeep SOAP + webhook REST/SOAP) |
| **NLP** | spaCy (`it_core_news_sm`) per algoritmo anti-AI |
| **PDF** | PyMuPDF per export e report Detector AI |

**Prerequisiti**: Python 3.11+, Node.js **20.19+ o 22.12+** (Vite 7 lo richiede), PostgreSQL, chiavi Anthropic + OpenAI.

---

## Architettura

```
StyleForge/
├── backend/                          FastAPI + Python
│   ├── api.py                        Server REST principale, wire dei router
│   ├── auth.py                       JWT, ruoli, permessi
│   ├── credits.py                    Sistema crediti + transazioni
│   ├── claude_client.py              Training, generazione, umanizzazione
│   ├── ai_client.py                  Client unificato OpenAI + Claude
│   ├── anti_ai_processor.py          Algoritmo anti-AI (spaCy)
│   ├── thesis_routes.py              Generazione tesi (7 step)
│   ├── thesis_export.py              Export PDF/DOCX/TXT/MD
│   ├── helper_calcifer.py            Assistente Calcifer (anti prompt injection)
│   ├── compilatio_client.py          Detector AI integration
│   ├── pagopa_client.py              SOAP client SolutionPA (zeep)
│   ├── pagopa_routes.py              Endpoint utente /api/payments/*
│   ├── pagopa_webhooks.py            Push esito (REST registerPayment)
│   ├── admin_routes.py               Pannello admin (utenti, costi, pagamenti...)
│   ├── session_manager.py            Sessioni Claude isolate, thread-safe
│   ├── job_manager.py                Job queue async con semaforo
│   ├── db_models.py                  SQLAlchemy ORM
│   ├── models.py                     Pydantic request/response
│   ├── config.py                     Configurazione centralizzata
│   └── migrations/*.sql              Migration SQL idempotenti
│
└── frontend/                         React + Vite
    ├── src/
    │   ├── pages/                    Dashboard, Train, Generate, Humanize,
    │   │                             ThesisGenerator, Admin, DetectorAI,
    │   │                             ResearchSearch, BuyCredits,
    │   │                             PaymentReturn, PaymentHistory
    │   ├── components/               Helper (Calcifer), CreditEstimatePreview,
    │   │                             ApiCostEstimate, thesis/, admin/
    │   ├── context/                  AuthContext (JWT, permessi)
    │   └── services/api.js           Client Axios
    └── vite.config.js
```

### Flusso job (training/generation/humanization)

```
Client → POST /train|/generate|/humanize
   → JobManager crea job (semaforo MAX_CONCURRENT_JOBS)
   → background task → ClaudeClient → Anthropic API
   → polling GET /jobs/{job_id} fino a status=completed
   → GET /results/{job_id} per scaricare il risultato
```

### Flusso PagoPA

```
Utente → /credits/buy → POST /api/payments/initiate
   → pdpCaricaPagamentoInAttesa (SOAP) → IUV
   → pdpAttivaRPT (SOAP) → checkout_url
   → redirect Checkout pagoPA → utente paga
   → SolutionPA push: POST /api/pagopa/esito (Basic Auth, idempotente)
       → SELECT FOR UPDATE su payment_orders
       → status=PAID, add_credits(transaction_type='pagopa_purchase')
   → /payments/return polling → UI mostra "+N crediti accreditati"
```

---

## Setup sviluppo

### Backend

```bash
cd backend

python3 -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download it_core_news_sm

cp .env.example .env
# Configura ANTHROPIC_API_KEY, OPENAI_API_KEY, SUPABASE_URL, ecc.

# Esegui le migration in ordine
psql "$DATABASE_URL" < migrations/01_init.sql
# ... (tutte le migration nella cartella, in ordine numerico)

python api.py
```

Backend su `http://localhost:8000`, Swagger su `/docs`.

### Frontend

```bash
cd frontend
npm install

cp .env.example .env             # configura VITE_API_URL=http://localhost:8000

npm run dev                      # sviluppo: http://localhost:5173
# oppure
npm run start                    # build + preview su :3000 (consigliato)
```

> **Importante**: in produzione **non** usare `npm run dev`. Il dev server Vite causa refresh automatici che fanno perdere lo stato all'utente. Usa `npm run start` (build + preview) o servi `dist/` con nginx.

---

## Configurazione

### Variabili backend (`.env`)

| Variabile | Descrizione | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Chiave Claude (obbligatoria) | — |
| `OPENAI_API_KEY` | Chiave OpenAI (per tesi) | — |
| `SUPABASE_URL` | URL DB PostgreSQL | — |
| `SUPABASE_ANON_KEY` | Chiave anonima Supabase | — |
| `DATABASE_URL` | Connection string PostgreSQL | — |
| `SECRET_KEY` | JWT signing key (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) | — |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validità access token | 30 |
| `MAX_CONCURRENT_JOBS` | Job paralleli massimi | 10 |
| `SESSION_CLEANUP_HOURS` | Cleanup sessioni non addestrate | 24 |
| `RATE_LIMIT_PER_MINUTE` | Rate limit API | 60 |
| `CORS_ORIGINS` | Domini consentiti (csv) | — |
| `HOST` / `PORT` | Bind server | `0.0.0.0` / `8000` |

### Variabili PagoPA / SolutionPA

| Variabile | Descrizione |
|---|---|
| `PAGOPA_TEST_MODE` | `true` per ambiente di collaudo |
| `PAGOPA_WSDL_URL` | URL WSDL DataProvider |
| `PAGOPA_USERNAME` / `PAGOPA_PASSWORD` | Credenziali SOAP outbound (verso SolutionPA) |
| `PAGOPA_DOMINIO` | Codice fiscale ente (es. `80005570561` per ERSAF) |
| `PAGOPA_UB` | Unità Business (es. `ERSAFQUOTATST`) |
| `PAGOPA_COD_TRIBUTO` | Codice tributo (es. `ERSAFINCATST`) |
| `PAGOPA_RETURN_URL_BASE` | URL base per redirect post-checkout |
| `PAGOPA_NOTIFY_AUTH_USER` / `PAGOPA_NOTIFY_AUTH_PASS` | Basic Auth inbound (SolutionPA → nostro webhook) |
| `PAGOPA_POSITION_TTL_DAYS` | TTL posizioni di pagamento (default 60) |
| `PAGOPA_SOAP_TIMEOUT` | Timeout SOAP secondi (default 30) |

### Variabili frontend (`.env`)

| Variabile | Descrizione | Default |
|---|---|---|
| `VITE_API_URL` | URL backend | `http://localhost:8000` |

---

## Deployment in produzione

### 1. Server prep (Ubuntu 22.04+)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git nginx postgresql-client

# Node.js 20 LTS (Vite 7 richiede 20.19+ o 22.12+)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verifica
python3 --version && node --version
```

### 2. Clone + setup

```bash
git clone <repo-url> ~/projects/StyleForge
cd ~/projects/StyleForge

# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download it_core_news_sm
cp .env.example .env && nano .env

# Frontend
cd ../frontend
npm install
echo "VITE_API_URL=https://api.tuodominio.it" > .env
npm run build                    # genera dist/
```

### 3. Systemd services

**`/etc/systemd/system/styleforge-backend.service`**
```ini
[Unit]
Description=StyleForge Backend
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/projects/StyleForge/backend
EnvironmentFile=/home/ubuntu/projects/StyleForge/backend/.env
Environment=PATH=/home/ubuntu/projects/StyleForge/backend/venv/bin
ExecStart=/home/ubuntu/projects/StyleForge/backend/venv/bin/uvicorn api:app \
    --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/styleforge-frontend.service`** (serve la build prodotta)
```ini
[Unit]
Description=StyleForge Frontend
After=network.target styleforge-backend.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/projects/StyleForge/frontend
ExecStart=/usr/bin/npm run preview -- --host 0.0.0.0 --port 3000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Attivazione**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now styleforge-backend styleforge-frontend
sudo systemctl status styleforge-backend
```

**Log**:
```bash
sudo journalctl -u styleforge-backend -f
sudo journalctl -u styleforge-frontend -f
```

### 4. Nginx reverse proxy + SSL

**`/etc/nginx/sites-available/styleforge`**
```nginx
server {
    listen 80;
    server_name tuodominio.it;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tuodominio.it;

    # SSL via certbot (popolato da `certbot --nginx`)
    ssl_certificate /etc/letsencrypt/live/tuodominio.it/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tuodominio.it/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }
}

server {
    listen 443 ssl http2;
    server_name api.tuodominio.it;

    ssl_certificate /etc/letsencrypt/live/api.tuodominio.it/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.tuodominio.it/privkey.pem;

    client_max_body_size 50M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/styleforge /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL con Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tuodominio.it -d api.tuodominio.it
```

### 5. Firewall

```bash
sudo ufw allow 22/tcp           # ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 6. Update procedure

```bash
cd ~/projects/StyleForge
git pull

# Backend: nuove dipendenze + migration
cd backend
source venv/bin/activate
pip install -r requirements.txt
psql "$DATABASE_URL" < migrations/<nuova_migration>.sql

# Frontend: rebuild
cd ../frontend
npm install
npm run build

sudo systemctl restart styleforge-backend styleforge-frontend
```

---

## API esterna

API REST per integrazioni programmatiche (umanizzazione e correzione anti-AI). Documentazione interattiva su `https://api.tuodominio.it/docs`.

**Autenticazione**: header `X-API-Key: sf_k_...` (le chiavi vengono create dall'admin nel pannello, mostrate una sola volta, salvate come hash SHA-256). Rate limit configurabile per chiave (default 30 req/min).

### Endpoint principali

| Endpoint | Descrizione |
|---|---|
| `POST /api/v1/humanize` | Umanizzazione completa (richiede sessione addestrata) |
| `POST /api/v1/anti-ai-correct` | Correzione anti-AI conservativa (no sessione) |
| `GET /api/v1/jobs/{job_id}` | Polling stato job |

### Flusso tipico

```bash
# 1. Avvia job
curl -X POST https://api.tuodominio.it/api/v1/humanize \
  -H "X-API-Key: sf_k_..." \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session_abc","text":"Testo da umanizzare..."}'
# → {"job_id":"job_xyz","status":"pending"}

# 2. Polling (ogni 3-5s)
curl https://api.tuodominio.it/api/v1/jobs/job_xyz \
  -H "X-API-Key: sf_k_..."
# → {"status":"completed","result":"Testo umanizzato..."}
```

### Codici di errore

| Codice | Significato |
|---|---|
| `401` | API key mancante/invalida |
| `403` | Chiave revocata, scaduta o account disabilitato |
| `404` | Sessione o job non trovato |
| `422` | Parametri non validi (es. testo < 50 char) |
| `429` | Rate limit superato (header `Retry-After: 60`) |
| `500` | Errore interno |

---

## Sicurezza

- **JWT** con access token (30 min) + refresh token (7 gg)
- **Ruoli e permessi granulari** (admin/utente/custom): `train`, `generate`, `humanize`, `thesis`, `manage_templates`, `compilatio_scan`, `compilatio_scan_thesis`, `pagopa_admin`
- **Calcifer anti prompt injection**: sanitizzazione input, system prompt blindato, conversazioni isolate per utente
- **API key SHA-256**: la chiave completa non viene mai salvata, solo l'hash
- **Webhook PagoPA**: Basic Auth dedicata (`PAGOPA_NOTIFY_AUTH_*`), idempotente con `SELECT FOR UPDATE` per race-safety
- **Rate limiting** per utente/chiave
- **CORS** configurabile per ambiente
- **Validazione input** Pydantic + sanitizzazione path file
- **CF/P.IVA** validati con regex (16 alfanumerici / 11 numerici)
- **PII**: codice fiscale e dati pagatore mascherati nei log e nel pannello admin

---

## Troubleshooting

### Backend non si avvia
- Verifica `ANTHROPIC_API_KEY` in `.env`
- Verifica modello spaCy: `python -c "import spacy; spacy.load('it_core_news_sm')"`
- Verifica DB: `psql "$DATABASE_URL" -c '\dt'`

### Job rimane in `pending`
```bash
# Aumenta concorrenza
echo "MAX_CONCURRENT_JOBS=20" >> backend/.env
sudo systemctl restart styleforge-backend
```

### Frontend non si connette al backend
- Verifica `VITE_API_URL` nel `.env` frontend (deve essere ricostruito dopo modifica: `npm run build`)
- Verifica CORS nel backend (`CORS_ORIGINS`)
- Health check: `curl http://localhost:8000/health`

### Porta 8000 occupata
```bash
lsof -ti:8000 | xargs kill -9
```

### Migration PagoPA fallisce con `null value in column "is_active"`
La tabella `credit_packages` esisteva da un tentativo precedente senza i `DEFAULT`. La migration `20_pagopa_payments.sql` è ora self-healing: rieseguila e correggerà i default mancanti automaticamente.

### Webhook PagoPA non accredita i crediti
1. Verifica nei log che SolutionPA stia chiamando `POST /api/pagopa/esito` (cerca `Basic Auth` 401 in nginx access log)
2. Coordinati con SolutionPA per le credenziali Basic Auth (`PAGOPA_NOTIFY_AUTH_*`)
3. Controlla `pagopa_events` table: ogni push lascia traccia anche se l'ordine non è trovato
4. Test idempotenza: re-delivery dello stesso IUV non deve doppiare l'accredito

### Detector AI rileva colori invertiti
Risolto nel commit `fd2db70`: Compilatio invia `types: [...]` (array) per i POI, il parser ora controlla `types` / `type` / `category` / `kind` con priorità AI > similarity > quotation.

### PDF report con caratteri sovrapposti
Risolto: caratteri Unicode fuori dal set Helvetica Base 14 (smart quotes, em-dash) vengono normalizzati con sostituzione length-preserving prima del rendering.

---

## Licenza

MIT
