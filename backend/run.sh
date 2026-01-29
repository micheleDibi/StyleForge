#!/bin/bash

# Script di avvio per StyleForge API

set -e

echo "=== StyleForge API - Avvio ==="

# Controlla se il virtual environment esiste
if [ ! -d "venv" ]; then
    echo "Virtual environment non trovato. Creazione in corso..."
    python3 -m venv venv
fi

# Attiva virtual environment
echo "Attivazione virtual environment..."
source venv/bin/activate

# Installa/aggiorna dipendenze
echo "Installazione dipendenze..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Controlla file .env
if [ ! -f ".env" ]; then
    echo "ATTENZIONE: File .env non trovato!"
    echo "Copia .env.example in .env e configura le variabili necessarie."
    exit 1
fi

# Controlla prompt_addestramento.txt
if [ ! -f "prompt_addestramento.txt" ]; then
    echo "ATTENZIONE: File prompt_addestramento.txt non trovato!"
    echo "Crea il file con il prompt di addestramento."
    exit 1
fi

# Crea directory necessarie
mkdir -p uploads results

# Avvia server
echo "Avvio server..."
echo "Documentazione disponibile su: http://localhost:8000/docs"
echo ""

if [ "$1" = "dev" ]; then
    echo "Modalità: SVILUPPO (con reload)"
    uvicorn api:app --reload --host 0.0.0.0 --port 8000
elif [ "$1" = "prod" ]; then
    echo "Modalità: PRODUZIONE"
    uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
else
    echo "Modalità: STANDARD"
    python api.py
fi
