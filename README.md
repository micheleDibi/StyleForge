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
8. [Anti-rilevamento AI (tesi)](#anti-rilevamento-ai-tesi)
9. [Sicurezza](#sicurezza)
10. [Troubleshooting](#troubleshooting)

---

## Funzionalità

### Core
- **Addestramento stilistico** — carica un PDF di esempi e l'AI impara il tuo stile (struttura frasi, vocabolario, tono).
- **Generazione contenuti** — articoli, saggi, relazioni nel tuo stile, scegliendo argomento, lunghezza, destinatario.
- **Umanizzazione testi** — due modalità: correzione anti-AI conservativa (no sessione richiesta) o riscrittura completa con sessione addestrata.
- **Generazione tesi** — wizard in 9 step (parametri → pubblico → allegati → paper → knowledge base → capitoli → sezioni → generazione → export PDF/DOCX/TXT/MD).
- **Knowledge Base per tesi (second brain)** — documenti e paper caricati vengono ingeriti in un wiki per-tesi (LLM Wiki, SDK Anthropic); la generazione attinge solo alle fonti selezionate via retriever TF-IDF. L'utente vede le "Informazioni estratte dai documenti" e un report di lint.
- **Anti-rilevamento AI (tesi)** — ogni sezione generata passa per una parafrasi controllata ricorsiva (stile DIPPER) seguita da un pass algoritmico register-safe, preservando citazioni e note. Vedi [Anti-rilevamento AI (tesi)](#anti-rilevamento-ai-tesi).
- **Detector AI** — scansione AI/plagio integrata via Compilatio con report PDF custom.
- **Ricerca accademica** — paper e riviste su un argomento (OpenAlex, Semantic Scholar, Crossref), con riassunti AI.
- **Image to Video** (admin) — generazione video da immagini (MiniMax).
- **Registrazione con verifica email** — alla registrazione viene inviato un link di conferma (token monouso, hash SHA-256 su DB); l'accesso resta bloccato finché l'email non è verificata. Reset password e inviti usano lo stesso meccanismo.

### Calcifer
Assistente AI integrato sempre disponibile in ogni pagina. Conosce tutte le funzionalità e guida gli utenti passo-passo. Protetto da prompt injection (system prompt blindato, sanitizzazione input).

### Pannello admin
- Gestione utenti, ruoli e permessi granulari
- Configurazione costi crediti per ogni operazione (admin-editable runtime)
- Parametro EUR/credito
- Template di esportazione PDF (header/footer/copertina personalizzabili)
- API key management
- **Listini** — gestione dei pacchetti crediti (CRUD) e del tasso EUR/credito

### Sistema crediti
Ogni operazione ha un costo configurabile. Stima crediti in tempo reale prima dell'azione, costo API in EUR (solo admin), storico transazioni completo. Le tesi si pagano **per step** del wizard (capitoli, sezioni, generazione contenuto, più l'eventuale analisi documenti/paper della Knowledge Base): ogni step ha una **quota fissa + uno scaling** sulla dimensione (caratteri degli allegati, numero di capitoli/sezioni, parole target). Si paga solo per gli step effettivamente eseguiti e gli step falliti o annullati vengono rimborsati automaticamente. Anche la ricerca accademica (ricerca, riassunto, suggerimento keyword) è misurata. Tutti i valori sono modificabili dall'admin a runtime.

### Acquisto crediti
I pacchetti crediti sono mostrati agli utenti come **listino** (pagina "Acquista Crediti", sola lettura). Non è integrato un pagamento online: l'accredito dei crediti viene effettuato manualmente dall'amministratore. Pacchetti e tasso EUR/credito si gestiscono dalla scheda admin **Listini**.

---

## Stack tecnologico

| Layer | Stack |
|---|---|
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, PostgreSQL (Supabase) |
| **AI** | Anthropic Claude Opus 4.8 (training, generate, humanize e **tesi di default**; provider OpenAI o3 selezionabile per le tesi via `THESIS_AI_PROVIDER=openai`), Claude Haiku 4.5 (Calcifer) |
| **Frontend** | React 19, Vite 7, Tailwind CSS 4, React Router 7, Axios |
| **Auth** | JWT (access 30min + refresh 7gg), ruoli e permessi |
| **NLP** | spaCy (`it_core_news_sm`) per algoritmo anti-AI |
| **PDF** | PyMuPDF per export e report Detector AI |

**Prerequisiti**: Python 3.11+, Node.js **20.19+ o 22.12+** (Vite 7 lo richiede), PostgreSQL, chiave Anthropic (obbligatoria). La chiave OpenAI serve solo se si imposta `THESIS_AI_PROVIDER=openai` per generare le tesi con o3.

---

## Architettura

```
StyleForge/
├── backend/                          FastAPI + Python
│   ├── api.py                        Server REST principale, wire dei router
│   ├── auth.py / auth_routes.py      JWT, ruoli, permessi + endpoint di autenticazione
│   ├── email_service.py             Invio email + token monouso (SHA-256: verifica/reset/invito)
│   ├── api_key_auth.py              Autenticazione via header X-API-Key (accesso esterno)
│   ├── external_api_routes.py       API pubblica protetta da API key
│   ├── credits.py                    Crediti + transazioni (tesi per-step: quota fissa + scaling, rimborsi)
│   ├── claude_client.py              Training, generazione, umanizzazione (Claude)
│   ├── ai_client.py                  Client unificato OpenAI/Claude + parafrasi controllata (anti-AI)
│   ├── openai_client.py             Client OpenAI (reasoning o3)
│   ├── anti_ai_processor.py          Pass algoritmico anti-AI register-safe (spaCy)
│   ├── thesis_routes.py              Generazione tesi (9 step) + export PDF/DOCX/TXT/MD
│   ├── thesis_prompts.py            Prompt builder della pipeline tesi
│   ├── attachment_processor.py      Estrazione testo dagli allegati
│   ├── llm_wiki/                     Second-brain per-tesi (SDK Anthropic)
│   │   ├── wiki_runner.py           Orchestrazione ingest + lint del wiki
│   │   ├── wiki_workspace.py        FS layer (bootstrap, materialize, lettura info estratte)
│   │   ├── wiki_retriever.py        build_context (TF-IDF) per i prompt di generazione
│   │   ├── wiki_tools.py            Tool Anthropic read/write sandboxati
│   │   └── paper_downloader.py      Download PDF dei paper (fallback abstract)
│   ├── research_routes.py           Ricerca accademica multi-provider
│   ├── research_providers/          OpenAlex, Semantic Scholar, Crossref
│   ├── research_summarizer.py       Riassunti AI dei risultati di ricerca
│   ├── helper_calcifer.py            Assistente Calcifer (anti prompt injection)
│   ├── compilatio_service.py         Detector AI (Compilatio) + report PDF custom
│   ├── video_routes.py / minimax_service.py   Image-to-video (MiniMax, admin)
│   ├── template_service.py          CRUD template export + applicazione a PDF/DOCX
│   ├── packages_routes.py           Listino pacchetti crediti (vetrina utente)
│   ├── admin_routes.py               Pannello admin (utenti, costi, listini...)
│   ├── distributor_routes.py         Dashboard distributore (sola lettura)
│   ├── i18n_routes.py               Multi-lingua (i18n), traduzioni AI admin-only
│   ├── session_manager.py            Sessioni Claude isolate, thread-safe
│   ├── job_manager.py                Job queue async con semaforo
│   ├── database.py                  Engine/sessione SQLAlchemy
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
    │   │                             ApiCostEstimate, thesis/ (WikiExtractedInfo...), admin/
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
| `OPENAI_API_KEY` | Chiave OpenAI (solo se `THESIS_AI_PROVIDER=openai`) | — |
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

### Variabili generazione tesi e anti-rilevamento AI

| Variabile | Descrizione | Default |
|---|---|---|
| `THESIS_AI_PROVIDER` | Provider di generazione del contenuto tesi: `claude` o `openai` | `claude` |
| `THESIS_CLAUDE_MODEL` | Modello Claude per le tesi | `claude-opus-4-8` |
| `OPENAI_MODEL_ID` | Modello OpenAI per le tesi (se provider `openai`) | `o3` |
| `THESIS_ANTI_AI_ENABLED` | Master switch della pipeline anti-rilevamento | `true` |
| `THESIS_PARAPHRASE_ENABLED` | Stage 0: parafrasi controllata ricorsiva (leva principale) | `true` |
| `THESIS_PARAPHRASE_ROUNDS` | Numero di passate di parafrasi ricorsiva | `2` |
| `THESIS_PARAPHRASE_MODEL` | Modello Claude per la parafrasi controllata | `claude-opus-4-8` |
| `THESIS_GEN_TEMPERATURE` | Temperatura di generazione (più alta = più varietà) | `1.0` |
| `THESIS_GEN_TOP_P` | top_p / nucleus sampling della generazione | `0.95` |
| `THESIS_ALGO_ENABLED` | Stage 2: pass algoritmico register-safe (`anti_ai_processor`) | `true` |
| `THESIS_ANTI_AI_PROFILE` | Profilo del pass algoritmico | `academic` |
| `THESIS_REWRITE_ENABLED` | Stage 1: riscrittura de-AI via LLM (legacy, OFF di default) | `false` |

> Come funzionano questi stage è spiegato nella sezione [Anti-rilevamento AI (tesi)](#anti-rilevamento-ai-tesi).

### Variabili email / SMTP (verifica registrazione, reset, invito)

| Variabile | Descrizione | Default |
|---|---|---|
| `SMTP_HOST` | Host SMTP. **Vuoto = email non inviate**, il link viene loggato (utile in sviluppo) | `""` |
| `SMTP_PORT` | Porta SMTP (587 = STARTTLS; OVH non usa la 465) | `587` |
| `SMTP_USER` / `SMTP_PASSWORD` | Credenziali SMTP | `""` |
| `SMTP_USE_SSL` | SSL diretto invece di STARTTLS | `false` |
| `MAIL_FROM` / `MAIL_FROM_NAME` | Mittente delle email | `noreply@styleforge.us` / `StyleForge` |
| `FRONTEND_BASE_URL` | URL base del frontend per i link nelle email | `https://app.styleforge.us` |

### Variabili LLM Wiki (Knowledge Base per tesi)

| Variabile | Descrizione | Default |
|---|---|---|
| `WIKI_CLAUDE_MODEL` | Modello Claude per ingest/lint del wiki | `claude-opus-4-8` |
| `WIKI_MAX_SOURCES` | Max fonti raw per tesi (limita il costo dell'ingest) | `15` |
| `WIKI_INGEST_TIMEOUT_SEC` | Timeout duro del job di ingest (oltre → `failed`) | `900` |
| `WIKI_INGEST_BATCH_SIZE` | Fonti per turno dell'SDK durante l'ingest | `5` |

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

## Anti-rilevamento AI (tesi)

Ogni sezione di tesi generata viene fatta passare per una pipeline anti-rilevamento prima di essere salvata (`_apply_anti_ai` in `thesis_routes.py`). L'obiettivo è abbassare il punteggio di **"Rilevamento AI"** dei detector (Compilatio, GPTZero, Turnitin…) mantenendo registro accademico, citazioni e lunghezza. In produzione questo ha portato il punteggio da **~61% a ~7%**.

### Il problema

Il plagio (similitudini) era già <1%: il punteggio alto era tutto **"AI-generated"**. I detector moderni **non** si basano solo su perplessità/burstiness: sono **classificatori neurali addestrati** sulla distribuzione tipica dei testi LLM. Per questo i ritocchi di superficie (sinonimi, virgole, micro-imperfezioni) da soli non bastano, e una riscrittura generica "rendi umano" è addirittura controproducente, perché riavvicina il testo alla distribuzione che il classificatore conosce.

### La leva principale: parafrasi controllata ricorsiva (DIPPER-style)

La ricerca (DIPPER, Sadasivan et al.) indica che la leva efficace è una **parafrasi controllata** che agisce su due manopole — **massima diversità lessicale** + **riordino strutturale di frasi e blocchi** — applicata in modo **ricorsivo** (l'effetto cresce con le passate). È esattamente ciò che fa `controlled_paraphrase` in `ai_client.py`:

- prompt che impone esplicitamente di **non ricalcare gli n-gram** dell'originale (sequenze di 3-4 parole), di sostituire verbi/sostantivi/aggettivi con sinonimi formali e di **cambiare l'ordine** di frasi e periodi (spezzando/fondendo per aumentare la burstiness);
- **ricorsiva**: di default **2 passate** (`THESIS_PARAPHRASE_ROUNDS`), la seconda parafrasa l'output della prima;
- eseguita con **Claude Opus a temperatura ~1.0** (alta diversità): a differenza dei modelli reasoning OpenAI (o3), Claude rispetta `temperature`/`top_p`;
- **vincoli inderogabili**: significato invariato, **registro accademico formale**, citazioni `[x]` e note `{{nota: ...}}` intatte, numeri/date/nomi identici, e **lunghezza ≥ originale** (floor interno al 90%: se una passata accorcia troppo, viene scartata).

### La pipeline completa (per sezione)

1. **Generazione del primo draft meno rilevabile** — il contenuto si genera di **default con Claude** (`THESIS_AI_PROVIDER=claude`) a `temperature`/`top_p` alti per più varietà; nel prompt vengono iniettati 1-2 brevi **esempi di prosa umana reale** estratti dalle fonti della tesi ("imita ritmo e lessico, non i contenuti" — anti-plagio), e ogni sezione usa un seed diverso per rompere la firma uniforme a livello di documento.
2. **Stage 0 — Parafrasi controllata ricorsiva** (la leva principale descritta sopra). `THESIS_PARAPHRASE_ENABLED`.
3. **Stage 1 — Riscrittura de-AI via LLM** *(legacy, OFF di default)*: una riscrittura "generica" non abbassa il punteggio, quindi è disattivata (`THESIS_REWRITE_ENABLED=false`).
4. **Stage 2 — Pass algoritmico register-safe** (`anti_ai_processor.py`, profilo `academic`): complementare e a costo zero. Rompe gli n-gram ad alta frequenza tipici dei testi AI sostituendoli con **alternative formali** ("è importante notare che" → "va osservato che", "questo significa che" → "ne consegue che"…), perturba il lessico con sinonimi formali, varia la perplessità con soli split strutturali (niente colloquialismi, niente modifiche ai titoli/TOC). Le citazioni `[x]` sono protette prima di ogni trasformazione e ripristinate dopo.

La bibliografia **non** viene parafrasata né processata (è una lista formale). Ogni stage è disattivabile da `.env`; il master switch è `THESIS_ANTI_AI_ENABLED`.

### Costo e onestà

La parafrasi ricorsiva aggiunge ~2 chiamate AI per sezione (è il motivo per cui la generazione contenuto è uno step a pagamento a sé). Nota di metodo: contro un classificatore addestrato **nessun metodo single-pass garantisce** un punteggio basso — questa pipeline massimizza la riduzione realistica senza un loop guidato dal detector. Il risultato osservato (~7%) può variare per argomento e lunghezza; le manopole (`THESIS_PARAPHRASE_ROUNDS`, `THESIS_GEN_TEMPERATURE`, modello) permettono di spingere oltre se serve.

---

## Sicurezza

- **JWT** con access token (30 min) + refresh token (7 gg)
- **Verifica email obbligatoria**: registrazione con token monouso (hash SHA-256 in `email_tokens`); login e refresh sono bloccati finché l'email non è confermata
- **Ruoli e permessi granulari** (admin/utente/custom): `train`, `generate`, `humanize`, `thesis`, `manage_templates`, `compilatio_scan`, `compilatio_scan_thesis`
- **Calcifer anti prompt injection**: sanitizzazione input, system prompt blindato, conversazioni isolate per utente
- **API key SHA-256**: la chiave completa non viene mai salvata, solo l'hash
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

### Detector AI rileva colori invertiti
Risolto nel commit `fd2db70`: Compilatio invia `types: [...]` (array) per i POI, il parser ora controlla `types` / `type` / `category` / `kind` con priorità AI > similarity > quotation.

### PDF report con caratteri sovrapposti
Risolto: caratteri Unicode fuori dal set Helvetica Base 14 (smart quotes, em-dash) vengono normalizzati con sostituzione length-preserving prima del rendering.

---

## Licenza

MIT
