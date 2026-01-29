"""
Test unitari per l'API StyleForge.

Esegui con: pytest test_api.py
"""

import pytest
from fastapi.testclient import TestClient
from api import app
from session_manager import session_manager
from job_manager import job_manager

client = TestClient(app)


class TestHealthCheck:
    """Test per health check endpoint."""

    def test_health_check(self):
        """Test health check restituisce 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "active_sessions" in data
        assert "active_jobs" in data


class TestSessions:
    """Test per session endpoints."""

    def test_create_session(self):
        """Test creazione sessione."""
        response = client.post("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["is_trained"] == False
        assert data["conversation_length"] == 0

    def test_create_session_with_custom_id(self):
        """Test creazione sessione con ID personalizzato."""
        custom_id = "test_session_123"
        response = client.post(f"/sessions?session_id={custom_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == custom_id

    def test_get_session(self):
        """Test recupero informazioni sessione."""
        # Crea sessione
        create_response = client.post("/sessions")
        session_id = create_response.json()["session_id"]

        # Recupera sessione
        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    def test_get_nonexistent_session(self):
        """Test recupero sessione inesistente."""
        response = client.get("/sessions/nonexistent")
        assert response.status_code == 404

    def test_list_sessions(self):
        """Test lista sessioni."""
        response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert isinstance(data["sessions"], list)

    def test_delete_session(self):
        """Test eliminazione sessione."""
        # Crea sessione
        create_response = client.post("/sessions")
        session_id = create_response.json()["session_id"]

        # Elimina sessione
        response = client.delete(f"/sessions/{session_id}")
        assert response.status_code == 200

        # Verifica eliminazione
        get_response = client.get(f"/sessions/{session_id}")
        assert get_response.status_code == 404


class TestJobs:
    """Test per job endpoints."""

    def test_get_job_nonexistent(self):
        """Test recupero job inesistente."""
        response = client.get("/jobs/nonexistent")
        assert response.status_code == 404

    def test_list_jobs(self):
        """Test lista job."""
        response = client.get("/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)


class TestGeneration:
    """Test per generation endpoint."""

    def test_generate_without_training(self):
        """Test generazione senza training fallisce."""
        # Crea sessione non addestrata
        session_response = client.post("/sessions")
        session_id = session_response.json()["session_id"]

        # Tenta generazione
        response = client.post("/generate", json={
            "session_id": session_id,
            "argomento": "Test",
            "numero_parole": 100
        })
        assert response.status_code == 400
        assert "non ancora addestrata" in response.json()["detail"]

    def test_generate_nonexistent_session(self):
        """Test generazione con sessione inesistente."""
        response = client.post("/generate", json={
            "session_id": "nonexistent",
            "argomento": "Test",
            "numero_parole": 100
        })
        assert response.status_code == 404


class TestValidation:
    """Test per validazione input."""

    def test_generate_invalid_numero_parole(self):
        """Test validazione numero_parole."""
        # Crea sessione
        session_response = client.post("/sessions")
        session_id = session_response.json()["session_id"]

        # Numero parole troppo basso
        response = client.post("/generate", json={
            "session_id": session_id,
            "argomento": "Test",
            "numero_parole": 50  # < 100
        })
        assert response.status_code == 422

        # Numero parole troppo alto
        response = client.post("/generate", json={
            "session_id": session_id,
            "argomento": "Test",
            "numero_parole": 20000  # > 10000
        })
        assert response.status_code == 422

    def test_generate_missing_fields(self):
        """Test validazione campi obbligatori."""
        response = client.post("/generate", json={
            "argomento": "Test"
            # Manca session_id e numero_parole
        })
        assert response.status_code == 422


# Cleanup fixture
@pytest.fixture(autouse=True)
def cleanup():
    """Pulizia dopo ogni test."""
    yield
    # Pulisci sessioni e job creati durante i test
    for session_id in list(session_manager._sessions.keys()):
        if session_id.startswith("test_"):
            session_manager.delete_session(session_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
