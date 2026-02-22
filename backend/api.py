"""
FastAPI Application per StyleForge.

API scalabile per la generazione di contenuti con Claude Opus 4.5.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
import shutil

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import uvicorn

from models import (
    TrainingRequest, TrainingResponse,
    GenerationRequest, GenerationResponse,
    HumanizeRequest, HumanizeResponse,
    AntiAICorrectionRequest, AntiAICorrectionResponse,
    CompilatioScanRequest, CompilatioScanResponse, CompilatioScanResult, CompilatioScanListResponse,
    RenameRequest,
    JobStatusResponse, SessionInfo, SessionListResponse,
    ErrorResponse, HealthResponse,
    JobStatus, JobType,
    CreditEstimateRequest, CreditEstimateResponse,
)
from session_manager import session_manager
from job_manager import job_manager
from claude_client import lettura_pdf
from helper_calcifer import calcifer, get_contextual_tip
from auth import get_current_user, get_current_active_user, require_permission
from auth_routes import router as auth_router
from thesis_routes import router as thesis_router
from admin_routes import router as admin_router
from db_models import User
from database import init_db, get_db
from ai_exceptions import InsufficientCreditsError
from credits import estimate_credits, deduct_credits, is_admin_user
import config
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Valida configurazione all'avvio
config.validate_config()

# Inizializza FastAPI
app = FastAPI(
    title=config.API_TITLE,
    description=config.API_DESCRIPTION,
    version=config.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - Configurazione permissiva per sviluppo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permetti tutte le origini in sviluppo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra router autenticazione
app.include_router(auth_router)

# Registra router tesi
app.include_router(thesis_router)

# Registra router admin
app.include_router(admin_router)


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def cleanup_old_data():
    """Task in background per pulire dati vecchi."""
    while True:
        try:
            # Pulisci job completati
            removed_jobs = job_manager.cleanup_completed_jobs(config.JOB_CLEANUP_HOURS)
            if removed_jobs > 0:
                print(f"Rimossi {removed_jobs} job vecchi")

            # Pulisci sessioni inattive
            removed_sessions = session_manager.cleanup_old_sessions(config.SESSION_CLEANUP_HOURS)
            if removed_sessions > 0:
                print(f"Rimosse {removed_sessions} sessioni inattive")

            # Attendi 1 ora prima del prossimo cleanup
            await asyncio.sleep(3600)

        except Exception as e:
            print(f"Errore nel cleanup: {e}")
            await asyncio.sleep(60)


@app.on_event("startup")
async def startup_event():
    """Esegue task all'avvio dell'applicazione."""
    # Inizializza database
    try:
        init_db()
        print("Database inizializzato")
    except Exception as e:
        print(f"Avviso: impossibile inizializzare il database: {e}")

    # Avvia task di cleanup in background
    asyncio.create_task(cleanup_old_data())
    print(f"StyleForge API v{config.API_VERSION} avviata")
    print(f"Sessioni attive: {session_manager.get_session_count()}")
    print(f"Job attivi: {job_manager.get_active_jobs_count()}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Restituisce lo stato dell'applicazione e statistiche sull'utilizzo.
    """
    return HealthResponse(
        status="healthy",
        version=config.API_VERSION,
        active_sessions=session_manager.get_session_count(),
        active_jobs=job_manager.get_active_jobs_count()
    )


# ============================================================================
# SESSION ENDPOINTS
# ============================================================================

@app.post("/sessions", response_model=SessionInfo, tags=["Sessions"])
async def create_session(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Crea una nuova sessione.

    Una sessione mantiene il contesto della conversazione con Claude.
    Ogni sessione è indipendente e può essere addestrata separatamente.
    """
    try:
        new_session_id = session_manager.create_session(
            user_id=str(current_user.id),
            session_id=session_id
        )
        session_data = session_manager.get_all_sessions(str(current_user.id))[new_session_id]

        return SessionInfo(**session_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/sessions", response_model=SessionListResponse, tags=["Sessions"])
async def list_sessions(current_user: User = Depends(get_current_active_user)):
    """
    Elenca tutte le sessioni attive dell'utente.

    Restituisce informazioni su tutte le sessioni con i loro stati.
    """
    sessions_data = session_manager.get_all_sessions(str(current_user.id))
    sessions = [SessionInfo(**data) for data in sessions_data.values()]

    return SessionListResponse(
        sessions=sessions,
        total=len(sessions)
    )


@app.get("/sessions/{session_id}", response_model=SessionInfo, tags=["Sessions"])
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Ottiene informazioni su una sessione specifica.
    """
    if not session_manager.session_exists(session_id, str(current_user.id)):
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")

    session_data = session_manager.get_all_sessions(str(current_user.id))[session_id]
    return SessionInfo(**session_data)


@app.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Elimina una sessione e tutti i suoi dati.
    """
    if not session_manager.session_exists(session_id, str(current_user.id)):
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")

    session_manager.delete_session(session_id, str(current_user.id))
    return {"message": f"Sessione {session_id} eliminata con successo"}


# ============================================================================
# TRAINING ENDPOINTS
# ============================================================================

def train_session_task(session_id: str, file_path: Path, max_pages: int) -> str:
    """
    Task sincrono per l'addestramento di una sessione.

    Args:
        session_id: ID della sessione.
        file_path: Percorso del file PDF.
        max_pages: Numero massimo di pagine da leggere.

    Returns:
        Risposta di Claude dopo l'addestramento.
    """
    import PyPDF2
    import re

    # Estrai titolo dal PDF (prima pagina)
    try:
        with open(file_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            if len(pdf_reader.pages) > 0:
                first_page = pdf_reader.pages[0].extract_text()
                # Prendi le prime 3 righe non vuote come potenziale titolo
                lines = [line.strip() for line in first_page.split('\n') if line.strip()]
                if lines:
                    # Prendi la riga più lunga tra le prime 3 (spesso è il titolo)
                    title_candidates = lines[:3]
                    title = max(title_candidates, key=len)
                    # Pulisci il titolo e limita la lunghezza
                    title = re.sub(r'[^\w\s\-àèéìòù]', '', title)
                    title = title[:50].strip()
                    if title:
                        session_manager.set_session_name(session_id, title)
    except Exception as e:
        print(f"Errore nell'estrazione del titolo: {e}")
        # Usa il nome del file come fallback
        session_manager.set_session_name(session_id, file_path.stem[:50])

    client = session_manager.get_session(session_id)
    result = client.addestramento(str(file_path))

    # Salva la conversation history e lo stato trained
    session_manager.save_conversation_history(session_id)
    session_manager.set_session_trained(session_id, True)

    return result


@app.post("/train", response_model=TrainingResponse, tags=["Training"])
async def train_session(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    max_pages: int = Form(50),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(require_permission('train')),
    db: Session = Depends(get_db)
):
    """
    Addestra una sessione caricando un file PDF.

    Il file viene analizzato e utilizzato per "addestrare" Claude sullo stile
    di scrittura dell'autore. L'operazione viene eseguita in background.

    **Workflow:**
    1. Carica un file PDF
    2. Ricevi un job_id
    3. Monitora lo stato con GET /jobs/{job_id}
    4. Quando completato, la sessione è pronta per generare contenuti
    """
    # Valida file
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Solo file PDF sono supportati"
        )

    # Salva file temporaneamente
    file_path = config.UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel salvataggio del file: {e}")

    # Deduzione crediti
    credit_estimate = estimate_credits('train', {'max_pages': max_pages}, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate['credits_needed'],
        operation_type='train',
        description=f"Addestramento modello ({max_pages} pagine)",
        db=db
    )

    # Crea o recupera sessione
    user_id = str(current_user.id)
    if session_id and session_manager.session_exists(session_id, user_id):
        session_id = session_id
    else:
        session_id = session_manager.create_session(user_id, session_id)

    # Crea job con nome auto-generato
    job_name = f"Training: {file.filename}"
    job_id = job_manager.create_job(
        session_id=session_id,
        user_id=user_id,
        job_type='training',
        task_func=train_session_task,
        name=job_name,
        file_path=file_path,
        max_pages=max_pages
    )

    # Aggiungi job alla sessione
    session_manager.add_job_to_session(session_id, job_id)

    # Esegui job in background
    background_tasks.add_task(job_manager.execute_job, job_id)

    return TrainingResponse(
        session_id=session_id,
        job_id=job_id,
        status='pending',
        message=f"Training avviato. Monitora lo stato con GET /jobs/{job_id}",
        created_at=datetime.now()
    )


# ============================================================================
# GENERATION ENDPOINTS
# ============================================================================

def generate_content_task(
    session_id: str,
    argomento: str,
    numero_parole: int,
    destinatario: str
) -> str:
    """
    Task sincrono per la generazione di contenuto.

    Args:
        session_id: ID della sessione.
        argomento: Argomento del contenuto.
        numero_parole: Numero di parole.
        destinatario: Pubblico destinatario.

    Returns:
        Contenuto generato da Claude.
    """
    client = session_manager.get_session(session_id)
    result = client.generazione(
        argomento=argomento,
        numero_parole=numero_parole,
        destinatario=destinatario
    )

    # Salva la conversation history
    session_manager.save_conversation_history(session_id)

    return result


@app.post("/generate", response_model=GenerationResponse, tags=["Generation"])
async def generate_content(
    request: GenerationRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(require_permission('generate')),
    db: Session = Depends(get_db)
):
    """
    Genera contenuto basato su una sessione addestrata.

    La sessione deve essere stata addestrata precedentemente con un file PDF.

    **Workflow:**
    1. Assicurati che la sessione sia stata addestrata
    2. Invia la richiesta di generazione
    3. Ricevi un job_id
    4. Monitora lo stato con GET /jobs/{job_id}
    5. Recupera il contenuto generato quando completato
    """
    user_id = str(current_user.id)

    # Verifica che la sessione esista
    if not session_manager.session_exists(request.session_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=f"Sessione {request.session_id} non trovata"
        )

    # Verifica che la sessione sia addestrata
    client = session_manager.get_session(request.session_id, user_id)
    if not client.is_trained:
        raise HTTPException(
            status_code=400,
            detail=f"Sessione {request.session_id} non ancora addestrata. Esegui prima il training."
        )

    # Deduzione crediti
    credit_estimate = estimate_credits('generate', {'numero_parole': request.numero_parole}, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate['credits_needed'],
        operation_type='generate',
        description=f"Generazione contenuto ({request.numero_parole} parole, tema: {request.argomento[:50]})",
        db=db
    )

    # Crea job con nome auto-generato
    job_name = f"Generazione: {request.argomento[:50]} (~{request.numero_parole} parole)"
    job_id = job_manager.create_job(
        session_id=request.session_id,
        user_id=user_id,
        job_type='generation',
        task_func=generate_content_task,
        name=job_name,
        argomento=request.argomento,
        numero_parole=request.numero_parole,
        destinatario=request.destinatario
    )

    # Aggiungi job alla sessione
    session_manager.add_job_to_session(request.session_id, job_id)

    # Esegui job in background
    background_tasks.add_task(job_manager.execute_job, job_id)

    return GenerationResponse(
        session_id=request.session_id,
        job_id=job_id,
        status='pending',
        message=f"Generazione avviata. Monitora lo stato con GET /jobs/{job_id}",
        created_at=datetime.now()
    )


# ============================================================================
# HUMANIZE ENDPOINTS
# ============================================================================

def humanize_content_task(
    session_id: str,
    testo: str
) -> str:
    """
    Task sincrono per l'umanizzazione di un testo AI.

    Args:
        session_id: ID della sessione addestrata.
        testo: Il testo generato da AI da riscrivere.

    Returns:
        Testo riscritto nello stile appreso e non rilevabile dai detector.
    """
    client = session_manager.get_session(session_id)
    result = client.umanizzazione(testo_originale=testo)

    # Salva la conversation history
    session_manager.save_conversation_history(session_id)

    return result


@app.post("/humanize", response_model=HumanizeResponse, tags=["Humanize"])
async def humanize_content(
    request: HumanizeRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(require_permission('humanize')),
    db: Session = Depends(get_db)
):
    """
    Riscrive un testo generato da AI per renderlo non rilevabile dai detector AI.

    Questa funzionalità RICHIEDE una sessione addestrata. Prende un testo
    generato da intelligenza artificiale e lo riscrive applicando:
    1. Lo STILE DELL'AUTORE appreso durante l'addestramento
    2. Tecniche avanzate per aumentare la perplessità e la burstiness

    **Obiettivo:** Superare i controlli di Compilatio, GPTZero e altri
    detector AI, mantenendo lo stile dell'autore.

    **Workflow:**
    1. Assicurati che la sessione sia stata addestrata
    2. Invia il testo da umanizzare
    3. Ricevi un job_id
    4. Monitora lo stato con GET /jobs/{job_id}
    5. Recupera il testo umanizzato quando completato
    """
    user_id = str(current_user.id)

    # Verifica che la sessione esista
    if not session_manager.session_exists(request.session_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=f"Sessione {request.session_id} non trovata"
        )

    # Verifica che la sessione sia addestrata
    client = session_manager.get_session(request.session_id, user_id)
    if not client.is_trained:
        raise HTTPException(
            status_code=400,
            detail=f"Sessione {request.session_id} non ancora addestrata. Esegui prima il training."
        )

    # Deduzione crediti
    credit_estimate = estimate_credits('humanize', {'text_length': len(request.testo)}, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate['credits_needed'],
        operation_type='humanize',
        description=f"Umanizzazione testo ({len(request.testo)} caratteri)",
        db=db
    )

    # Crea job con nome auto-generato
    testo_preview = request.testo[:40].replace('\n', ' ')
    job_name = f"Umanizzazione: {testo_preview}..."
    job_id = job_manager.create_job(
        session_id=request.session_id,
        user_id=user_id,
        job_type='humanization',
        task_func=humanize_content_task,
        name=job_name,
        testo=request.testo
    )

    # Aggiungi job alla sessione
    session_manager.add_job_to_session(request.session_id, job_id)

    # Esegui job in background
    background_tasks.add_task(job_manager.execute_job, job_id)

    return HumanizeResponse(
        session_id=request.session_id,
        job_id=job_id,
        status='pending',
        message=f"Umanizzazione avviata. Monitora lo stato con GET /jobs/{job_id}",
        created_at=datetime.now()
    )


# ============================================================================
# ANTI-AI CORRECTION ENDPOINTS
# ============================================================================

def anti_ai_correction_task(testo: str) -> str:
    """
    Task sincrono per la correzione Anti-AI.

    Applica solo micro-modifiche conservative al testo per ridurre
    la rilevabilità AI, senza riscriverlo completamente.

    Args:
        testo: Il testo da correggere.

    Returns:
        Testo corretto con micro-modifiche.
    """
    from ai_client import anti_ai_correction
    return anti_ai_correction(testo)


@app.post("/anti-ai-correction", response_model=AntiAICorrectionResponse, tags=["Anti-AI Correction"])
async def anti_ai_correction_endpoint(
    request: AntiAICorrectionRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(require_permission('humanize')),
    db: Session = Depends(get_db)
):
    """
    Correzione Anti-AI: micro-modifiche conservative per ridurre la rilevabilità AI.

    A differenza dell'umanizzazione completa (che riscrive nello stile dell'autore),
    questa funzione fa SOLO piccole modifiche mirate:
    - Sostituzioni sinonimiche (max 10-15% delle parole)
    - Leggere variazioni sintattiche
    - Variazione punteggiatura
    - Inserimento di piccole imperfezioni naturali

    Il testo originale viene mantenuto al 90%+.

    **NON richiede una sessione addestrata.**
    """
    user_id = str(current_user.id)

    # Deduzione crediti (stessa logica humanize)
    credit_estimate = estimate_credits('humanize', {'text_length': len(request.testo)}, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate['credits_needed'],
        operation_type='humanize',
        description=f"Correzione Anti-AI ({len(request.testo)} caratteri)",
        db=db
    )

    # Crea job SENZA sessione, con nome auto-generato
    testo_preview = request.testo[:40].replace('\n', ' ')
    job_name = f"Correzione Anti-AI: {testo_preview}..."
    job_id = job_manager.create_job(
        session_id=None,
        user_id=user_id,
        job_type='humanization',
        task_func=anti_ai_correction_task,
        name=job_name,
        testo=request.testo
    )

    # Esegui job in background
    background_tasks.add_task(job_manager.execute_job, job_id)

    return AntiAICorrectionResponse(
        job_id=job_id,
        status='pending',
        message=f"Correzione Anti-AI avviata. Monitora lo stato con GET /jobs/{job_id}",
        created_at=datetime.now()
    )


# ============================================================================
# COMPILATIO SCAN ENDPOINTS (Admin-only)
# ============================================================================

from auth import get_current_admin_user
from compilatio_service import get_compilatio_service, CompilatioService
from db_models import CompilatioScan
import uuid as uuid_module


def compilatio_scan_task(
    text: str,
    scan_user_id: str = None,
    scan_job_id: str = None,
    source_type: str = None,
    source_job_id: str = None
) -> str:
    """
    Task sincrono per la scansione Compilatio.
    Viene eseguito in background dal job_manager.
    """
    service = get_compilatio_service()

    # Contatore per limitare gli aggiornamenti DB (ogni 5 chiamate)
    _progress_state = {"count": 0, "last_db_update": 0}

    def progress_callback(progress: int):
        """Aggiorna il progresso del job. Scrive in DB solo periodicamente per evitare connection exhaustion."""
        try:
            # Aggiorna sempre in memoria (leggero, no DB)
            job = job_manager._active_jobs.get(scan_job_id)
            if job:
                job.progress = progress

            # Scrivi in DB solo ogni 5 callback o al 100%, per evitare connection exhaustion con NullPool
            _progress_state["count"] += 1
            should_write_db = (
                _progress_state["count"] % 5 == 0 or
                progress >= 100 or
                progress - _progress_state["last_db_update"] >= 20
            )

            if should_write_db:
                _progress_state["last_db_update"] = progress
                from database import SessionLocal
                from db_models import Job as JobModel
                db = SessionLocal()
                try:
                    db_job = db.query(JobModel).filter_by(job_id=scan_job_id).first()
                    if db_job:
                        db_job.progress = progress
                        db.commit()
                finally:
                    db.close()
        except Exception:
            pass

    return service.scan_text(
        text=text,
        user_id=scan_user_id,
        job_id=scan_job_id,
        source_type=source_type,
        source_job_id=source_job_id,
        progress_callback=progress_callback
    )


@app.post("/compilatio/scan", response_model=CompilatioScanResponse, tags=["Compilatio"])
async def compilatio_scan(
    request: CompilatioScanRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Avvia una scansione Compilatio per rilevare contenuto AI e plagio.

    **Solo admin.** Il testo viene convertito in PDF e inviato a Compilatio per analisi.
    I risultati includono percentuali di AI, similarità, plagio e un report PDF dettagliato.

    Se il testo è già stato scansionato (dedup via hash), ritorna il risultato cached.
    """
    user_id = str(current_user.id)

    # Check dedup: se esiste già una scansione per questo testo
    text_hash = CompilatioService.compute_text_hash(request.text)
    existing = CompilatioService.check_existing_scan(text_hash, user_id, db)
    if existing:
        return CompilatioScanResponse(
            job_id=existing.get("job_id", "cached"),
            status="completed",
            message="Risultato trovato in cache (scansione già effettuata per questo testo)",
            created_at=existing.get("created_at", datetime.now()),
            cached=True,
            cached_scan=existing
        )

    # Stima e deduzione crediti
    credit_estimate = estimate_credits('compilatio_scan', {'text_length': len(request.text)}, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate['credits_needed'],
        operation_type='compilatio_scan',
        description=f"Scansione Compilatio ({len(request.text)} caratteri)",
        db=db
    )

    # Pre-genera job_id per passarlo alla task function
    pre_job_id = f"job_{uuid_module.uuid4().hex[:12]}"

    # Crea job
    text_preview = request.text[:40].replace('\n', ' ')
    job_name = f"Compilatio Scan: {text_preview}..."
    job_id = job_manager.create_job(
        session_id=None,
        user_id=user_id,
        job_type='compilatio_scan',
        task_func=compilatio_scan_task,
        job_id=pre_job_id,
        name=job_name,
        text=request.text,
        scan_user_id=user_id,
        scan_job_id=pre_job_id,
        source_type=request.source_type,
        source_job_id=request.source_job_id
    )

    # Esegui in background
    background_tasks.add_task(job_manager.execute_job, job_id)

    return CompilatioScanResponse(
        job_id=job_id,
        status='pending',
        message=f"Scansione Compilatio avviata. Monitora lo stato con GET /jobs/{job_id}",
        created_at=datetime.now(),
        cached=False
    )


@app.get("/compilatio/scans", response_model=CompilatioScanListResponse, tags=["Compilatio"])
async def list_compilatio_scans(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Lista tutte le scansioni Compilatio dell'utente admin.
    Ordinate per data di creazione decrescente.
    """
    user_id = current_user.id

    total = db.query(CompilatioScan).filter(
        CompilatioScan.user_id == user_id,
        CompilatioScan.completed_at.isnot(None)
    ).count()

    scans = db.query(CompilatioScan).filter(
        CompilatioScan.user_id == user_id,
        CompilatioScan.completed_at.isnot(None)
    ).order_by(
        CompilatioScan.created_at.desc()
    ).offset(offset).limit(limit).all()

    return CompilatioScanListResponse(
        scans=[s.to_dict() for s in scans],
        total=total
    )


@app.get("/compilatio/report/{scan_id}", tags=["Compilatio"])
async def download_compilatio_report(
    scan_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Scarica il report PDF di una scansione Compilatio.
    """
    scan = db.query(CompilatioScan).filter(
        CompilatioScan.id == scan_id,
    ).first()

    if not scan:
        raise HTTPException(status_code=404, detail="Scansione non trovata")

    if not scan.report_pdf_path or not Path(scan.report_pdf_path).exists():
        raise HTTPException(status_code=404, detail="Report PDF non disponibile")

    return FileResponse(
        path=scan.report_pdf_path,
        media_type="application/pdf",
        filename=f"compilatio_report_{scan_id[:8]}.pdf"
    )


@app.get("/compilatio/scan-by-source/{source_job_id}", tags=["Compilatio"])
async def get_scan_by_source(
    source_job_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Recupera la scansione Compilatio associata a un job sorgente.
    Utile per mostrare i risultati nella Dashboard accanto al job originale.
    """
    scan = db.query(CompilatioScan).filter(
        CompilatioScan.source_job_id == source_job_id,
        CompilatioScan.completed_at.isnot(None)
    ).order_by(CompilatioScan.created_at.desc()).first()

    if not scan:
        return {"scan": None}

    return {"scan": scan.to_dict()}


@app.get("/compilatio/scans-by-sources", tags=["Compilatio"])
async def get_scans_by_sources(
    source_job_ids: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Recupera le scansioni Compilatio per multipli job sorgente in una sola chiamata.
    source_job_ids: stringa con ID separati da virgola.
    """
    ids = [s.strip() for s in source_job_ids.split(",") if s.strip()]
    if not ids:
        return {"scans": {}}

    scans = db.query(CompilatioScan).filter(
        CompilatioScan.source_job_id.in_(ids),
        CompilatioScan.completed_at.isnot(None)
    ).all()

    # Mappa source_job_id -> scan (prendi il piu' recente per ogni source)
    result = {}
    for scan in scans:
        sid = scan.source_job_id
        if sid not in result or scan.created_at > result[sid].created_at:
            result[sid] = scan

    return {"scans": {k: v.to_dict() for k, v in result.items()}}


# ============================================================================
# RENAME ENDPOINTS
# ============================================================================

@app.patch("/sessions/{session_id}/name", tags=["Sessions"])
async def rename_session(
    session_id: str,
    request: RenameRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Rinomina una sessione.

    Permette di impostare un nome descrittivo personalizzato per la sessione.
    """
    user_id = str(current_user.id)

    # Verifica che la sessione esista e appartenga all'utente
    if not session_manager.session_exists(session_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=f"Sessione {session_id} non trovata"
        )

    session_manager.set_session_name(session_id, request.name)
    return {"message": "Nome sessione aggiornato", "name": request.name}


@app.patch("/jobs/{job_id}/name", tags=["Jobs"])
async def rename_job(
    job_id: str,
    request: RenameRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Rinomina un job.

    Permette di impostare un nome descrittivo personalizzato per il job.
    """
    from db_models import Job as JobModel

    user_id = str(current_user.id)

    # Verifica che il job esista e appartenga all'utente
    db_job = db.query(JobModel).filter(
        JobModel.job_id == job_id,
        JobModel.user_id == user_id
    ).first()

    if not db_job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} non trovato"
        )

    db_job.name = request.name
    db_job.updated_at = datetime.utcnow()
    db.commit()

    # Aggiorna anche in memoria se presente
    job = job_manager._active_jobs.get(job_id)
    if job:
        job.name = request.name

    return {"message": "Nome job aggiornato", "name": request.name}


# ============================================================================
# CREDITS ENDPOINTS
# ============================================================================

@app.post("/credits/estimate", response_model=CreditEstimateResponse, tags=["Credits"])
async def estimate_operation_credits(
    request: CreditEstimateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Stima i crediti necessari per un'operazione PRIMA di eseguirla.
    L'utente deve confermare prima di procedere.
    """
    result = estimate_credits(request.operation_type, request.params, db=db)

    is_admin = is_admin_user(current_user)
    current_balance = -1 if is_admin else current_user.credits  # -1 = infiniti

    return CreditEstimateResponse(
        credits_needed=result['credits_needed'],
        breakdown=result['breakdown'],
        current_balance=current_balance,
        sufficient=is_admin or current_user.credits >= result['credits_needed']
    )


# ============================================================================
# JOB ENDPOINTS
# ============================================================================

@app.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Ottiene lo stato di un job.

    Restituisce informazioni dettagliate sullo stato corrente del job,
    incluso il risultato se completato.
    """
    job_status = job_manager.get_job_status(job_id, str(current_user.id))

    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} non trovato")

    return JobStatusResponse(**job_status)


@app.get("/jobs", tags=["Jobs"])
async def list_jobs(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Elenca tutti i job dell'utente, opzionalmente filtrati per sessione.
    """
    user_id = str(current_user.id)
    if session_id:
        jobs = job_manager.get_session_jobs(session_id, user_id)
    else:
        jobs = job_manager.get_all_jobs(user_id)

    return {"jobs": jobs, "total": len(jobs)}


@app.delete("/jobs/{job_id}", tags=["Jobs"])
async def delete_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Elimina un job.

    ATTENZIONE: Questa operazione cancellerà il job anche se in esecuzione.
    """
    job = job_manager.get_job(job_id, str(current_user.id))
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} non trovato")

    job_manager.delete_job(job_id, str(current_user.id))
    return {"message": f"Job {job_id} eliminato con successo"}



# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@app.get("/results/{job_id}", tags=["Results"])
async def download_result(
    job_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Scarica il risultato di un job come file PDF.

    Il contenuto generato viene restituito come file .pdf scaricabile.
    """
    import fitz  # PyMuPDF

    job = job_manager.get_job(job_id, str(current_user.id))

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} non trovato")

    if job.status != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} non ancora completato (stato: {job.status})"
        )

    if not job.result:
        raise HTTPException(
            status_code=404,
            detail=f"Nessun risultato disponibile per job {job_id}"
        )

    # Genera PDF con il contenuto
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = config.RESULTS_DIR / f"result_{job_id}_{timestamp}.pdf"

    # Crea documento PDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size in points

    # Configurazione testo
    font_size = 11
    line_height = font_size * 1.5
    margin_left = 50
    margin_right = 545
    margin_top = 50
    margin_bottom = 792

    # Inserisci il testo nel PDF
    text = job.result

    # Inserisci il testo con wrapping automatico
    text_rect = fitz.Rect(margin_left, margin_top, margin_right, margin_bottom)

    # Usa il metodo insert_textbox per inserire testo con wrapping
    result_code = page.insert_textbox(
        text_rect,
        text,
        fontsize=font_size,
        fontname="helv",
        align=fitz.TEXT_ALIGN_LEFT
    )

    # Se il testo è troppo lungo per una pagina, crea più pagine
    if result_code < 0:  # -1 significa che il testo è troppo lungo
        # Dividi il testo in paragrafi
        paragraphs = text.split('\n')
        doc = fitz.open()  # Ricrea il documento

        current_page = doc.new_page(width=595, height=842)
        y_position = margin_top

        for paragraph in paragraphs:
            if not paragraph.strip():
                y_position += line_height
                continue

            # Wrap del testo del paragrafo
            words = paragraph.split()
            lines = []
            current_line = []

            for word in words:
                test_line = ' '.join(current_line + [word])
                # Stima della larghezza (approssimativa)
                if len(test_line) * (font_size * 0.6) < (margin_right - margin_left):
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]

            if current_line:
                lines.append(' '.join(current_line))

            # Inserisci le righe
            for line in lines:
                if y_position + line_height > margin_bottom:
                    # Crea nuova pagina
                    current_page = doc.new_page(width=595, height=842)
                    y_position = margin_top

                current_page.insert_text(
                    (margin_left, y_position),
                    line,
                    fontsize=font_size,
                    fontname="helv"
                )
                y_position += line_height

            y_position += line_height * 0.5  # Spazio extra tra paragrafi

    # Salva il PDF
    doc.save(result_path)
    doc.close()

    return FileResponse(
        path=result_path,
        filename=f"contenuto_generato_{timestamp}.pdf",
        media_type="application/pdf"
    )


# ============================================================================
# CALCIFER HELPER ENDPOINTS
# ============================================================================

class CalciferChatRequest(BaseModel):
    """Richiesta di chat con Calcifer."""
    message: str
    conversation_id: Optional[str] = "default"
    context: Optional[dict] = None


class CalciferChatResponse(BaseModel):
    """Risposta di Calcifer."""
    response: str
    conversation_id: str
    timestamp: datetime


class CalciferTipRequest(BaseModel):
    """Richiesta di suggerimento contestuale."""
    page: str
    context: Optional[dict] = None


@app.post("/calcifer/chat", tags=["Calcifer"], response_model=CalciferChatResponse)
async def chat_with_calcifer(
    request: CalciferChatRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Chatta con Calcifer, l'assistente AI.

    Permette all'utente di fare domande e ricevere aiuto da Calcifer.
    """
    try:
        response = calcifer.get_response(
            user_message=request.message,
            conversation_id=request.conversation_id,
            context=request.context
        )

        return CalciferChatResponse(
            response=response,
            conversation_id=request.conversation_id,
            timestamp=datetime.now()
        )
    except InsufficientCreditsError as e:
        raise HTTPException(status_code=402, detail=e.user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calcifer/tip", tags=["Calcifer"])
async def get_tip(
    request: CalciferTipRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Ottiene un suggerimento contestuale da Calcifer.

    Utile per mostrare suggerimenti dinamici basati sulla pagina corrente.
    """
    try:
        tip = get_contextual_tip(
            page=request.page,
            context=request.context
        )

        return {"tip": tip}
    except InsufficientCreditsError as e:
        raise HTTPException(status_code=402, detail=e.user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/calcifer/conversation/{conversation_id}", tags=["Calcifer"])
async def clear_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Cancella la cronologia di una conversazione con Calcifer."""
    calcifer.clear_conversation(conversation_id)
    return {"message": "Conversazione cancellata"}


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(InsufficientCreditsError)
async def insufficient_credits_handler(request, exc: InsufficientCreditsError):
    """Handler per errori di crediti/quota AI insufficienti."""
    error_response = ErrorResponse(
        error="Crediti AI Insufficienti",
        detail=exc.user_message
    )
    return JSONResponse(
        status_code=402,
        content=error_response.model_dump(mode='json')
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handler generico per le eccezioni."""
    error_response = ErrorResponse(
        error="Internal Server Error",
        detail=str(exc)
    )
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(mode='json')
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level="info"
    )
