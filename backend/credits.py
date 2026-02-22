"""
Sistema di gestione crediti interni per StyleForge.
Gestisce la stima dei costi, la verifica del saldo e la deduzione dei crediti.
I costi sono configurabili dall'admin tramite la tabella system_settings.
"""

import math
import copy
import logging
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db_models import User, CreditTransaction, Role, SystemSetting

logger = logging.getLogger(__name__)


# ============================================================================
# TABELLA COSTI IN CREDITI (DEFAULT - fallback se non personalizzati)
# ============================================================================

DEFAULT_CREDIT_COSTS = {
    'train': {
        'base': 5,          # costo base per addestramento
        'per_page': 1,      # per pagina PDF
    },
    'generate': {
        'base': 3,          # costo base per generazione contenuto
        'per_1000_words': 2, # per 1000 parole richieste
    },
    'humanize': {
        'base': 3,          # costo base per umanizzazione
        'per_1000_chars': 1, # per 1000 caratteri input
    },
    'thesis_chapters': {
        'base': 5,          # generare struttura capitoli
    },
    'thesis_sections': {
        'base': 5,          # generare struttura sezioni
    },
    'thesis_content': {
        'base': 10,         # costo base generazione contenuto tesi
        'per_chapter': 5,   # per capitolo
        'per_section': 3,   # per sezione
        'per_1000_words_target': 1,  # per 1000 parole target per sezione
    },
    'compilatio_scan': {
        'base': 5,           # costo base per scansione Compilatio
        'per_1000_chars': 1, # per 1000 caratteri analizzati
    },
}

# Alias per compatibilita' con import esistenti
CREDIT_COSTS = DEFAULT_CREDIT_COSTS

# Lista codici permesso disponibili
PERMISSION_CODES = ['train', 'generate', 'humanize', 'thesis', 'manage_templates', 'compilatio_scan']


# ============================================================================
# GESTIONE COSTI DINAMICI (DB-backed)
# ============================================================================

def get_credit_costs(db: Optional[Session] = None) -> dict:
    """
    Recupera i costi dei crediti. Se personalizzati dall'admin, li legge dal DB.
    Altrimenti ritorna i default hardcoded.

    Args:
        db: Sessione database (opzionale per compatibilita' backward)

    Returns:
        dict con i costi per ogni operazione
    """
    if db is None:
        return copy.deepcopy(DEFAULT_CREDIT_COSTS)

    try:
        setting = db.query(SystemSetting).filter(
            SystemSetting.key == 'credit_costs'
        ).first()

        if setting and setting.value:
            # Merge: parti dai default e sovrascrivi con i valori personalizzati
            # Cosi' se l'admin ha personalizzato solo alcune operazioni,
            # le altre mantengono i default
            merged = copy.deepcopy(DEFAULT_CREDIT_COSTS)
            for op_type, op_costs in setting.value.items():
                if op_type in merged:
                    merged[op_type].update(op_costs)
                else:
                    merged[op_type] = op_costs
            return merged
    except Exception as e:
        logger.warning(f"Errore lettura costi da DB, uso default: {e}")

    return copy.deepcopy(DEFAULT_CREDIT_COSTS)


def is_credit_costs_default(db: Session) -> bool:
    """Controlla se i costi sono quelli default (non personalizzati)."""
    try:
        setting = db.query(SystemSetting).filter(
            SystemSetting.key == 'credit_costs'
        ).first()
        return setting is None
    except Exception:
        return True


def save_credit_costs(costs: dict, admin_user_id, db: Session) -> dict:
    """
    Salva i costi personalizzati nel database.

    Args:
        costs: Dizionario costi (stessa struttura di DEFAULT_CREDIT_COSTS)
        admin_user_id: ID dell'admin che effettua la modifica
        db: Sessione database

    Returns:
        I costi salvati (merged con default)
    """
    # Valida: tutti i valori devono essere numeri >= 0
    for op_type, op_costs in costs.items():
        if not isinstance(op_costs, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Costi per '{op_type}' devono essere un dizionario"
            )
        for key, value in op_costs.items():
            if not isinstance(value, (int, float)) or value < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Il valore '{key}' per '{op_type}' deve essere un numero >= 0"
                )

    # Salva o aggiorna
    setting = db.query(SystemSetting).filter(
        SystemSetting.key == 'credit_costs'
    ).first()

    if setting:
        setting.value = costs
        setting.updated_at = datetime.utcnow()
        setting.updated_by = admin_user_id
    else:
        setting = SystemSetting(
            key='credit_costs',
            value=costs,
            updated_at=datetime.utcnow(),
            updated_by=admin_user_id
        )
        db.add(setting)

    db.commit()
    return get_credit_costs(db)


def reset_credit_costs(admin_user_id, db: Session) -> dict:
    """
    Ripristina i costi default cancellando la personalizzazione.

    Returns:
        I costi default
    """
    setting = db.query(SystemSetting).filter(
        SystemSetting.key == 'credit_costs'
    ).first()

    if setting:
        db.delete(setting)
        db.commit()

    return copy.deepcopy(DEFAULT_CREDIT_COSTS)


# ============================================================================
# FUNZIONI DI STIMA CREDITI
# ============================================================================

def estimate_credits(operation_type: str, params: dict, db: Optional[Session] = None) -> dict:
    """
    Stima i crediti necessari per un'operazione.

    Args:
        operation_type: Tipo di operazione ('train', 'generate', 'humanize',
                       'thesis_chapters', 'thesis_sections', 'thesis_content')
        params: Parametri dell'operazione (es. num_pages, num_words, etc.)
        db: Sessione database (opzionale, se fornito usa costi dinamici)

    Returns:
        dict con 'credits_needed' (int) e 'breakdown' (dict con dettagli)
    """
    all_costs = get_credit_costs(db)
    costs = all_costs.get(operation_type)
    if not costs:
        return {"credits_needed": 0, "breakdown": {"error": f"Tipo operazione sconosciuto: {operation_type}"}}

    breakdown = {}
    total = 0

    if operation_type == 'train':
        base = costs['base']
        pages = params.get('max_pages', 50)
        page_cost = math.ceil(pages * costs['per_page'])
        total = base + page_cost
        breakdown = {
            "base": base,
            "pagine": f"{pages} pagine x {costs['per_page']} = {page_cost}",
            "pagine_crediti": page_cost
        }

    elif operation_type == 'generate':
        base = costs['base']
        words = params.get('numero_parole', 1000)
        word_cost = math.ceil(words / 1000 * costs['per_1000_words'])
        total = base + word_cost
        breakdown = {
            "base": base,
            "parole": f"{words} parole x {costs['per_1000_words']}/1000 = {word_cost}",
            "parole_crediti": word_cost
        }

    elif operation_type == 'humanize':
        base = costs['base']
        chars = params.get('text_length', 0)
        char_cost = math.ceil(chars / 1000 * costs['per_1000_chars'])
        total = base + char_cost
        breakdown = {
            "base": base,
            "caratteri": f"{chars} caratteri x {costs['per_1000_chars']}/1000 = {char_cost}",
            "caratteri_crediti": char_cost
        }

    elif operation_type == 'thesis_chapters':
        total = costs['base']
        breakdown = {
            "base": total,
            "descrizione": "Generazione struttura capitoli"
        }

    elif operation_type == 'thesis_sections':
        total = costs['base']
        breakdown = {
            "base": total,
            "descrizione": "Generazione struttura sezioni"
        }

    elif operation_type == 'thesis_content':
        base = costs['base']
        num_chapters = params.get('num_chapters', 5)
        sections_per_chapter = params.get('sections_per_chapter', 3)
        words_per_section = params.get('words_per_section', 5000)

        total_sections = num_chapters * sections_per_chapter
        chapter_cost = num_chapters * costs['per_chapter']
        section_cost = total_sections * costs['per_section']
        word_cost = math.ceil(total_sections * words_per_section / 1000 * costs['per_1000_words_target'])

        total = base + chapter_cost + section_cost + word_cost
        breakdown = {
            "base": base,
            "capitoli": f"{num_chapters} capitoli x {costs['per_chapter']} = {chapter_cost}",
            "capitoli_crediti": chapter_cost,
            "sezioni": f"{total_sections} sezioni x {costs['per_section']} = {section_cost}",
            "sezioni_crediti": section_cost,
            "parole": f"{total_sections * words_per_section:,} parole totali x {costs['per_1000_words_target']}/1000 = {word_cost}",
            "parole_crediti": word_cost,
            "info": f"{num_chapters} capitoli, {sections_per_chapter} sezioni/capitolo, {words_per_section} parole/sezione"
        }

    elif operation_type == 'compilatio_scan':
        base = costs['base']
        chars = params.get('text_length', 0)
        char_cost = math.ceil(chars / 1000 * costs['per_1000_chars'])
        total = base + char_cost
        breakdown = {
            "base": base,
            "caratteri": f"{chars} caratteri x {costs['per_1000_chars']}/1000 = {char_cost}",
            "caratteri_crediti": char_cost
        }

    return {
        "credits_needed": total,
        "breakdown": breakdown
    }


# ============================================================================
# FUNZIONI DI GESTIONE CREDITI
# ============================================================================

def is_admin_user(user: User) -> bool:
    """Controlla se l'utente e' un amministratore (crediti infiniti)."""
    if user.is_admin:
        return True
    if user.role and user.role.name == 'admin':
        return True
    return False


def check_credits(user: User, amount: int) -> bool:
    """
    Verifica se l'utente ha abbastanza crediti.
    Admin ha sempre crediti sufficienti.
    """
    if is_admin_user(user):
        return True
    return user.credits >= amount


def deduct_credits(
    user: User,
    amount: int,
    operation_type: str,
    description: str,
    db: Session,
    job_id: Optional[str] = None
) -> Optional[CreditTransaction]:
    """
    Deduce crediti dal saldo dell'utente e registra la transazione.
    Se l'utente e' admin, non deduce ma registra comunque.

    Args:
        user: Utente
        amount: Crediti da dedurre (valore positivo, verra' negato)
        operation_type: Tipo operazione
        description: Descrizione della transazione
        db: Sessione database
        job_id: ID del job relativo (opzionale)

    Returns:
        CreditTransaction creata, oppure None se admin

    Raises:
        HTTPException 402 se crediti insufficienti
    """
    if is_admin_user(user):
        # Admin: non deduce crediti, non registra transazione di consumo
        return None

    if user.credits < amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Crediti insufficienti. Necessari: {amount}, disponibili: {user.credits}"
        )

    # Deduce i crediti
    user.credits -= amount
    new_balance = user.credits

    # Registra la transazione
    transaction = CreditTransaction(
        user_id=user.id,
        amount=-amount,  # negativo per consumo
        balance_after=new_balance,
        transaction_type='consumption',
        description=description,
        related_job_id=job_id,
        operation_type=operation_type
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction


def add_credits(
    user: User,
    amount: int,
    description: str,
    db: Session,
    transaction_type: str = 'admin_adjustment',
    admin_user: Optional[User] = None
) -> CreditTransaction:
    """
    Aggiunge crediti al saldo di un utente.

    Args:
        user: Utente destinatario
        amount: Crediti da aggiungere (positivo) o rimuovere (negativo)
        description: Descrizione
        db: Sessione database
        transaction_type: Tipo transazione
        admin_user: Admin che ha eseguito l'operazione (per logging)

    Returns:
        CreditTransaction creata
    """
    user.credits += amount
    # Non permettere saldo negativo
    if user.credits < 0:
        user.credits = 0

    new_balance = user.credits

    desc = description
    if admin_user:
        desc = f"[Admin: {admin_user.username}] {description}"

    transaction = CreditTransaction(
        user_id=user.id,
        amount=amount,
        balance_after=new_balance,
        transaction_type=transaction_type,
        description=desc,
        operation_type=None
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction


def get_user_transactions(
    user_id,
    db: Session,
    limit: int = 50,
    offset: int = 0
) -> list:
    """Ottiene lo storico transazioni di un utente."""
    transactions = db.query(CreditTransaction).filter(
        CreditTransaction.user_id == user_id
    ).order_by(
        CreditTransaction.created_at.desc()
    ).offset(offset).limit(limit).all()

    return [t.to_dict() for t in transactions]
