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
    # Tesi: addebito PER STEP = quota fissa (base) + scaling sulla dimensione.
    # Le quote base sommano a ~1000 (floor), lo scaling aggiunge per tesi più grandi.
    # Si paga solo gli step eseguiti. Tutti i valori modificabili da admin.
    'thesis_chapters': {
        'base': 150,                     # quota fissa step capitoli
        'per_1000_attachment_chars': 1,  # + scaling sui caratteri degli allegati
    },
    'thesis_sections': {
        'base': 150,                     # quota fissa step sezioni
        'per_chapter': 5,                # + scaling per capitolo
    },
    'thesis_content': {
        'base': 700,                     # quota fissa step contenuto
        'per_chapter': 5,                # + scaling per capitolo
        'per_section': 3,                # + scaling per sezione
        'per_1000_words_target': 1,      # + scaling per 1000 parole target
    },
    'compilatio_scan': {
        'base': 5,           # costo base per scansione Compilatio (manuale/generate/humanize)
        'per_1000_chars': 1, # per 1000 caratteri analizzati
    },
    'compilatio_scan_thesis': {
        'base': 30,          # tariffa flat per scansione Detector AI sulle tesi
    },
    'research_search': {
        'base': 3,           # costo base per ricerca multi-provider
        'per_source': 1,     # aggiuntivo per ogni fonte interrogata oltre la prima
    },
    'research_summary': {
        'base': 3,           # costo base per riassunto AI di un paper
    },
    # Estrazione keyword dai documenti caricati (per popolare la search bar paper)
    'paper_keyword_suggest': {
        'base': 2,           # costo base
        'per_attachment': 1, # per ogni documento testuale considerato (max 5)
    },
    # Analisi documenti/paper (ingest Knowledge Base via SDK Anthropic): step a
    # pagamento (quota fissa + scaling per fonte analizzata). Copre ingest+lint+autofix.
    'wiki_ingest': {
        'base': 100,         # quota fissa analisi documenti/paper
        'per_source': 5,     # + scaling per ogni fonte analizzata (paper + upload)
    },
    # LLM Wiki: lint del wiki (one-shot, costo basso)
    'wiki_lint': {
        'base': 3,
    },
}

# Alias per compatibilita' con import esistenti
CREDIT_COSTS = DEFAULT_CREDIT_COSTS

# Lista codici permesso disponibili
PERMISSION_CODES = ['train', 'generate', 'humanize', 'thesis', 'manage_templates', 'compilatio_scan', 'compilatio_scan_thesis', 'research']


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

    # Rimuove eventuali override legacy del vecchio costo flat 'thesis_total':
    # ora la tesi si paga per step (thesis_chapters/sections/content).
    costs.pop('thesis_total', None)

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
        # Quota fissa + scaling sui caratteri degli allegati.
        base = costs['base']
        attachment_chars = params.get('attachment_chars', 0)
        attachment_cost = math.ceil(attachment_chars / 1000 * costs.get('per_1000_attachment_chars', 0)) if attachment_chars > 0 else 0
        total = base + attachment_cost
        breakdown = {"base": base, "descrizione": "Generazione struttura capitoli"}
        if attachment_cost > 0:
            breakdown["allegati"] = f"{attachment_chars:,} caratteri x {costs.get('per_1000_attachment_chars', 0)}/1000 = {attachment_cost}"
            breakdown["allegati_crediti"] = attachment_cost

    elif operation_type == 'thesis_sections':
        # Quota fissa + scaling per capitolo.
        base = costs['base']
        num_chapters = params.get('num_chapters', 5)
        chapter_cost = num_chapters * costs.get('per_chapter', 0)
        total = base + chapter_cost
        breakdown = {"base": base, "descrizione": "Generazione struttura sezioni"}
        if chapter_cost > 0:
            breakdown["capitoli"] = f"{num_chapters} capitoli x {costs.get('per_chapter', 0)} = {chapter_cost}"
            breakdown["capitoli_crediti"] = chapter_cost

    elif operation_type == 'thesis_content':
        # Quota fissa + scaling per capitolo/sezione/parole.
        base = costs['base']
        num_chapters = params.get('num_chapters', 5)
        sections_per_chapter = params.get('sections_per_chapter', 3)
        words_per_section = params.get('words_per_section', 5000)

        total_sections = num_chapters * sections_per_chapter
        chapter_cost = num_chapters * costs.get('per_chapter', 0)
        section_cost = total_sections * costs.get('per_section', 0)
        word_cost = math.ceil(total_sections * words_per_section / 1000 * costs.get('per_1000_words_target', 0))

        total = base + chapter_cost + section_cost + word_cost
        breakdown = {
            "base": base,
            "capitoli": f"{num_chapters} capitoli x {costs.get('per_chapter', 0)} = {chapter_cost}",
            "capitoli_crediti": chapter_cost,
            "sezioni": f"{total_sections} sezioni x {costs.get('per_section', 0)} = {section_cost}",
            "sezioni_crediti": section_cost,
            "parole": f"{total_sections * words_per_section:,} parole x {costs.get('per_1000_words_target', 0)}/1000 = {word_cost}",
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

    elif operation_type == 'compilatio_scan_thesis':
        # Tariffa flat per la scansione Detector AI sulle tesi.
        # Ignora la lunghezza del documento: costo fisso configurabile dall'admin.
        total = int(costs.get('base', 30) or 0)
        breakdown = {
            "base": total,
            "descrizione": "Detector AI - Scansione tesi (tariffa flat)",
        }

    elif operation_type == 'research_search':
        base = costs['base']
        num_sources = max(1, params.get('num_sources', 3))
        per_source = costs.get('per_source', 1)
        extra = max(0, num_sources - 1) * per_source
        total = base + extra
        breakdown = {
            "base": base,
            "descrizione": "Ricerca accademica multi-provider",
        }
        if extra > 0:
            breakdown["fonti"] = f"{num_sources} fonti x {per_source} (extra) = {extra}"
            breakdown["fonti_crediti"] = extra

    elif operation_type == 'research_summary':
        total = costs['base']
        breakdown = {
            "base": total,
            "descrizione": "Riassunto AI di un paper accademico"
        }

    elif operation_type == 'paper_keyword_suggest':
        base = costs['base']
        num_attachments = max(0, int(params.get('num_attachments', 0) or 0))
        per_attachment = costs.get('per_attachment', 1)
        extra = num_attachments * per_attachment
        total = base + extra
        breakdown = {
            "base": base,
            "descrizione": "Suggerimento keyword da documenti caricati",
        }
        if extra > 0:
            breakdown["documenti"] = f"{num_attachments} documenti x {per_attachment} = {extra}"
            breakdown["documenti_crediti"] = extra

    elif operation_type == 'wiki_ingest':
        base = costs['base']
        num_sources = max(0, int(params.get('num_sources', 0) or 0))
        per_source = costs.get('per_source', 2)
        extra = num_sources * per_source
        total = base + extra
        breakdown = {
            "base": base,
            "descrizione": "Ingest LLM Wiki (sintesi cross-fonte via Claude)",
            "fonti": num_sources,
            "fonti_crediti": extra,
        }

    elif operation_type == 'wiki_lint':
        total = costs['base']
        breakdown = {
            "base": total,
            "descrizione": "Lint LLM Wiki (controllo coerenza, contraddizioni, gaps)"
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


def transfer_credits(
    giver: User,
    receiver: User,
    amount: int,
    db: Session,
    description: str,
):
    """
    Trasferisce `amount` crediti da `giver` a `receiver` in modo atomico.

    Scala i crediti dal donatore (che deve averne a sufficienza) e li accredita al
    ricevente, registrando DUE CreditTransaction ('transfer': out sul donatore, in
    sul ricevente). Le righe vengono bloccate con SELECT FOR UPDATE (ordinate per id
    per evitare deadlock) così assegnazioni/approvazioni concorrenti non causano
    scoperti.

    Per i grant dell'admin (crediti infiniti) usare add_credits, NON questa funzione.

    Raises:
        HTTPException 400 se amount<=0 o giver==receiver
        HTTPException 402 se il donatore non ha crediti sufficienti
    """
    if amount <= 0:
        raise HTTPException(status_code=400, detail="L'importo da trasferire deve essere positivo.")
    if giver.id == receiver.id:
        raise HTTPException(status_code=400, detail="Donatore e ricevente coincidono.")

    # Lock di entrambe le righe in ordine di id (deadlock-safe).
    locked = (
        db.query(User)
        .filter(User.id.in_([giver.id, receiver.id]))
        .order_by(User.id)
        .with_for_update()
        .all()
    )
    by_id = {u.id: u for u in locked}
    g = by_id.get(giver.id)
    r = by_id.get(receiver.id)
    if g is None or r is None:
        raise HTTPException(status_code=404, detail="Utente non trovato per il trasferimento.")

    if g.credits < amount:
        raise HTTPException(
            status_code=402,
            detail=f"Crediti insufficienti per il trasferimento ({g.credits} < {amount}).",
        )

    g.credits -= amount
    r.credits += amount

    tx_out = CreditTransaction(
        user_id=g.id, amount=-amount, balance_after=g.credits,
        transaction_type='transfer', operation_type='transfer_out',
        description=f"{description} (a {r.username})",
    )
    tx_in = CreditTransaction(
        user_id=r.id, amount=amount, balance_after=r.credits,
        transaction_type='transfer', operation_type='transfer_in',
        description=f"{description} (da {g.username})",
    )
    db.add(tx_out)
    db.add(tx_in)
    db.commit()
    return tx_out, tx_in


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
