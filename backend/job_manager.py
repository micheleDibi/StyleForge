"""
Job Manager per gestire job asincroni con persistenza database.
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any, List
from threading import Lock
from sqlalchemy.orm import Session as DBSession

from models import JobStatus, JobType
from db_models import Job as JobModel, Session as SessionModel
from database import SessionLocal


class Job:
    """Rappresenta un job in esecuzione (in memoria)."""

    def __init__(
        self,
        job_id: str,
        session_id: str,
        user_id: str,
        job_type: JobType,
        task_func: Callable,
        db_session_id: str,  # UUID della sessione nel database
        **kwargs
    ):
        """
        Inizializza un job.

        Args:
            job_id: ID univoco del job.
            session_id: ID della sessione associata (stringa leggibile).
            user_id: ID dell'utente proprietario.
            job_type: Tipo di job.
            task_func: Funzione da eseguire.
            db_session_id: UUID della sessione nel database.
            **kwargs: Argomenti da passare alla funzione.
        """
        self.job_id = job_id
        self.session_id = session_id
        self.user_id = user_id
        self.db_session_id = db_session_id
        self.job_type = job_type
        self.task_func = task_func
        self.kwargs = kwargs
        self.status = 'pending'
        self.progress = 0
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None

    def to_dict(self) -> dict:
        """Converte il job in un dizionario."""
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at
        }


class JobManager:
    """
    Gestisce l'esecuzione di job asincroni con persistenza su database.
    """

    def __init__(self, max_concurrent_jobs: int = 10):
        """
        Inizializza il job manager.

        Args:
            max_concurrent_jobs: Numero massimo di job eseguibili contemporaneamente.
        """
        self._active_jobs: Dict[str, Job] = {}  # Job in esecuzione (in memoria)
        self._lock = Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._max_concurrent_jobs = max_concurrent_jobs

    def _get_db(self) -> DBSession:
        """Ottiene una sessione database."""
        return SessionLocal()

    def create_job(
        self,
        session_id: str,
        user_id: str,
        job_type: JobType,
        task_func: Callable,
        job_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Crea un nuovo job.

        Args:
            session_id: ID della sessione (stringa leggibile).
            user_id: ID dell'utente proprietario.
            job_type: Tipo di job.
            task_func: Funzione da eseguire.
            job_id: ID opzionale per il job.
            **kwargs: Argomenti da passare alla funzione.

        Returns:
            L'ID del job creato.
        """
        db = self._get_db()
        try:
            with self._lock:
                if job_id is None:
                    job_id = f"job_{uuid.uuid4().hex[:12]}"

                # Trova la sessione nel database
                db_session = db.query(SessionModel).filter(
                    SessionModel.session_id == session_id
                ).first()
                if not db_session:
                    raise ValueError(f"Sessione {session_id} non trovata")

                # Crea il job nel database
                db_job = JobModel(
                    job_id=job_id,
                    session_id=db_session.id,
                    user_id=user_id,
                    job_type=job_type,
                    status='pending',
                    progress=0
                )
                db.add(db_job)
                db.commit()

                # Crea il job in memoria per l'esecuzione
                job = Job(
                    job_id=job_id,
                    session_id=session_id,
                    user_id=user_id,
                    job_type=job_type,
                    task_func=task_func,
                    db_session_id=str(db_session.id),
                    **kwargs
                )

                # Aggiungi session_id ai kwargs del job
                if 'session_id' not in job.kwargs:
                    job.kwargs['session_id'] = session_id

                self._active_jobs[job_id] = job
                return job_id
        finally:
            db.close()

    async def execute_job(self, job_id: str) -> None:
        """
        Esegue un job in modo asincrono.

        Args:
            job_id: ID del job da eseguire.
        """
        async with self._semaphore:
            job = self._active_jobs.get(job_id)
            if not job:
                return

            db = self._get_db()
            try:
                # Aggiorna stato in memoria e database
                job.status = 'training' if job.job_type == JobType.TRAINING or job.job_type == 'training' else 'generating'
                job.updated_at = datetime.utcnow()
                job.progress = 10

                self._update_job_in_db(db, job_id, job.status, job.progress)

                # Esegui il task
                if asyncio.iscoroutinefunction(job.task_func):
                    result = await job.task_func(**job.kwargs)
                else:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, lambda: job.task_func(**job.kwargs))

                # Aggiorna con successo
                job.status = 'completed'
                job.progress = 100
                job.result = result
                job.completed_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()

                self._update_job_in_db(
                    db, job_id, job.status, job.progress,
                    result=result, completed_at=job.completed_at
                )

            except Exception as e:
                # Aggiorna con errore
                job.status = 'failed'
                job.error = str(e)
                job.updated_at = datetime.utcnow()
                job.completed_at = datetime.utcnow()

                self._update_job_in_db(
                    db, job_id, job.status, job.progress,
                    error=str(e), completed_at=job.completed_at
                )
            finally:
                db.close()

    def _update_job_in_db(
        self,
        db: DBSession,
        job_id: str,
        status: str,
        progress: int,
        result: Optional[str] = None,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> None:
        """Aggiorna lo stato del job nel database."""
        db_job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
        if db_job:
            db_job.status = status
            db_job.progress = progress
            db_job.updated_at = datetime.utcnow()
            if result is not None:
                db_job.result = result
            if error is not None:
                db_job.error = error
            if completed_at is not None:
                db_job.completed_at = completed_at
            db.commit()

    def get_job(self, job_id: str, user_id: Optional[str] = None) -> Optional[Job]:
        """
        Ottiene un job dalla cache o dal database.

        Args:
            job_id: ID del job.
            user_id: ID dell'utente (opzionale, per verifica proprietà).

        Returns:
            Il job o None se non esiste.
        """
        # Prima controlla la cache
        with self._lock:
            if job_id in self._active_jobs:
                job = self._active_jobs[job_id]
                if user_id and job.user_id != user_id:
                    return None
                return job

        # Poi controlla il database
        db = self._get_db()
        try:
            query = db.query(JobModel).filter(JobModel.job_id == job_id)
            if user_id:
                query = query.filter(JobModel.user_id == user_id)

            db_job = query.first()
            if db_job:
                # Crea un oggetto Job fittizio dal database
                job = Job(
                    job_id=db_job.job_id,
                    session_id=db_job.session.session_id if db_job.session else "",
                    user_id=str(db_job.user_id),
                    job_type=db_job.job_type,
                    task_func=lambda: None,  # Placeholder
                    db_session_id=str(db_job.session_id)
                )
                job.status = db_job.status
                job.progress = db_job.progress
                job.result = db_job.result
                job.error = db_job.error
                job.created_at = db_job.created_at
                job.updated_at = db_job.updated_at
                job.completed_at = db_job.completed_at
                return job
            return None
        finally:
            db.close()

    def get_job_status(self, job_id: str, user_id: Optional[str] = None) -> Optional[dict]:
        """
        Ottiene lo stato di un job.

        Args:
            job_id: ID del job.
            user_id: ID dell'utente (opzionale).

        Returns:
            Dizionario con lo stato del job o None se non esiste.
        """
        job = self.get_job(job_id, user_id)
        return job.to_dict() if job else None

    def get_session_jobs(self, session_id: str, user_id: Optional[str] = None) -> List[dict]:
        """
        Ottiene tutti i job di una sessione.

        Args:
            session_id: ID della sessione.
            user_id: ID dell'utente (opzionale).

        Returns:
            Lista di dizionari con lo stato dei job.
        """
        db = self._get_db()
        try:
            # Trova la sessione
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            if not session:
                return []

            query = db.query(JobModel).filter(JobModel.session_id == session.id)
            if user_id:
                query = query.filter(JobModel.user_id == user_id)

            jobs = query.order_by(JobModel.created_at.desc()).all()
            return [job.to_dict() for job in jobs]
        finally:
            db.close()

    def get_all_jobs(self, user_id: Optional[str] = None) -> List[dict]:
        """
        Ottiene tutti i job.

        Args:
            user_id: Se specificato, filtra per utente.

        Returns:
            Lista di dizionari con lo stato di tutti i job.
        """
        db = self._get_db()
        try:
            query = db.query(JobModel)
            if user_id:
                query = query.filter(JobModel.user_id == user_id)

            jobs = query.order_by(JobModel.created_at.desc()).all()
            return [job.to_dict() for job in jobs]
        finally:
            db.close()

    def get_user_jobs(self, user_id: str) -> List[dict]:
        """
        Ottiene tutti i job di un utente.

        Args:
            user_id: ID dell'utente.

        Returns:
            Lista di dizionari con lo stato dei job.
        """
        return self.get_all_jobs(user_id)

    def delete_job(self, job_id: str, user_id: Optional[str] = None) -> bool:
        """
        Elimina un job.

        Args:
            job_id: ID del job da eliminare.
            user_id: ID dell'utente (opzionale, per verifica proprietà).

        Returns:
            True se eliminato, False altrimenti.
        """
        db = self._get_db()
        try:
            with self._lock:
                # Rimuovi dalla cache
                if job_id in self._active_jobs:
                    job = self._active_jobs[job_id]
                    if user_id and job.user_id != user_id:
                        return False
                    if job._task and not job._task.done():
                        job._task.cancel()
                    del self._active_jobs[job_id]

            # Rimuovi dal database
            query = db.query(JobModel).filter(JobModel.job_id == job_id)
            if user_id:
                query = query.filter(JobModel.user_id == user_id)

            db_job = query.first()
            if db_job:
                db.delete(db_job)
                db.commit()
                return True
            return False
        finally:
            db.close()

    def cleanup_completed_jobs(self, max_age_hours: int = 24) -> int:
        """
        Rimuove i job completati da più di max_age_hours.

        Args:
            max_age_hours: Età massima in ore per mantenere un job completato.

        Returns:
            Numero di job rimossi.
        """
        db = self._get_db()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

            # Rimuovi dalla cache
            with self._lock:
                to_remove = []
                for job_id, job in self._active_jobs.items():
                    if job.status in ['completed', 'failed'] and job.completed_at:
                        if job.completed_at < cutoff:
                            to_remove.append(job_id)
                for job_id in to_remove:
                    del self._active_jobs[job_id]

            # Rimuovi dal database
            old_jobs = db.query(JobModel).filter(
                JobModel.status.in_(['completed', 'failed']),
                JobModel.completed_at < cutoff
            ).all()

            count = len(old_jobs)
            for job in old_jobs:
                db.delete(job)
            db.commit()

            return count
        finally:
            db.close()

    def get_active_jobs_count(self, user_id: Optional[str] = None) -> int:
        """
        Restituisce il numero di job attivi (in esecuzione o in coda).

        Args:
            user_id: Se specificato, conta solo i job dell'utente.

        Returns:
            Numero di job attivi.
        """
        db = self._get_db()
        try:
            query = db.query(JobModel).filter(
                JobModel.status.in_(['pending', 'training', 'generating'])
            )
            if user_id:
                query = query.filter(JobModel.user_id == user_id)
            return query.count()
        finally:
            db.close()

    def get_job_count(self, user_id: Optional[str] = None) -> int:
        """
        Restituisce il numero totale di job.

        Args:
            user_id: Se specificato, conta solo i job dell'utente.

        Returns:
            Numero di job.
        """
        db = self._get_db()
        try:
            query = db.query(JobModel)
            if user_id:
                query = query.filter(JobModel.user_id == user_id)
            return query.count()
        finally:
            db.close()


# Singleton instance
job_manager = JobManager(max_concurrent_jobs=10)
