"""
Session Manager per gestire multiple sessioni Claude con persistenza database.
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from threading import Lock
from sqlalchemy.orm import Session as DBSession

from claude_client import ClaudeClient
from db_models import Session as SessionModel
from database import SessionLocal


class SessionManager:
    """
    Gestisce multiple sessioni Claude con persistenza su database.

    Mantiene una cache in memoria dei client Claude attivi mentre
    persiste i metadati sul database PostgreSQL.
    """

    def __init__(self):
        """Inizializza il session manager."""
        self._clients: Dict[str, ClaudeClient] = {}  # Cache in memoria dei client
        self._lock = Lock()

    def _get_db(self) -> DBSession:
        """Ottiene una sessione database."""
        return SessionLocal()

    def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        db: Optional[DBSession] = None
    ) -> str:
        """
        Crea una nuova sessione Claude.

        Args:
            user_id: ID dell'utente proprietario.
            session_id: ID opzionale per la sessione.
            db: Sessione database opzionale.

        Returns:
            L'ID della sessione creata.
        """
        close_db = False
        if db is None:
            db = self._get_db()
            close_db = True

        try:
            with self._lock:
                if session_id is None:
                    session_id = f"session_{uuid.uuid4().hex[:12]}"

                # Verifica che l'ID non esista già
                existing = db.query(SessionModel).filter(
                    SessionModel.session_id == session_id
                ).first()
                if existing:
                    raise ValueError(f"Sessione {session_id} già esistente")

                # Crea la sessione nel database
                db_session = SessionModel(
                    session_id=session_id,
                    user_id=user_id,
                    is_trained=False
                )
                db.add(db_session)
                db.commit()

                # Crea il client Claude in memoria
                self._clients[session_id] = ClaudeClient()

                return session_id
        finally:
            if close_db:
                db.close()

    def get_session(self, session_id: str, user_id: Optional[str] = None) -> ClaudeClient:
        """
        Ottiene una sessione esistente.

        Args:
            session_id: ID della sessione.
            user_id: ID dell'utente (opzionale, per verifica proprietà).

        Returns:
            Il client Claude della sessione.

        Raises:
            ValueError: Se la sessione non esiste o non appartiene all'utente.
        """
        db = self._get_db()
        try:
            with self._lock:
                # Verifica che la sessione esista nel database
                query = db.query(SessionModel).filter(
                    SessionModel.session_id == session_id
                )
                if user_id:
                    query = query.filter(SessionModel.user_id == user_id)

                db_session = query.first()
                if not db_session:
                    raise ValueError(f"Sessione {session_id} non trovata")

                # Aggiorna last_activity
                db_session.last_activity = datetime.utcnow()
                db.commit()

                # Se il client non è in cache, ricrealo
                if session_id not in self._clients:
                    client = ClaudeClient()
                    # Ripristina la conversation history dal database se presente
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
        """
        Elimina una sessione.

        Args:
            session_id: ID della sessione da eliminare.
            user_id: ID dell'utente (opzionale, per verifica proprietà).
        """
        db = self._get_db()
        try:
            with self._lock:
                query = db.query(SessionModel).filter(
                    SessionModel.session_id == session_id
                )
                if user_id:
                    query = query.filter(SessionModel.user_id == user_id)

                db_session = query.first()
                if db_session:
                    db.delete(db_session)
                    db.commit()

                # Rimuovi dalla cache
                if session_id in self._clients:
                    del self._clients[session_id]
        finally:
            db.close()

    def session_exists(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """
        Verifica se una sessione esiste.

        Args:
            session_id: ID della sessione.
            user_id: ID dell'utente (opzionale).

        Returns:
            True se la sessione esiste, False altrimenti.
        """
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
        """
        Ottiene informazioni su tutte le sessioni.

        Args:
            user_id: Se specificato, filtra per utente.

        Returns:
            Dizionario con informazioni su tutte le sessioni.
        """
        db = self._get_db()
        try:
            query = db.query(SessionModel)
            if user_id:
                query = query.filter(SessionModel.user_id == user_id)

            sessions = query.all()
            result = {}

            for session in sessions:
                # Ottieni il numero di job dalla relazione
                jobs = [job.job_id for job in session.jobs]

                # Calcola la lunghezza della conversation history
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
        """
        Ottiene tutte le sessioni di un utente.

        Args:
            user_id: ID dell'utente.

        Returns:
            Lista di dizionari con informazioni sulle sessioni.
        """
        sessions_dict = self.get_all_sessions(user_id)
        return list(sessions_dict.values())

    def set_session_name(self, session_id: str, name: str) -> None:
        """
        Imposta il nome descrittivo di una sessione.

        Args:
            session_id: ID della sessione.
            name: Nome descrittivo da impostare.
        """
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
        """
        Imposta lo stato di training di una sessione.

        Args:
            session_id: ID della sessione.
            trained: Stato di training.
        """
        db = self._get_db()
        try:
            db_session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            if db_session:
                db_session.is_trained = trained
                db.commit()

            # Aggiorna anche il client in cache
            if session_id in self._clients:
                self._clients[session_id].is_trained = trained
        finally:
            db.close()

    def save_conversation_history(self, session_id: str) -> None:
        """
        Salva la conversation history di un client nel database.

        Args:
            session_id: ID della sessione.
        """
        db = self._get_db()
        try:
            if session_id in self._clients:
                client = self._clients[session_id]
                db_session = db.query(SessionModel).filter(
                    SessionModel.session_id == session_id
                ).first()
                if db_session:
                    db_session.conversation_history = json.dumps(client.conversation_history)
                    db_session.is_trained = client.is_trained
                    db.commit()
        finally:
            db.close()

    def add_job_to_session(self, session_id: str, job_id: str) -> None:
        """
        Aggiunge un job ID alla lista dei job di una sessione.
        Questo è gestito automaticamente dalla relazione nel database.

        Args:
            session_id: ID della sessione.
            job_id: ID del job da aggiungere.
        """
        # La relazione è gestita dal JobManager quando crea il job
        pass

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Rimuove le sessioni inattive da più di max_age_hours.

        Args:
            max_age_hours: Età massima in ore per mantenere una sessione.

        Returns:
            Numero di sessioni rimosse.
        """
        db = self._get_db()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

            # Trova sessioni vecchie
            old_sessions = db.query(SessionModel).filter(
                SessionModel.last_activity < cutoff
            ).all()

            count = len(old_sessions)

            with self._lock:
                for session in old_sessions:
                    # Rimuovi dalla cache
                    if session.session_id in self._clients:
                        del self._clients[session.session_id]
                    db.delete(session)

                db.commit()

            return count
        finally:
            db.close()

    def get_session_count(self, user_id: Optional[str] = None) -> int:
        """
        Restituisce il numero di sessioni.

        Args:
            user_id: Se specificato, conta solo le sessioni dell'utente.

        Returns:
            Numero di sessioni.
        """
        db = self._get_db()
        try:
            query = db.query(SessionModel)
            if user_id:
                query = query.filter(SessionModel.user_id == user_id)
            return query.count()
        finally:
            db.close()

    def get_session_db_model(self, session_id: str) -> Optional[SessionModel]:
        """
        Ottiene il modello database della sessione.

        Args:
            session_id: ID della sessione.

        Returns:
            Il modello SessionModel o None.
        """
        db = self._get_db()
        try:
            return db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
        finally:
            db.close()


# Singleton instance
session_manager = SessionManager()
