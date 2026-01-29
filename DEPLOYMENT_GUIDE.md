# Guida al Deployment di StyleForge su Server

Questa guida ti permetterà di mettere online l'applicazione StyleForge (frontend React + backend FastAPI) su un server Linux utilizzando screen per mantenere i processi in esecuzione.

## Prerequisiti sul Server

Il server deve avere installato:
- Ubuntu 20.04+ / Debian 11+ (o altra distribuzione Linux)
- Python 3.9+
- Node.js 20.19+ o 22.12+ (richiesto da Vite 7.x)
- npm
- screen
- git (per clonare il repository)

## 1. Preparazione del Server

### 1.1 Connessione al Server

```bash
ssh utente@indirizzo-server
```

### 1.2 Installazione dei Prerequisiti

```bash
# Aggiorna il sistema
sudo apt update && sudo apt upgrade -y

# Installa Python e pip
sudo apt install -y python3 python3-pip python3-venv

# Installa Node.js 20 LTS e npm (tramite NodeSource)
# IMPORTANTE: Vite 7.x richiede Node.js 20.19+ o 22.12+
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Installa screen
sudo apt install -y screen

# Installa git
sudo apt install -y git

# Verifica le installazioni
python3 --version
node --version
npm --version
screen --version
```

## 2. Clonazione del Progetto

```bash
# Crea una directory per i progetti (se non esiste)
mkdir -p ~/projects
cd ~/projects

# Clona il repository (sostituisci con il tuo URL)
git clone <URL_DEL_TUO_REPOSITORY> StyleForge
cd StyleForge
```

Se non hai un repository Git, carica i file via SCP:
```bash
# Dal tuo computer locale
scp -r /path/to/StyleForge utente@indirizzo-server:~/projects/
```

## 3. Configurazione del Backend

### 3.1 Setup dell'Ambiente Python

```bash
cd ~/projects/StyleForge/backend

# Crea un ambiente virtuale
python3 -m venv venv

# Attiva l'ambiente virtuale
source venv/bin/activate

# Aggiorna pip
pip install --upgrade pip

# Installa le dipendenze
pip install -r requirements.txt

# Scarica il modello spaCy (necessario per il backend)
python -m spacy download en_core_web_sm
```

### 3.2 Configurazione delle Variabili d'Ambiente

```bash
# Copia il file di esempio
cp .env.example .env

# Modifica il file .env con i tuoi valori
nano .env
```

Configura almeno queste variabili nel file `.env`:

```bash
# API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Database (Supabase o PostgreSQL)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
DATABASE_URL=postgresql://user:password@localhost:5432/styleforge

# Security
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Server Configuration
HOST=0.0.0.0
PORT=8000

# CORS
FRONTEND_URL=http://your-server-ip:3000
```

Per generare una SECRET_KEY sicura:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.3 Creazione delle Directory Necessarie

```bash
# Assicurati di essere nella directory backend
cd ~/projects/StyleForge/backend

# Crea le directory per uploads e results
mkdir -p uploads results
chmod 755 uploads results
```

## 4. Configurazione del Frontend

### 4.1 Installazione delle Dipendenze

```bash
cd ~/projects/StyleForge/frontend

# Installa le dipendenze
npm install
```

### 4.2 Configurazione dell'URL del Backend

Crea un file `.env` nella directory frontend:

```bash
nano .env
```

Aggiungi:
```bash
VITE_API_URL=http://your-server-ip:8000
```

### 4.3 Build del Frontend (Opzionale - se vuoi servire versione ottimizzata)

```bash
# Crea la build di produzione
npm run build

# La build sarà nella cartella dist/
```

## 5. Avvio con Screen

### 5.1 Avvio del Backend

```bash
# Crea una sessione screen per il backend
screen -S styleforge-backend

# Vai nella directory backend
cd ~/projects/StyleForge/backend

# Attiva l'ambiente virtuale
source venv/bin/activate

# Avvia il server FastAPI
python api.py

# Oppure con uvicorn direttamente
# uvicorn api:app --host 0.0.0.0 --port 8000

# Il backend ora è in esecuzione sulla porta 8000
```

Per uscire dalla sessione screen senza fermare il processo:
- Premi `Ctrl + A`, poi premi `D` (detach)

### 5.2 Avvio del Frontend

```bash
# Crea una sessione screen per il frontend
screen -S styleforge-frontend

# Vai nella directory frontend
cd ~/projects/StyleForge/frontend

# Avvia il server di sviluppo Vite
npm run dev -- --host 0.0.0.0 --port 3000

# Oppure se hai fatto la build, usa preview
# npm run preview -- --host 0.0.0.0 --port 3000
```

Per uscire dalla sessione screen senza fermare il processo:
- Premi `Ctrl + A`, poi premi `D` (detach)

## 6. Gestione delle Sessioni Screen

### 6.1 Comandi Utili di Screen

```bash
# Lista tutte le sessioni screen attive
screen -ls

# Riattaccarsi a una sessione
screen -r styleforge-backend
screen -r styleforge-frontend

# Se la sessione è ancora "attached", forza il riattacco
screen -rd styleforge-backend

# Terminare una sessione (dall'interno della sessione)
# Ctrl + D oppure exit

# Killare una sessione dall'esterno
screen -X -S styleforge-backend quit
```

### 6.2 Script di Gestione Rapida

Puoi creare degli script per semplificare la gestione:

#### Script di Avvio (`start.sh`)

```bash
nano ~/projects/StyleForge/start.sh
```

```bash
#!/bin/bash

echo "Avvio StyleForge Backend..."
screen -dmS styleforge-backend bash -c 'cd ~/projects/StyleForge/backend && source venv/bin/activate && python api.py'

echo "Attendo 5 secondi..."
sleep 5

echo "Avvio StyleForge Frontend..."
screen -dmS styleforge-frontend bash -c 'cd ~/projects/StyleForge/frontend && npm run dev -- --host 0.0.0.0 --port 3000'

echo "StyleForge avviato!"
echo "Backend: http://$(hostname -I | awk '{print $1}'):8000"
echo "Frontend: http://$(hostname -I | awk '{print $1}'):3000"
echo ""
echo "Usa 'screen -r styleforge-backend' per vedere il backend"
echo "Usa 'screen -r styleforge-frontend' per vedere il frontend"
```

#### Script di Stop (`stop.sh`)

```bash
nano ~/projects/StyleForge/stop.sh
```

```bash
#!/bin/bash

echo "Arresto StyleForge..."
screen -X -S styleforge-backend quit
screen -X -S styleforge-frontend quit
echo "StyleForge arrestato!"
```

#### Script di Restart (`restart.sh`)

```bash
nano ~/projects/StyleForge/restart.sh
```

```bash
#!/bin/bash

echo "Riavvio StyleForge..."
bash ~/projects/StyleForge/stop.sh
sleep 2
bash ~/projects/StyleForge/start.sh
```

Rendi gli script eseguibili:
```bash
chmod +x ~/projects/StyleForge/*.sh
```

## 7. Configurazione del Firewall

Assicurati che le porte siano aperte:

```bash
# Con ufw (Ubuntu/Debian)
sudo ufw allow 8000/tcp
sudo ufw allow 3000/tcp
sudo ufw status

# Con firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload
```

## 8. Accesso all'Applicazione

Una volta avviati entrambi i servizi:

- **Frontend**: `http://your-server-ip:3000`
- **Backend API**: `http://your-server-ip:8000`
- **Documentazione API**: `http://your-server-ip:8000/docs`

## 9. Monitoraggio e Log

### 9.1 Visualizzare i Log in Tempo Reale

```bash
# Riattaccarsi alla sessione e vedere i log
screen -r styleforge-backend
# oppure
screen -r styleforge-frontend

# Per uscire senza terminare: Ctrl+A poi D
```

### 9.2 Salvare i Log su File

Modifica gli script di avvio per salvare i log:

```bash
# Backend con log
screen -dmS styleforge-backend bash -c 'cd ~/projects/StyleForge/backend && source venv/bin/activate && python api.py 2>&1 | tee -a backend.log'

# Frontend con log
screen -dmS styleforge-frontend bash -c 'cd ~/projects/StyleForge/frontend && npm run dev -- --host 0.0.0.0 --port 3000 2>&1 | tee -a frontend.log'
```

## 10. Deployment in Produzione (Opzionale ma Consigliato)

Per un ambiente di produzione più robusto, considera:

### 10.1 Utilizzo di Process Manager (alternativa a screen)

**PM2 per il Backend:**
```bash
# Installa PM2
npm install -g pm2

# Avvia il backend con PM2
cd ~/projects/StyleForge/backend
pm2 start "python api.py" --name styleforge-backend

# Avvia il frontend con PM2
cd ~/projects/StyleForge/frontend
pm2 start "npm run preview -- --host 0.0.0.0 --port 3000" --name styleforge-frontend

# Salva la configurazione per restart automatico
pm2 save
pm2 startup
```

### 10.2 Reverse Proxy con Nginx

Installa e configura Nginx:

```bash
sudo apt install nginx

# Crea la configurazione
sudo nano /etc/nginx/sites-available/styleforge
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api {
        rewrite ^/api/(.*) /$1 break;
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Attiva la configurazione:
```bash
sudo ln -s /etc/nginx/sites-available/styleforge /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 10.3 SSL con Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 11. Deployment con Systemd (Produzione)

Systemd è il sistema di init predefinito su Linux moderno ed è la soluzione raccomandata per deployment in produzione. Offre:
- Restart automatico in caso di crash
- Gestione centralizzata dei servizi
- Log integrati con journalctl
- Avvio automatico al boot
- Controllo risorse e sicurezza

### 11.1 Creazione del Service File per il Backend

```bash
sudo nano /etc/systemd/system/styleforge-backend.service
```

Inserisci questa configurazione (sostituisci `your-username` con il tuo utente):

```ini
[Unit]
Description=StyleForge Backend API
Documentation=https://github.com/yourusername/styleforge
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=your-username
Group=your-username
WorkingDirectory=/home/your-username/projects/StyleForge/backend

# Variabili d'ambiente
Environment="PATH=/home/your-username/projects/StyleForge/backend/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/your-username/projects/StyleForge/backend/.env

# Comando di avvio
ExecStart=/home/your-username/projects/StyleForge/backend/venv/bin/python /home/your-username/projects/StyleForge/backend/api.py

# Restart automatico
Restart=always
RestartSec=10

# Limiti di sicurezza e risorse
StandardOutput=journal
StandardError=journal
SyslogIdentifier=styleforge-backend

# Timeout
TimeoutStartSec=60
TimeoutStopSec=30

# Sicurezza
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/your-username/projects/StyleForge/backend/uploads
ReadWritePaths=/home/your-username/projects/StyleForge/backend/results

[Install]
WantedBy=multi-user.target
```

### 11.2 Creazione del Service File per il Frontend

```bash
sudo nano /etc/systemd/system/styleforge-frontend.service
```

**Opzione 1: Development Server (per testing)**

```ini
[Unit]
Description=StyleForge Frontend (Vite Dev Server)
Documentation=https://github.com/yourusername/styleforge
After=network.target styleforge-backend.service
Wants=styleforge-backend.service

[Service]
Type=simple
User=your-username
Group=your-username
WorkingDirectory=/home/your-username/projects/StyleForge/frontend

# Variabili d'ambiente
Environment="NODE_ENV=development"
Environment="PATH=/usr/bin:/bin:/usr/local/bin"

# Comando di avvio
ExecStart=/usr/bin/npm run dev -- --host 0.0.0.0 --port 3000

# Restart automatico
Restart=always
RestartSec=10

# Log
StandardOutput=journal
StandardError=journal
SyslogIdentifier=styleforge-frontend

# Timeout
TimeoutStartSec=60
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

**Opzione 2: Build di Produzione (consigliato)**

Prima crea la build:
```bash
cd ~/projects/StyleForge/frontend
npm run build
```

Poi usa questo service file:

```ini
[Unit]
Description=StyleForge Frontend (Production)
Documentation=https://github.com/yourusername/styleforge
After=network.target styleforge-backend.service
Wants=styleforge-backend.service

[Service]
Type=simple
User=your-username
Group=your-username
WorkingDirectory=/home/your-username/projects/StyleForge/frontend

# Variabili d'ambiente
Environment="NODE_ENV=production"
Environment="PATH=/usr/bin:/bin:/usr/local/bin"

# Comando di avvio (usa preview per servire la build)
ExecStart=/usr/bin/npm run preview -- --host 0.0.0.0 --port 3000

# Restart automatico
Restart=always
RestartSec=10

# Log
StandardOutput=journal
StandardError=journal
SyslogIdentifier=styleforge-frontend

# Timeout
TimeoutStartSec=60
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

### 11.3 Configurazione Alternativa Backend con Uvicorn (Più Performante)

Se preferisci usare uvicorn direttamente con workers multipli:

```bash
sudo nano /etc/systemd/system/styleforge-backend.service
```

```ini
[Unit]
Description=StyleForge Backend API (Uvicorn)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=your-username
Group=your-username
WorkingDirectory=/home/your-username/projects/StyleForge/backend

Environment="PATH=/home/your-username/projects/StyleForge/backend/venv/bin"
EnvironmentFile=/home/your-username/projects/StyleForge/backend/.env

# Uvicorn con 4 workers
ExecStart=/home/your-username/projects/StyleForge/backend/venv/bin/uvicorn api:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info \
    --access-log

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=styleforge-backend

TimeoutStartSec=60
TimeoutStopSec=30

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### 11.4 Attivazione e Gestione dei Servizi

```bash
# Ricarica systemd per leggere i nuovi service file
sudo systemctl daemon-reload

# Abilita i servizi all'avvio del sistema
sudo systemctl enable styleforge-backend
sudo systemctl enable styleforge-frontend

# Avvia i servizi
sudo systemctl start styleforge-backend
sudo systemctl start styleforge-frontend

# Verifica lo stato
sudo systemctl status styleforge-backend
sudo systemctl status styleforge-frontend
```

### 11.5 Comandi di Gestione Systemd

```bash
# Avvio
sudo systemctl start styleforge-backend
sudo systemctl start styleforge-frontend

# Stop
sudo systemctl stop styleforge-backend
sudo systemctl stop styleforge-frontend

# Restart
sudo systemctl restart styleforge-backend
sudo systemctl restart styleforge-frontend

# Reload (senza downtime, se supportato)
sudo systemctl reload styleforge-backend

# Verifica stato
sudo systemctl status styleforge-backend
sudo systemctl status styleforge-frontend

# Verifica se abilitato all'avvio
sudo systemctl is-enabled styleforge-backend
sudo systemctl is-enabled styleforge-frontend

# Disabilita avvio automatico
sudo systemctl disable styleforge-backend
sudo systemctl disable styleforge-frontend

# Riavvio solo se fallisce
sudo systemctl restart --failed

# Visualizza tutte le dipendenze
systemctl list-dependencies styleforge-backend
```

### 11.6 Visualizzazione dei Log con Journalctl

```bash
# Log del backend (ultimi 100 righe)
sudo journalctl -u styleforge-backend -n 100

# Log del frontend
sudo journalctl -u styleforge-frontend -n 100

# Segui i log in tempo reale (come tail -f)
sudo journalctl -u styleforge-backend -f
sudo journalctl -u styleforge-frontend -f

# Log di entrambi i servizi
sudo journalctl -u styleforge-backend -u styleforge-frontend -f

# Log dall'ultima ora
sudo journalctl -u styleforge-backend --since "1 hour ago"

# Log di oggi
sudo journalctl -u styleforge-backend --since today

# Log tra date specifiche
sudo journalctl -u styleforge-backend --since "2024-01-01" --until "2024-01-02"

# Log con priorità (solo errori)
sudo journalctl -u styleforge-backend -p err

# Esporta log in un file
sudo journalctl -u styleforge-backend > backend.log
sudo journalctl -u styleforge-frontend > frontend.log

# Pulisci vecchi log (mantieni solo gli ultimi 7 giorni)
sudo journalctl --vacuum-time=7d

# Pulisci log (mantieni solo 500MB)
sudo journalctl --vacuum-size=500M
```

### 11.7 Configurazione Avanzata con Environment File

Per gestire meglio le variabili d'ambiente, puoi creare file separati:

```bash
sudo nano /etc/styleforge/backend.env
```

```bash
ANTHROPIC_API_KEY=your_key_here
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
DATABASE_URL=postgresql://user:pass@localhost/styleforge
SECRET_KEY=your_secret
HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=info
```

Poi modifica il service file:
```ini
[Service]
EnvironmentFile=/etc/styleforge/backend.env
```

Proteggi il file:
```bash
sudo chmod 600 /etc/styleforge/backend.env
sudo chown root:root /etc/styleforge/backend.env
```

### 11.8 Monitoraggio e Alerting

#### Script di Health Check

Crea uno script per monitorare i servizi:

```bash
nano ~/projects/StyleForge/health-check.sh
```

```bash
#!/bin/bash

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "=== StyleForge Health Check ==="
echo ""

# Check Backend
echo -n "Backend Service: "
if systemctl is-active --quiet styleforge-backend; then
    echo -e "${GREEN}RUNNING${NC}"
else
    echo -e "${RED}STOPPED${NC}"
fi

echo -n "Backend API: "
if curl -f -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Check Frontend
echo -n "Frontend Service: "
if systemctl is-active --quiet styleforge-frontend; then
    echo -e "${GREEN}RUNNING${NC}"
else
    echo -e "${RED}STOPPED${NC}"
fi

echo -n "Frontend Server: "
if curl -f -s http://localhost:3000 > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Disk Space
echo ""
echo "Disk Usage:"
df -h /home | grep -v Filesystem

# Memory Usage
echo ""
echo "Memory Usage:"
free -h

# Recent Errors
echo ""
echo "Recent Backend Errors (last 10):"
sudo journalctl -u styleforge-backend -p err -n 10 --no-pager
```

```bash
chmod +x ~/projects/StyleForge/health-check.sh
```

#### Timer Systemd per Health Check Automatico

```bash
sudo nano /etc/systemd/system/styleforge-healthcheck.service
```

```ini
[Unit]
Description=StyleForge Health Check
After=styleforge-backend.service styleforge-frontend.service

[Service]
Type=oneshot
ExecStart=/home/your-username/projects/StyleForge/health-check.sh
StandardOutput=journal
```

```bash
sudo nano /etc/systemd/system/styleforge-healthcheck.timer
```

```ini
[Unit]
Description=Run StyleForge Health Check every 5 minutes
Requires=styleforge-healthcheck.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
Unit=styleforge-healthcheck.service

[Install]
WantedBy=timers.target
```

Attiva il timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable styleforge-healthcheck.timer
sudo systemctl start styleforge-healthcheck.timer

# Verifica timer attivi
systemctl list-timers
```

### 11.9 Limiti di Risorse

Per limitare l'uso di risorse, modifica i service file:

```ini
[Service]
# Limita memoria a 2GB
MemoryLimit=2G
MemoryMax=2G

# Limita CPU al 80%
CPUQuota=80%

# Limita numero di file aperti
LimitNOFILE=10000

# Limita processi
TasksMax=100
```

### 11.10 Backup Automatico con Systemd Timer

```bash
sudo nano /etc/systemd/system/styleforge-backup.service
```

```ini
[Unit]
Description=StyleForge Backup Service

[Service]
Type=oneshot
User=your-username
WorkingDirectory=/home/your-username/projects/StyleForge
ExecStart=/bin/bash /home/your-username/projects/StyleForge/backup.sh
```

```bash
sudo nano /etc/systemd/system/styleforge-backup.timer
```

```ini
[Unit]
Description=Run StyleForge backup daily at 2 AM

[Timer]
OnCalendar=daily
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Crea lo script di backup:
```bash
nano ~/projects/StyleForge/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/your-username/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup database
pg_dump styleforge > "$BACKUP_DIR/db_$DATE.sql"

# Backup uploads e results
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" \
    /home/your-username/projects/StyleForge/backend/uploads \
    /home/your-username/projects/StyleForge/backend/results

# Rimuovi backup più vecchi di 7 giorni
find "$BACKUP_DIR" -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

```bash
chmod +x ~/projects/StyleForge/backup.sh
sudo systemctl enable styleforge-backup.timer
sudo systemctl start styleforge-backup.timer
```

### 11.11 Troubleshooting Systemd

```bash
# Il servizio non parte
sudo systemctl status styleforge-backend
sudo journalctl -xe -u styleforge-backend

# Testa la configurazione
sudo systemd-analyze verify styleforge-backend.service

# Verifica permessi
ls -la /etc/systemd/system/styleforge-*.service

# Ricarica dopo modifiche
sudo systemctl daemon-reload
sudo systemctl restart styleforge-backend

# Verifica dipendenze
systemctl list-dependencies styleforge-backend

# Simula avvio senza realmente avviare
sudo systemd-analyze verify styleforge-backend.service

# Debug mode
sudo systemd-analyze verify styleforge-backend.service
sudo journalctl -u styleforge-backend --since today --no-pager
```

### 11.12 Script di Deploy Completo con Systemd

```bash
nano ~/projects/StyleForge/deploy-systemd.sh
```

```bash
#!/bin/bash

set -e  # Exit on error

echo "=== StyleForge Deployment Script ==="
echo ""

# Variabili
PROJECT_DIR="$HOME/projects/StyleForge"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# Update code
echo "1. Updating code..."
cd "$PROJECT_DIR"
git pull

# Backend
echo "2. Updating backend dependencies..."
cd "$BACKEND_DIR"
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Frontend
echo "3. Building frontend..."
cd "$FRONTEND_DIR"
npm install
npm run build

# Restart services
echo "4. Restarting services..."
sudo systemctl restart styleforge-backend
sudo systemctl restart styleforge-frontend

# Wait for services
echo "5. Waiting for services to start..."
sleep 5

# Health check
echo "6. Running health check..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Backend is healthy"
else
    echo "✗ Backend health check failed"
    exit 1
fi

if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✓ Frontend is healthy"
else
    echo "✗ Frontend health check failed"
    exit 1
fi

echo ""
echo "=== Deployment completed successfully! ==="
sudo systemctl status styleforge-backend --no-pager
sudo systemctl status styleforge-frontend --no-pager
```

```bash
chmod +x ~/projects/StyleForge/deploy-systemd.sh
```

### 11.13 Riepilogo Comandi Systemd

```bash
# Setup iniziale
sudo systemctl daemon-reload
sudo systemctl enable styleforge-backend styleforge-frontend
sudo systemctl start styleforge-backend styleforge-frontend

# Gestione quotidiana
sudo systemctl restart styleforge-backend    # Restart backend
sudo systemctl reload styleforge-backend     # Reload config senza downtime
sudo systemctl status styleforge-*           # Status di tutti i servizi

# Monitoring
sudo journalctl -u styleforge-backend -f     # Follow logs
sudo systemctl list-units 'styleforge-*'     # Lista tutti i servizi

# Troubleshooting
sudo systemctl --failed                       # Servizi falliti
sudo journalctl -xe                          # Log degli errori
sudo systemctl reset-failed                  # Reset stato failed
```

## 12. Troubleshooting

### Il backend non si avvia

```bash
# Verifica i log
screen -r styleforge-backend

# Controlla le variabili d'ambiente
cd ~/projects/StyleForge/backend
source venv/bin/activate
cat .env

# Testa manualmente
python api.py
```

### Il frontend non si connette al backend

1. Verifica che il backend sia in esecuzione: `curl http://localhost:8000/health`
2. Controlla il file `.env` del frontend
3. Verifica il CORS nel backend (`config.py` o `api.py`)
4. Controlla il firewall

### Le sessioni screen si chiudono

```bash
# Verifica gli errori nei log
screen -r styleforge-backend
# oppure
tail -f ~/projects/StyleForge/backend/backend.log
```

### Permessi negati

```bash
# Assicurati che le directory abbiano i permessi corretti
chmod -R 755 ~/projects/StyleForge/backend/uploads
chmod -R 755 ~/projects/StyleForge/backend/results
```

## 13. Manutenzione

### Aggiornamento dell'Applicazione

```bash
# Ferma i servizi
bash ~/projects/StyleForge/stop.sh

# Aggiorna il codice
cd ~/projects/StyleForge
git pull

# Aggiorna backend
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Aggiorna frontend
cd ../frontend
npm install

# Riavvia
bash ~/projects/StyleForge/start.sh
```

### Backup

```bash
# Backup del database
pg_dump styleforge > backup_$(date +%Y%m%d).sql

# Backup dei file
tar -czf styleforge_backup_$(date +%Y%m%d).tar.gz ~/projects/StyleForge
```

## 14. Avvio Automatico al Boot con Crontab (Alternativa a Systemd)

### Usando crontab

```bash
crontab -e
```

Aggiungi:
```bash
@reboot sleep 30 && /bin/bash ~/projects/StyleForge/start.sh
```

**Nota:** Per un setup con systemd completo e robusto, vedi la sezione 11.

## 15. Riepilogo Comandi Rapidi

```bash
# Avvio manuale con screen
bash ~/projects/StyleForge/start.sh

# Stop
bash ~/projects/StyleForge/stop.sh

# Restart
bash ~/projects/StyleForge/restart.sh

# Visualizza sessioni attive
screen -ls

# Accedi al backend
screen -r styleforge-backend

# Accedi al frontend
screen -r styleforge-frontend

# Esci da screen (senza terminare)
# Ctrl+A poi D

# Verifica servizi
curl http://localhost:8000/health
curl http://localhost:3000
```

## 16. Note Finali

- **Screen** è ottimo per deployment rapidi e testing, ma per produzione considera **PM2** o **systemd**
- Configura sempre **backup automatici** del database
- Monitora l'uso delle risorse con `htop` o `top`
- Configura **SSL/TLS** per produzione
- Considera l'uso di un **reverse proxy** (Nginx/Apache) per gestire meglio il traffico
- Implementa **rate limiting** e **autenticazione** per l'API in produzione

Buon deployment!
