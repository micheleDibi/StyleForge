"""
Sistema di gestione crediti interni per StyleForge.
Gestisce la stima dei costi, la verifica del saldo e la deduzione dei crediti.
"""

import math
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db_models import User, CreditTransaction, Role


# ============================================================================
# TABELLA COSTI IN CREDITI
# ============================================================================

CREDIT_COSTS = {
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
}

# Lista codici permesso disponibili
PERMISSION_CODES = ['train', 'generate', 'humanize', 'thesis']


# ============================================================================
# FUNZIONI DI STIMA CREDITI
# ============================================================================

def estimate_credits(operation_type: str, params: dict) -> dict:
    """
    Stima i crediti necessari per un'operazione.

    Args:
        operation_type: Tipo di operazione ('train', 'generate', 'humanize',
                       'thesis_chapters', 'thesis_sections', 'thesis_content')
        params: Parametri dell'operazione (es. num_pages, num_words, etc.)

    Returns:
        dict con 'credits_needed' (int) e 'breakdown' (dict con dettagli)
    """
    costs = CREDIT_COSTS.get(operation_type)
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
