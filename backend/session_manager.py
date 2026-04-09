"""
Session Manager per gestire multiple sessioni Claude con persistenza database.
"""

import uuid
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from sqlalchemy.orm import Session as DBSession

from claude_client import ClaudeClient
from db_models import Session as SessionModel
from database import SessionLocal


class SessionManager:
    """
    Gestisce multiple sessioni Claude con persistenza su database.

    Mantiene una cache in memoria dei client Claude attivi mentre
    persiste i metadati sul database PostgreSQL. La conversation history
    viene salvata automaticamente dopo ogni operazione.
    """

    def __init__(self):
        """Inizializza il session manager."""
        self._clients: Dict[str, ClaudeClient] = {}
        self._lock = asyncio.Lock()

    def _get_db(self) -> DBSession:
        """Ottiene una sessione database."""
        return SessionLocal()

    def _save_client_to_db(self, session_id: str, db: Optional[DBSession] = None):
        """Salva lo stato del client in cache nel database."""
        if session_id not in self._clients:
            return
        client = self._clients[session_id]
        close_db = False
        if db is None:
            db = self._get_db()
            close_db = True
        try:
            db_session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            if db_session:
                db_session.conversation_history = json.dumps(client.conversation_history)
                db_session.is_trained = client.is_trained
                db_session.last_activity = datetime.utcnow()
                db.commit()
        finally:
            if close_db:
                db.close()

    def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        db: Optional[DBSession] = None
    ) -> str:
        """Crea una nuova sessione Claude."""
        close_db = False
        if db is None:
            db = self._get_db()
            close_db = True

        try:
            if session_id is None:
                session_id = f"session_{uuid.uuid4().hex[:12]}"

            existing = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            if existing:
                raise ValueError(f"Sessione {session_id} gia' esistente")

            db_session = SessionModel(
                session_id=session_id,
                user_id=user_id,
                is_trained=False
            )
            db.add(db_session)
            db.commit()

            self._clients[session_id] = ClaudeClient()

            return session_id
        finally:
            if close_db:
                db.close()

    def get_session(self, session_id: str, user_id: Optional[str] = None) -> ClaudeClient:
        """Ottiene una sessione esistente. Ricostruisce dalla DB se non in cache."""
        db = self._get_db()
        try:
            query = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            )
            if user_id:
                query = query.filter(SessionModel.user_id == user_id)

            db_session = query.first()
            if not db_session:
                raise ValueError(f"Sessione {session_id} non trovata")

            db_session.last_activity = datetime.utcnow()
            db.commit()

            if session_id not in self._clients:
                client = ClaudeClient()
                if db_session.conversation_history:
                    try:
                        client.conversation_history = json.loads(db_session.conversation_history)
                        client.is_trained = db_session.is_trained
                    except json.JSONDecodeError:
                        pass
                self._clients[session_id] = client

            return self._clients[session_id]
        finally:
            db.close()

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        """Elimina una sessione."""
        db = self._get_db()
        try:
            query = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            )
            if user_id:
                query = query.filter(SessionModel.user_id == user_id)

            db_session = query.first()
            if db_session:
                db.delete(db_session)
                db.commit()

            if session_id in self._clients:
                del self._clients[session_id]
        finally:
            db.close()

    def session_exists(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """Verifica se una sessione esiste."""
        db = self._get_db()
        try:
            query = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            )
            if user_id:
                query = query.filter(SessionModel.user_id == user_id)
            return query.first() is not None
        finally:
            db.close()

    def get_all_sessions(self, user_id: Optional[str] = None) -> Dict[str, dict]:
        """Ottiene informazioni su tutte le sessioni."""
        db = self._get_db()
        try:
            query = db.query(SessionModel)
            if user_id:
                query = query.filter(SessionModel.user_id == user_id)

            sessions = query.all()
            result = {}

            for session in sessions:
                jobs = [job.job_id for job in session.jobs]

                conv_length = 0
                if session.conversation_history:
                    try:
                        history = json.loads(session.conversation_history)
                        conv_length = len(history)
                    except json.JSONDecodeError:
                        pass

                result[session.session_id] = {
                    "session_id": session.session_id,
                    "name": session.name,
                    "is_trained": session.is_trained,
                    "conversation_length": conv_length,
                    "created_at": session.created_at,
                    "last_activity": session.last_activity,
                    "jobs": jobs
                }

            return result
        finally:
            db.close()

    def get_user_sessions(self, user_id: str) -> List[dict]:
        """Ottiene tutte le sessioni di un utente."""
        sessions_dict = self.get_all_sessions(user_id)
        return list(sessions_dict.values())

    def set_session_name(self, session_id: str, name: str) -> None:
        """Imposta il nome descrittivo di una sessione."""
        db = self._get_db()
        try:
            db_session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            if db_session:
                db_session.name = name
                db.commit()
        finally:
            db.close()

    def set_session_trained(self, session_id: str, trained: bool = True) -> None:
        """Imposta lo stato di training e salva la conversation history."""
        db = self._get_db()
        try:
            db_session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            if db_session:
                db_session.is_trained = trained
                # Salva anche la conversation history
                if session_id in self._clients:
                    client = self._clients[session_id]
                    client.is_trained = trained
                    db_session.conversation_history = json.dumps(client.conversation_history)
                db.commit()
        finally:
            db.close()

    def save_conversation_history(self, session_id: str) -> None:
        """Salva la conversation history di un client nel database."""
        self._save_client_to_db(session_id)

    def add_job_to_session(self, session_id: str, job_id: str) -> None:
        """Aggiunge un job ID alla lista dei job di una sessione."""
        pass  # Gestito dalla relazione FK nel database

    def get_session_count(self, user_id: Optional[str] = None) -> int:
        """Ottiene il numero di sessioni."""
        db = self._get_db()
        try:
            query = db.query(SessionModel)
            if user_id:
                query = query.filter(SessionModel.user_id == user_id)
            return query.count()
        finally:
            db.close()

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Rimuove le sessioni non addestrate inattive."""
        db = self._get_db()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

            old_sessions = db.query(SessionModel).filter(
                SessionModel.last_activity < cutoff,
                SessionModel.is_trained == False
            ).all()

            count = len(old_sessions)

            for session in old_sessions:
                if session.session_id in self._clients:
                    del self._clients[session.session_id]
                db.delete(session)

            db.commit()

            return count
        finally:
            db.close()


# Istanza globale
session_manager = SessionManager()
