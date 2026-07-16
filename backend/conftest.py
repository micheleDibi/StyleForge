"""
Configurazione pytest condivisa.

Esiste per una ragione sola: auth.py rifiuta di importarsi senza una
JWT_SECRET_KEY valida (e' il fix di VULN-0003). Senza queste variabili l'intera
suite morirebbe in fase di COLLECTION, non su un singolo test, perche' basta un
import indiretto (test_api -> api -> auth) a far esplodere tutto.

Funziona perche' load_dotenv() non fa override: una variabile gia' presente
nell'ambiente vince sul .env. Va quindi impostata PRIMA di qualunque import dei
moduli applicativi — cioe' qui, che pytest carica per primo.

Il valore e' un segnaposto di test: non firma nulla che esca da qui.
"""

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-secret-non-usare-mai-in-produzione-" + "x" * 32,
)
