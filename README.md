# StyleForge

**Piattaforma AI per la generazione e umanizzazione di contenuti accademici e professionali.**

StyleForge addestra modelli AI sul tuo stile di scrittura personale, permettendoti di generare contenuti originali, umanizzare testi AI e creare tesi complete — il tutto con un'interfaccia web moderna e un assistente integrato.

---

## Funzionalita

### Addestramento Stilistico
Carica un PDF con esempi del tuo stile di scrittura. L'AI analizza il testo e impara le tue peculiarita linguistiche, la struttura delle frasi e il vocabolario. Le sessioni addestrate restano disponibili per sempre.

### Generazione Contenuti
Genera articoli, saggi e relazioni nel tuo stile personale. Scegli argomento, lunghezza e destinatario — l'AI produce contenuti indistinguibili da quelli scritti da te.

### Umanizzazione Testi
Due modalita per rendere i testi AI non rilevabili dai detector:
- **Correzione Anti-AI**: micro-correzioni conservative che mantengono il 90%+ del testo originale. Non richiede sessione addestrata.
- **Umanizzazione con Profilo Stilistico**: riscrittura completa nel tuo stile personale. Richiede una sessione addestrata.

### Generazione Tesi
Procedura guidata in 7 step per creare tesi e documenti accademici completi:
1. **Parametri** — titolo, descrizione, stile, profondita, struttura
2. **Pubblico** — livello di conoscenza, settore, destinatari
3. **Allegati** — carica PDF, DOCX, TXT o link web come fonti di riferimento
4. **Capitoli** — l'AI genera la struttura, modificabile prima di confermare
5. **Sezioni** — l'AI genera le sezioni per ogni capitolo, modificabili
6. **Generazione** — il contenuto viene prodotto sezione per sezione con progresso in tempo reale
7. **Download** — anteprima e esportazione in PDF, DOCX, TXT o Markdown

### Calcifer — Assistente AI Integrato
Calcifer e l'assistente interattivo sempre disponibile in ogni pagina. Conosce tutte le funzionalita della piattaforma e guida gli utenti passo dopo passo. Include protezione anti prompt injection per un utilizzo sicuro in produzione.

### Pannello Amministrazione
- Gestione utenti, ruoli e permessi
- Configurazione costi crediti per ogni operazione
- Parametro di conversione EUR/crediti
- Gestione template di esportazione PDF
- Gestione chiavi API
- Statistiche di utilizzo

### Sistema Crediti
Ogni operazione ha un costo in crediti configurabile dall'admin:
- Stima crediti in tempo reale prima di ogni operazione (visibile a tutti gli utenti)
- Stima costo API in EUR (visibile solo agli admin)
- Crediti allegati calcolati per caratteri estratti
- Storico transazioni completo

---

## Architettura

```
StyleForge/
├── backend/                 # FastAPI + Python
│   ├── api.py              # Server REST principale
│   ├── auth.py             # Autenticazione JWT
│   ├── credits.py          # Sistema crediti
│   ├── claude_client.py    # Client Claude (addestramento, generazione, umanizzazione)
│   ├── ai_client.py        # Client AI unificato (OpenAI + Claude)
│   ├── anti_ai_processor.py # Algoritmo anti-AI post-processing
│   ├── thesis_routes.py    # Generazione tesi (7 step)
│   ├── helper_calcifer.py  # Assistente Calcifer
│   ├── session_manager.py  # Gestione sessioni
│   ├── job_manager.py      # Job queue asincroni
│   └── config.py           # Configurazione
│
└── frontend/                # React + Vite
    ├── src/
    │   ├── pages/          # Dashboard, Train, Generate, Humanize, ThesisGenerator, Admin
    │   ├── components/     # Helper (Calcifer), CreditEstimatePreview, ApiCostEstimate, thesis/
    │   ├── context/        # AuthContext (JWT, permessi, ruoli)
    │   └── services/       # Client API (Axios)
    └── vite.config.js
```

---

## Setup

### Prerequisiti
- Python 3.11+
- Node.js 18+
- PostgreSQL (Supabase)
- Chiave API Anthropic
- Chiave API OpenAI (per generazione tesi)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Configura: ANTHROPIC_API_KEY, OPENAI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, etc.

python api.py
```

Backend disponibile su `http://localhost:8000`
Documentazione API interattiva su `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install

cp .env.example .env
# Configura: VITE_API_URL=http://localhost:8000

# Sviluppo
npm run dev

# Produzione
npm run start    # build + serve su porta 3000
```

---

## Deploy in Produzione

### Frontend

In produzione il frontend deve essere servito come build statica, **non** con il dev server Vite:

```bash
cd frontend
npm run start    # esegue: vite build && vite preview (porta 3000)
```

Il dev server (`npm run dev`) causa refresh automatici della pagina che fanno perdere lo stato all'utente.

### Backend

```bash
cd backend
uvicorn api:app --workers 4 --host 0.0.0.0 --port 8000
```

### Reverse Proxy (nginx/openresty)

Il frontend e il backend girano su porte separate. Configura il reverse proxy per instradare:
- `dominio.com` → frontend (porta 3000)
- `api.dominio.com` → backend (porta 8000)

---

## Tecnologie

| Layer | Stack |
|-------|-------|
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, PostgreSQL (Supabase) |
| **AI** | Anthropic Claude Opus 4.6 (addestramento, generazione, umanizzazione), OpenAI o3 (tesi) |
| **Frontend** | React 19, Vite 7, Tailwind CSS 4, React Router 7, Axios |
| **Auth** | JWT (access + refresh token), ruoli e permessi granulari |
| **Assistente** | Calcifer (Claude Haiku 4.5, anti prompt injection) |

---

## Configurazione

### Variabili d'Ambiente Backend

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Chiave API Anthropic (obbligatoria) | — |
| `OPENAI_API_KEY` | Chiave API OpenAI (per tesi) | — |
| `SUPABASE_URL` | URL database PostgreSQL | — |
| `SUPABASE_ANON_KEY` | Chiave anonima Supabase | — |
| `MAX_CONCURRENT_JOBS` | Job paralleli massimi | 10 |
| `SESSION_CLEANUP_HOURS` | Cleanup sessioni non addestrate (ore) | 24 |
| `RATE_LIMIT_PER_MINUTE` | Rate limit API per minuto | 60 |

### Variabili d'Ambiente Frontend

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `VITE_API_URL` | URL del backend | `http://localhost:8000` |

---

## Sicurezza

- **Autenticazione JWT** con access token (30 min) e refresh token (7 giorni)
- **Ruoli e permessi** granulari (admin, utente, custom)
- **Calcifer** protetto da prompt injection (sanitizzazione input, system prompt blindato)
- **Conversazioni isolate** per utente (nessuna condivisione stato tra utenti)
- **Rate limiting** configurabile
- **CORS** configurabile per produzione

---

## Documentazione Aggiuntiva

- `backend/README_API.md` — Documentazione endpoints API
- `backend/ARCHITECTURE.md` — Architettura dettagliata del backend
- `backend/.env.example` — Template variabili d'ambiente

---

## Licenza

MIT
