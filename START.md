# 🚀 START - StyleForge

Guida rapida per avviare StyleForge in 2 minuti.

## 📋 Prerequisiti

- Python 3.11+
- Node.js 18+
- Chiave API Anthropic

## 🔧 Setup (5 minuti)

### 1. Backend

```bash
cd backend

# Setup virtuale
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

# Installa
pip install -r requirements.txt

# Configura
cp .env.example .env
nano .env  # Aggiungi ANTHROPIC_API_KEY

# Avvia
python api.py
```

✅ Backend running su: **http://localhost:8000**

### 2. Frontend

```bash
cd ../frontend

# Installa
npm install

# Configura (opzionale, già configurato)
# cp .env.example .env
# nano .env  # Cambia VITE_ACCESS_CODE se vuoi

# Avvia
npm run dev
```

✅ Frontend running su: **http://localhost:5173**

## 🎯 Primo Utilizzo

### 1. Login
- Apri: http://localhost:5173
- Codice: `styleforge2025`

### 2. Training
1. Click "Nuovo Training"
2. Carica PDF (es. libro, articolo)
3. Click "Avvia Training"
4. Attendi completamento (~5min)

### 3. Genera
1. Click "Genera Contenuto"
2. Inserisci argomento
3. Specifica parole (es. 1000)
4. Click "Genera"
5. Scarica risultato!

## ⚡ Quick Commands

```bash
# Backend
cd backend && python api.py

# Frontend
cd frontend && npm run dev

# Build Frontend
cd frontend && npm run build
```

## 🔑 Configurazione Minima

### backend/.env
```env
ANTHROPIC_API_KEY=sk-ant-api03-xxx
```

### frontend/.env
```env
VITE_ACCESS_CODE=styleforge2025  # Cambia questo!
VITE_API_URL=http://localhost:8000
```

## ✅ Verifica Installazione

```bash
# Backend health
curl http://localhost:8000/health

# Frontend
open http://localhost:5173
```

## 🐛 Problemi Comuni

**Backend non si avvia:**
```bash
# Verifica API key
cat backend/.env | grep ANTHROPIC_API_KEY
```

**Frontend non si connette:**
```bash
# Verifica backend
curl http://localhost:8000/health

# Verifica CORS (deve essere configurato)
```

**Job rimane in pending:**
```bash
# Aumenta job concorrenti in backend/.env
echo "MAX_CONCURRENT_JOBS=20" >> backend/.env
```

## 📚 Documentazione Completa

- **API**: `backend/README_API.md`
- **Frontend**: `frontend/README.md`
- **Architettura**: `backend/ARCHITECTURE.md`
- **Quick Start**: `backend/QUICKSTART.md`

## 🎉 Pronto!

Ora sei pronto per usare StyleForge:
1. Login → http://localhost:5173
2. Carica un PDF
3. Genera contenuti!

---

**Help?** Leggi la doc completa in `README.md`
