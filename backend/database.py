"""
Configurazione Database Supabase con SQLAlchemy.

Supabase utilizza PostgreSQL, quindi SQLAlchemy funziona perfettamente.
La connessione avviene tramite la connection string di Supabase.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

load_dotenv()

# Configurazione Database Supabase
# Formato: postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
# Oppure usa la connection string diretta dal pannello Supabase
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/postgres"
)

# URL asincrono per asyncpg (Supabase)
# Supabase supporta sia connessioni dirette che pooled
# Per asyncpg, usa la porta 5432 (connessione diretta) invece di 6543 (pooler)
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Se usi Supabase con pooler (porta 6543), potresti dover usare la connessione diretta per async
# In tal caso, imposta DATABASE_URL_DIRECT nel .env per la connessione asincrona

# Engine sincrono (per Alembic e operazioni sincrone)
# Usa NullPool per Supabase per evitare problemi con il connection pooling
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,  # Verifica connessione prima dell'uso
    poolclass=NullPool   # Disabilita pooling locale (Supabase ha il suo)
)

# Engine asincrono (per FastAPI)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool
)

# Session Factory sincrona
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Session Factory asincrona
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base per i modelli
Base = declarative_base()


def get_db():
    """
    Dependency per ottenere una sessione database sincrona.
    Usato per operazioni sincrone con Supabase.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """
    Dependency per ottenere una sessione database asincrona.
    Usato per operazioni async con Supabase.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db():
    """
    Inizializza il database creando tutte le tabelle.

    NOTA IMPORTANTE per Supabase:
    - NON usare questa funzione con Supabase!
    - Invece, esegui il file init_supabase.sql nel SQL Editor di Supabase
    - Questo garantisce che ENUM types, triggers e RLS siano configurati correttamente

    Questa funzione è mantenuta solo per sviluppo locale con PostgreSQL standard.
    """
    from db_models import Base
    Base.metadata.create_all(bind=engine)


def test_connection():
    """
    Testa la connessione al database Supabase.
    Utile per verificare che la configurazione sia corretta.
    """
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return True
    except Exception as e:
        print(f"Errore connessione database: {e}")
        return False
