"""
Test di sicurezza dell'autenticazione (nessun DB/rete).

Codificano i PoC di vuln-0003 come regression test: se qualcuno rimette un
default al segreto, o smette di controllare il tipo di token, qui si rompe.

Esecuzione: python3 -m pytest test_auth_security.py -q
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

import pytest
from jose import jwt

import config

HERE = os.path.dirname(os.path.abspath(__file__))

# Il segreto pubblicato nel repo fino al pen-test: e' il PoC di vuln-0003.
DEFAULT_STORICO = "your-super-secret-key-change-in-production"

SEGRETO_FORTE = "K7x" + "q9Zt2Lm4Rv8Bn6Wy3Hc5Jd1Fg0Ps" + "aA" * 20


# ═════════════════════════════════════ validate_jwt_secret ═══════════════════

class TestValidateJwtSecret:
    @pytest.mark.parametrize("valore", [None, "", "   ", "\n\t "])
    def test_segreto_assente_o_vuoto(self, valore):
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            config.validate_jwt_secret(valore)

    @pytest.mark.parametrize(
        "valore",
        [
            DEFAULT_STORICO,
            DEFAULT_STORICO.upper(),
            "change-me",
            "changeme",
            "secret",
            "your-secret-key",
        ],
    )
    def test_segnaposto_rifiutati(self, valore):
        with pytest.raises(RuntimeError, match="segnaposto"):
            config.validate_jwt_secret(valore)

    def test_il_default_storico_non_passa_per_lunghezza(self):
        # Il punto di questo test: il segnaposto e' lungo 42 caratteri, quindi
        # una soglia "almeno 32" lo lascerebbe passare e il fix sarebbe finto.
        # E' la deny-list a fermarlo, non la lunghezza.
        assert len(DEFAULT_STORICO) == 42
        assert config.JWT_SECRET_MIN_LENGTH > len(DEFAULT_STORICO)

    def test_segreto_troppo_corto(self):
        with pytest.raises(RuntimeError, match="troppo corta"):
            config.validate_jwt_secret("a" * (config.JWT_SECRET_MIN_LENGTH - 1))

    def test_segreto_valido_passa(self):
        assert config.validate_jwt_secret(SEGRETO_FORTE) == SEGRETO_FORTE

    def test_segreto_valido_viene_ripulito(self):
        assert config.validate_jwt_secret(f"  {SEGRETO_FORTE}  ") == SEGRETO_FORTE

    def test_token_urlsafe_64_e_accettato(self):
        # Il comando che diamo all'operatore deve produrre un valore valido.
        import secrets

        config.validate_jwt_secret(secrets.token_urlsafe(64))

    def test_il_messaggio_dice_come_generarne_uno(self):
        with pytest.raises(RuntimeError) as e:
            config.validate_jwt_secret(None)
        assert "secrets.token_urlsafe" in str(e.value)


# ═══════════════════════════════════════ boot guard ══════════════════════════

def _import_auth_con(secret):
    """
    Importa auth in un processo separato con JWT_SECRET_KEY esplicita.

    NON si usa monkeypatch.delenv + importlib.reload: auth.py chiama
    load_dotenv(), che ripescherebbe il valore dal .env su disco. Il test
    passerebbe oggi solo per coincidenza e fallirebbe appena il .env cambia o
    in CI, dove il .env non esiste. La variabile va sempre passata esplicita.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": HERE,
        "ANTHROPIC_API_KEY": "dummy",
    }
    if secret is not None:
        env["JWT_SECRET_KEY"] = secret
    return subprocess.run(
        [sys.executable, "-c", "import auth"],
        env=env,
        cwd=HERE,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestBootGuard:
    def test_lapp_non_parte_col_segreto_di_default(self):
        # PoC vuln-0003: e' il valore che sta ancora nei .env copiati.
        r = _import_auth_con(DEFAULT_STORICO)
        assert r.returncode != 0, "auth si e' importato col segreto pubblico"
        assert "segnaposto" in r.stderr

    def test_lapp_non_parte_col_segreto_troppo_corto(self):
        r = _import_auth_con("corto")
        assert r.returncode != 0
        assert "troppo corta" in r.stderr

    def test_lapp_non_parte_senza_segreto(self):
        r = _import_auth_con(None)
        assert r.returncode != 0
        assert "JWT_SECRET_KEY" in r.stderr

    def test_lapp_parte_col_segreto_forte(self):
        r = _import_auth_con(SEGRETO_FORTE)
        assert r.returncode == 0, f"auth non si importa con un segreto valido:\n{r.stderr}"

    def test_il_messaggio_di_errore_e_utile(self):
        r = _import_auth_con(DEFAULT_STORICO)
        # Chi vede il crash in produzione deve capire subito cosa fare.
        assert "secrets.token_urlsafe" in r.stderr
        assert "JWT_SECRET_KEY" in r.stderr


# ═══════════════════════════════════════ token typing ════════════════════════

class TestTokenTyping:
    def _payload(self):
        return {"sub": "11111111-1111-1111-1111-111111111111", "username": "tizio"}

    def test_access_token_accettato(self):
        import auth

        td = auth.decode_token(auth.create_access_token(self._payload()))
        assert td is not None and td.token_type == "access"

    def test_refresh_token_rifiutato_dove_serve_un_access(self):
        # Prima di questo controllo un refresh token (7 giorni di vita) passava
        # come Bearer su qualsiasi endpoint, admin inclusi.
        import auth

        assert auth.decode_token(auth.create_refresh_token(self._payload())) is None

    def test_access_token_rifiutato_dove_serve_un_refresh(self):
        import auth

        token = auth.create_access_token(self._payload())
        assert auth.decode_token(token, expected_type="refresh") is None

    def test_refresh_token_accettato_come_refresh(self):
        import auth

        td = auth.decode_token(auth.create_refresh_token(self._payload()), expected_type="refresh")
        assert td is not None and td.token_type == "refresh"

    def test_token_senza_claim_type_rifiutato(self):
        import auth

        token = jwt.encode(
            {**self._payload(), "exp": datetime.utcnow() + timedelta(minutes=30)},
            auth.SECRET_KEY,
            algorithm=auth.ALGORITHM,
        )
        assert auth.decode_token(token) is None

    def test_poc_vuln0003_token_forgiato_col_default_e_rifiutato(self):
        # Il PoC del report, alla lettera: token firmato col segreto pubblico.
        import auth

        forgiato = jwt.encode(
            {
                "sub": "11111111-1111-1111-1111-111111111111",
                "username": "attacker",
                "type": "access",
                "exp": datetime.utcnow() + timedelta(minutes=30),
            },
            DEFAULT_STORICO,
            algorithm="HS256",
        )
        assert auth.decode_token(forgiato) is None, "token forgiato col default accettato!"

    def test_token_di_un_altro_segreto_rifiutato(self):
        import auth

        altro = jwt.encode(
            {"sub": "x", "type": "access", "exp": datetime.utcnow() + timedelta(minutes=30)},
            "un-altro-segreto-lungo-abbastanza-" + "z" * 40,
            algorithm="HS256",
        )
        assert auth.decode_token(altro) is None
