# Guida Aggiornamento Node.js per StyleForge

## Problema

Vite 7.x richiede Node.js versione 20.19+ o 22.12+, ma il server ha la versione 18.20.8.

## Soluzione: Aggiornare Node.js a una Versione Compatibile

### Opzione 1: Aggiornare Node.js tramite NodeSource (Consigliato)

#### Per Node.js 20.x (LTS - Long Term Support)

```bash
# Rimuovi la vecchia repository NodeSource
sudo rm -f /etc/apt/sources.list.d/nodesource.list

# Aggiungi la repository per Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# Aggiorna e installa Node.js 20
sudo apt update
sudo apt install -y nodejs

# Verifica la versione
node --version  # Dovrebbe mostrare v20.x.x
npm --version
```

#### Per Node.js 22.x (Current - Più recente)

```bash
# Rimuovi la vecchia repository NodeSource
sudo rm -f /etc/apt/sources.list.d/nodesource.list

# Aggiungi la repository per Node.js 22.x
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -

# Aggiorna e installa Node.js 22
sudo apt update
sudo apt install -y nodejs

# Verifica la versione
node --version  # Dovrebbe mostrare v22.x.x
npm --version
```

### Opzione 2: Usare NVM (Node Version Manager) - Più Flessibile

NVM ti permette di gestire multiple versioni di Node.js sullo stesso sistema.

#### Installazione di NVM

```bash
# Scarica e installa NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Carica NVM nel terminale corrente
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Verifica l'installazione
nvm --version
```

#### Installazione Node.js con NVM

```bash
# Installa Node.js 20 (LTS)
nvm install 20

# Oppure installa Node.js 22 (Current)
nvm install 22

# Imposta come versione predefinita
nvm alias default 20  # o 22

# Usa la versione
nvm use 20  # o 22

# Verifica
node --version
npm --version
```

#### Aggiungere NVM al Profile (per rendere permanente)

Aggiungi queste righe al tuo `~/.bashrc` o `~/.profile`:

```bash
nano ~/.bashrc
```

Aggiungi alla fine:
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
```

Ricarica:
```bash
source ~/.bashrc
```

## Dopo l'Aggiornamento di Node.js

### 1. Reinstalla le Dipendenze del Frontend

```bash
cd ~/projects/StyleForge/frontend

# Rimuovi node_modules e package-lock.json
rm -rf node_modules package-lock.json

# Reinstalla le dipendenze
npm install

# Verifica che funzioni
npm run dev -- --host 0.0.0.0 --port 3000
```

### 2. Aggiorna gli Script se usi Systemd

Se hai già configurato i service file systemd, devi aggiornarli per usare la versione corretta di Node.js.

#### Se hai usato NodeSource (Opzione 1)

I service file funzioneranno automaticamente perché `node` e `npm` sono nel PATH di sistema.

#### Se hai usato NVM (Opzione 2)

Devi modificare i service file per puntare alla versione corretta di Node.js gestita da NVM.

Prima trova il path di Node.js:
```bash
nvm which 20  # o 22
# Output esempio: /root/.nvm/versions/node/v20.19.0/bin/node
```

Poi modifica il service file:
```bash
sudo nano /etc/systemd/system/styleforge-frontend.service
```

Cambia l'`ExecStart` usando il path completo:
```ini
[Service]
# Invece di:
# ExecStart=/usr/bin/npm run dev -- --host 0.0.0.0 --port 3000

# Usa:
ExecStart=/root/.nvm/versions/node/v20.19.0/bin/npm run dev -- --host 0.0.0.0 --port 3000

# Oppure per produzione:
ExecStart=/root/.nvm/versions/node/v20.19.0/bin/npm run preview -- --host 0.0.0.0 --port 3000
```

E aggiungi il PATH corretto:
```ini
[Service]
Environment="PATH=/root/.nvm/versions/node/v20.19.0/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

Ricarica systemd:
```bash
sudo systemctl daemon-reload
sudo systemctl restart styleforge-frontend
```

### 3. Aggiorna gli Script Bash

Se usi gli script bash per avviare i servizi con screen, aggiorna il file `start.sh`:

#### Se usi NodeSource (nessuna modifica necessaria)

Gli script funzioneranno automaticamente.

#### Se usi NVM

```bash
nano ~/projects/StyleForge/start.sh
```

Modifica lo script per caricare NVM:
```bash
#!/bin/bash

# Carica NVM
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Usa la versione corretta di Node.js
nvm use 20  # o 22

echo "Avvio StyleForge Backend..."
screen -dmS styleforge-backend bash -c 'cd ~/projects/StyleForge/backend && source venv/bin/activate && python api.py'

echo "Attendo 5 secondi..."
sleep 5

echo "Avvio StyleForge Frontend..."
screen -dmS styleforge-frontend bash -c '
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use 20
    cd ~/projects/StyleForge/frontend && npm run dev -- --host 0.0.0.0 --port 3000
'

echo "StyleForge avviato!"
echo "Backend: http://$(hostname -I | awk '{print $1}'):8000"
echo "Frontend: http://$(hostname -I | awk '{print $1}'):3000"
```

## Verifica Finale

Dopo aver completato l'aggiornamento:

```bash
# Verifica versioni
node --version  # Deve essere >= 20.19.0
npm --version

# Testa il frontend
cd ~/projects/StyleForge/frontend
npm run dev -- --host 0.0.0.0 --port 3000

# Se funziona, fermalo (Ctrl+C) e avvia con screen o systemd
```

## Raccomandazione

**Per un server di produzione, usa NodeSource (Opzione 1) con Node.js 20 LTS** perché:
- È più stabile e testato
- Più facile da gestire con systemd
- Supporto a lungo termine (LTS)
- Installazione system-wide senza complicazioni

**Usa NVM (Opzione 2) se:**
- Devi gestire multiple versioni di Node.js
- Hai più progetti che richiedono versioni diverse
- Preferisci maggiore flessibilità

## Comandi Rapidi per l'Aggiornamento

### Quick Fix con NodeSource (Raccomandato per la maggior parte dei casi)

```bash
# Tutto in un comando
sudo rm -f /etc/apt/sources.list.d/nodesource.list && \
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && \
sudo apt update && \
sudo apt install -y nodejs && \
node --version && \
cd ~/projects/StyleForge/frontend && \
rm -rf node_modules package-lock.json && \
npm install && \
echo "✓ Node.js aggiornato e dipendenze reinstallate!"
```

Dopo questo comando, puoi avviare il frontend normalmente con screen o systemd.

## Troubleshooting

### Errore: "Unable to locate package nodejs"

```bash
# Pulisci la cache
sudo apt clean
sudo apt update

# Riprova l'installazione della repository NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt update
sudo apt install -y nodejs
```

### NVM non carica automaticamente

Assicurati di aver aggiunto le righe al `~/.bashrc` e di aver fatto `source ~/.bashrc`.

### Permission denied durante l'installazione

Se usi NVM come root, assicurati di installarlo per l'utente root:
```bash
sudo su -
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

### npm install fallisce dopo l'aggiornamento

```bash
# Pulisci tutto e reinstalla
cd ~/projects/StyleForge/frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```
