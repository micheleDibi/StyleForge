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
    JobStatusResponse, SessionInfo, SessionListResponse,
    DetectionRequest, DetectionResponse,
    ErrorResponse, HealthResponse,
    JobStatus, JobType
)
from session_manager import session_manager
from job_manager import job_manager
from claude_client import lettura_pdf
from helper_calcifer import calcifer, get_contextual_tip
from auth import get_current_user, get_current_active_user
from auth_routes import router as auth_router
from thesis_routes import router as thesis_router
from db_models import User
from database import init_db
import config
from pydantic import BaseModel

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
    current_user: User = Depends(get_current_active_user)
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

    # Crea o recupera sessione
    user_id = str(current_user.id)
    if session_id and session_manager.session_exists(session_id, user_id):
        session_id = session_id
    else:
        session_id = session_manager.create_session(user_id, session_id)

    # Crea job
    job_id = job_manager.create_job(
        session_id=session_id,
        user_id=user_id,
        job_type='training',
        task_func=train_session_task,
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
    current_user: User = Depends(get_current_active_user)
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

    # Crea job
    job_id = job_manager.create_job(
        session_id=request.session_id,
        user_id=user_id,
        job_type='generation',
        task_func=generate_content_task,
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
    current_user: User = Depends(get_current_active_user)
):
    """
    Riscrive un testo generato da AI per renderlo non rilevabile dai detector AI.

    Questa funzionalità RICHIEDE una sessione addestrata. Prende un testo
    generato da intelligenza artificiale e lo riscrive applicando:
    1. Lo STILE DELL'AUTORE appreso durante l'addestramento
    2. Tecniche avanzate per aumentare la perplessità e la burstiness

    **Obiettivo:** Superare i controlli di Compilatio, Copyleaks, GPTZero e altri
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

    # Crea job
    job_id = job_manager.create_job(
        session_id=request.session_id,
        user_id=user_id,
        job_type='humanization',
        task_func=humanize_content_task,
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
# AI DETECTION ENDPOINTS
# ============================================================================

@app.post("/detect", response_model=DetectionResponse, tags=["AI Detection"])
async def detect_ai_text(
    request: DetectionRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Rileva se un testo è stato generato da AI.

    Utilizza il metodo Binoculars per analizzare il testo e determinare
    se è stato generato da un'intelligenza artificiale.

    **Nota:** Questa operazione può richiedere tempo, specialmente al primo utilizzo
    quando i modelli devono essere caricati.
    """
    try:
        from detector import BinocularsDetector

        # Inizializza detector (potrebbe essere cachato in futuro)
        detector = BinocularsDetector(
            model_name=request.model_name,
            threshold=request.threshold
        )

        # Esegui rilevamento
        result = detector.detect(request.text)

        return DetectionResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel rilevamento: {str(e)}"
        )


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
