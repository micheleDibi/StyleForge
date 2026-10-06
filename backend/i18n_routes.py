"""
Router FastAPI per il multi-lingua (i18n).

- Endpoint pubblici (/api): elenco lingue attive + traduzioni di una lingua
  (usati dal frontend a runtime).
- Endpoint admin (/admin/languages): CRUD lingue, editor traduzioni, sync del
  catalogo base italiano, traduzione AI delle label vuote (in background).

Le traduzioni AI usano ai_client (Claude) e NON addebitano crediti (admin-only).
Il job di traduzione gira in BackgroundTasks con un dizionario di progresso in
memoria (niente job_manager: l'enum PG job_type è bloccato).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_admin_user
from database import get_db, SessionLocal
from db_models import Language, Translation, User
from models import (
    LanguageResponse, LanguageListResponse, LanguageCreateRequest, LanguageUpdateRequest,
    LanguageDetailResponse, TranslationEntry, TranslationsUpsertRequest,
    TranslateJobResponse, TranslateStatusResponse,
)

logger = logging.getLogger(__name__)

# Router pubblico (runtime frontend) e admin
public_router = APIRouter(prefix="/api", tags=["i18n"])
admin_router = APIRouter(prefix="/admin/languages", tags=["i18n admin"])

# Cache in-process delle traduzioni pubbliche: { code: {key: value} }
_public_cache: dict[str, dict] = {}

# Stato dei job di traduzione AI in memoria: { job_id: {status,total,done,error} }
_translate_jobs: dict[str, dict] = {}

AI_BATCH_SIZE = 40


def _invalidate_cache(code: str | None = None):
    if code is None:
        _public_cache.clear()
    else:
        _public_cache.pop(code, None)


def _upsert_translations(db: Session, language_code: str, items: dict) -> int:
    """Upsert in blocco di {key: value} per una lingua. Ritorna il numero di chiavi scritte."""
    existing = {
        t.key: t for t in db.query(Translation).filter(Translation.language_code == language_code).all()
    }
    for key, value in items.items():
        t = existing.get(key)
        if t:
            t.value = value
        else:
            db.add(Translation(language_code=language_code, key=key, value=value))
    db.commit()
    _invalidate_cache(language_code)
    return len(items)


# ============================================================================
# PUBBLICI
# ============================================================================

@public_router.get("/languages", response_model=LanguageListResponse)
def list_active_languages(db: Session = Depends(get_db)):
    """Lingue attive per lo switcher (pubblico)."""
    rows = (
        db.query(Language)
        .filter(Language.is_active == True)  # noqa: E712
        .order_by(Language.sort_order.asc(), Language.code.asc())
        .all()
    )
    return LanguageListResponse(languages=[LanguageResponse(**r.to_dict()) for r in rows])


@public_router.get("/translations/{code}")
def get_translations(code: str, db: Session = Depends(get_db)):
    """Mappa {chiave: valore} per una lingua (solo valori non vuoti). Cache in-process."""
    if code in _public_cache:
        return _public_cache[code]
    rows = db.query(Translation).filter(Translation.language_code == code).all()
    result = {t.key: t.value for t in rows if t.value}
    _public_cache[code] = result
    return result


# ============================================================================
# ADMIN — CRUD lingue
# ============================================================================

@admin_router.get("", response_model=LanguageListResponse)
def admin_list_languages(admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    rows = db.query(Language).order_by(Language.sort_order.asc(), Language.code.asc()).all()
    return LanguageListResponse(languages=[LanguageResponse(**r.to_dict()) for r in rows])


@admin_router.post("", response_model=TranslateJobResponse)
def admin_create_language(
    request: LanguageCreateRequest,
    background_tasks: BackgroundTasks,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    code = request.code.strip().lower()
    if db.query(Language).filter(Language.code == code).first():
        raise HTTPException(status_code=400, detail=f"La lingua '{code}' esiste già")
    lang = Language(
        code=code,
        name=request.name.strip(),
        native_name=request.native_name.strip(),
        flag_country_code=request.flag_country_code.strip().lower(),
        is_active=request.is_active,
        is_default=False,
        sort_order=request.sort_order,
    )
    db.add(lang)
    db.commit()

    job_id = ""
    message = "Lingua creata"
    if request.translate_all:
        job_id = _start_translate_job(code, background_tasks)
        message = "Lingua creata. Traduzione AI avviata."
    return TranslateJobResponse(job_id=job_id, message=message)


@admin_router.put("/{code}", response_model=LanguageResponse)
def admin_update_language(
    code: str,
    request: LanguageUpdateRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    lang = db.query(Language).filter(Language.code == code).first()
    if not lang:
        raise HTTPException(status_code=404, detail="Lingua non trovata")
    if request.name is not None:
        lang.name = request.name.strip()
    if request.native_name is not None:
        lang.native_name = request.native_name.strip()
    if request.flag_country_code is not None:
        lang.flag_country_code = request.flag_country_code.strip().lower()
    if request.is_active is not None:
        if lang.is_default and not request.is_active:
            raise HTTPException(status_code=400, detail="La lingua di default non può essere disattivata")
        lang.is_active = request.is_active
    if request.sort_order is not None:
        lang.sort_order = request.sort_order
    lang.updated_at = datetime.utcnow()
    db.commit()
    _invalidate_cache(code)
    return LanguageResponse(**lang.to_dict())


@admin_router.delete("/{code}")
def admin_delete_language(code: str, admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    lang = db.query(Language).filter(Language.code == code).first()
    if not lang:
        raise HTTPException(status_code=404, detail="Lingua non trovata")
    if lang.is_default:
        raise HTTPException(status_code=400, detail="La lingua di default non può essere eliminata")
    db.delete(lang)  # cascade rimuove le translations
    db.commit()
    _invalidate_cache(code)
    return {"message": "Lingua eliminata", "code": code}


# ============================================================================
# ADMIN — editor traduzioni
# ============================================================================

@admin_router.get("/{code}/detail", response_model=LanguageDetailResponse)
def admin_language_detail(
    code: str,
    search: str = Query(None),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Tutte le chiavi base (it) con i valori della lingua richiesta; marca i vuoti."""
    lang = db.query(Language).filter(Language.code == code).first()
    if not lang:
        raise HTTPException(status_code=404, detail="Lingua non trovata")

    base = db.query(Translation).filter(Translation.language_code == 'it').all()
    target = {t.key: t.value for t in db.query(Translation).filter(Translation.language_code == code).all()}

    entries = []
    translated = 0
    s = (search or "").strip().lower()
    for b in base:
        key = b.key
        val = target.get(key)
        is_empty = not val
        if not is_empty:
            translated += 1
        if s and s not in key.lower() and not (val and s in val.lower()):
            continue
        entries.append(TranslationEntry(key=key, value=val, is_empty=is_empty))

    total = len(base)
    return LanguageDetailResponse(
        language=LanguageResponse(**lang.to_dict()),
        entries=entries,
        total=total,
        translated=translated,
        empty=total - translated,
    )


@admin_router.put("/{code}/translations")
def admin_save_translations(
    code: str,
    request: TranslationsUpsertRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    lang = db.query(Language).filter(Language.code == code).first()
    if not lang:
        raise HTTPException(status_code=404, detail="Lingua non trovata")
    n = _upsert_translations(db, code, request.translations)
    return {"message": "Traduzioni salvate", "count": n}


@admin_router.post("/sync-base")
def admin_sync_base(
    request: TranslationsUpsertRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Aggiorna il catalogo base italiano (chiavi → testo italiano) dal it.json del frontend."""
    if not db.query(Language).filter(Language.code == 'it').first():
        db.add(Language(code='it', name='Italiano', native_name='Italiano',
                        flag_country_code='it', is_active=True, is_default=True, sort_order=0))
        db.commit()
    n = _upsert_translations(db, 'it', request.translations)
    return {"message": "Catalogo base sincronizzato", "count": n}


# ============================================================================
# ADMIN — traduzione AI (background + polling)
# ============================================================================

def _build_translate_prompt(native_name: str, code: str, batch: dict) -> str:
    return (
        f"Sei un traduttore professionista di interfacce software. Traduci dall'ITALIANO "
        f"alla lingua '{native_name}' (codice '{code}') le seguenti stringhe di UI di una web app.\n"
        f"Regole IMPORTANTI:\n"
        f"- Restituisci SOLO un oggetto JSON con le STESSE chiavi numeriche ricevute e come valori le traduzioni.\n"
        f"- Mantieni IDENTICI i segnaposto tra doppie graffe come {{{{nome}}}}: non tradurli, non spostarli.\n"
        f"- Preserva la punteggiatura finale e il tono conciso tipico di una UI.\n"
        f"- Non aggiungere spiegazioni, solo il JSON.\n\n"
        f"Stringhe da tradurre (chiave numerica -> testo italiano):\n"
        f"{json.dumps(batch, ensure_ascii=False)}"
    )


def _run_translate_job(job_id: str, code: str):
    """Task in background: traduce con AI tutte le label vuote della lingua `code`."""
    db = SessionLocal()
    try:
        from ai_client import get_ai_client
        lang = db.query(Language).filter(Language.code == code).first()
        if not lang:
            _translate_jobs[job_id] = {"status": "failed", "total": 0, "done": 0, "error": "Lingua non trovata"}
            return

        base = {t.key: t.value for t in db.query(Translation).filter(Translation.language_code == 'it').all()}
        target = {t.key: t.value for t in db.query(Translation).filter(Translation.language_code == code).all()}
        # chiavi da tradurre: presenti nel base, vuote nel target
        empty_keys = [k for k, v in base.items() if (v) and (not target.get(k))]

        _translate_jobs[job_id] = {"status": "running", "total": len(empty_keys), "done": 0, "error": None}
        if not empty_keys:
            _translate_jobs[job_id]["status"] = "completed"
            return

        client = get_ai_client("claude")
        for i in range(0, len(empty_keys), AI_BATCH_SIZE):
            chunk = empty_keys[i:i + AI_BATCH_SIZE]
            # id numerici -> testo italiano (matching robusto)
            id_to_key = {str(j): k for j, k in enumerate(chunk)}
            batch = {j: base[k] for j, k in id_to_key.items()}
            try:
                prompt = _build_translate_prompt(lang.native_name, code, batch)
                result = client.generate_json(prompt, max_tokens=4000)
                items = {}
                for j, translated in (result or {}).items():
                    key = id_to_key.get(str(j))
                    if key and isinstance(translated, str) and translated.strip():
                        items[key] = translated.strip()
                if items:
                    _upsert_translations(db, code, items)
            except Exception:
                logger.exception("[i18n] batch di traduzione fallito (lingua %s)", code)
                # le chiavi restano vuote -> fallback italiano
            _translate_jobs[job_id]["done"] = min(i + len(chunk), len(empty_keys))

        _translate_jobs[job_id]["status"] = "completed"
        _invalidate_cache(code)
    except Exception as e:
        logger.exception("[i18n] job di traduzione fallito")
        _translate_jobs[job_id] = {"status": "failed", "total": 0, "done": 0, "error": str(e)}
    finally:
        db.close()


def _start_translate_job(code: str, background_tasks: BackgroundTasks) -> str:
    job_id = uuid.uuid4().hex
    _translate_jobs[job_id] = {"status": "running", "total": 0, "done": 0, "error": None}
    background_tasks.add_task(_run_translate_job, job_id, code)
    return job_id


@admin_router.post("/{code}/translate-empty", response_model=TranslateJobResponse)
def admin_translate_empty(
    code: str,
    background_tasks: BackgroundTasks,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    lang = db.query(Language).filter(Language.code == code).first()
    if not lang:
        raise HTTPException(status_code=404, detail="Lingua non trovata")
    if code == 'it':
        raise HTTPException(status_code=400, detail="L'italiano è la lingua base e non si traduce")
    job_id = _start_translate_job(code, background_tasks)
    return TranslateJobResponse(job_id=job_id, message="Traduzione AI avviata")


@admin_router.get("/translate-status/{job_id}", response_model=TranslateStatusResponse)
def admin_translate_status(job_id: str, admin_user: User = Depends(get_current_admin_user)):
    job = _translate_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job non trovato")
    return TranslateStatusResponse(**job)
