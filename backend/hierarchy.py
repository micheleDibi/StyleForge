"""
Logica dell'albero di distribuzione (admin -> distributore -> rivenditore -> privato).

Il link canonico è `User.parent_id` (1:1). Questo modulo centralizza:
  - navigazione dell'albero (genitore, figli, discendenti, antenati);
  - autorizzazione "actor può gestire target" (admin o antenato);
  - calcolo del referente che riceve una richiesta crediti;
  - regole su quali sottotipi un attore può creare;
  - protezione dai cicli.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db_models import User
from credits import is_admin_user

ENTITY_DISTRIBUTORE = 'distributore'
ENTITY_RIVENDITORE = 'rivenditore'
ENTITY_PRIVATO = 'privato'
VALID_ENTITY_TYPES = {ENTITY_DISTRIBUTORE, ENTITY_RIVENDITORE, ENTITY_PRIVATO}

# Profondità massima di risalita/discesa: backstop anti-loop (l'albero reale è di 3 livelli).
_MAX_DEPTH = 50


def _entity(user: User) -> str:
    return (getattr(user, 'entity_type', None) or ENTITY_PRIVATO).strip().lower()


def get_parent(user: User, db: Session) -> Optional[User]:
    """Genitore diretto (None per i distributori o gli orfani)."""
    if not user.parent_id:
        return None
    return db.query(User).filter(User.id == user.parent_id).first()


def get_children(user: User, db: Session) -> List[User]:
    """Figli diretti, ordinati per username."""
    return (
        db.query(User)
        .filter(User.parent_id == user.id)
        .order_by(User.username.asc())
        .all()
    )


def get_descendants(user: User, db: Session) -> List[User]:
    """Tutto il sottoalbero (BFS, cycle-safe con visited-set)."""
    out: List[User] = []
    visited = {user.id}
    frontier = [user.id]
    depth = 0
    while frontier and depth < _MAX_DEPTH:
        rows = (
            db.query(User)
            .filter(User.parent_id.in_(frontier))
            .order_by(User.username.asc())
            .all()
        )
        next_frontier = []
        for r in rows:
            if r.id in visited:
                continue
            visited.add(r.id)
            out.append(r)
            next_frontier.append(r.id)
        frontier = next_frontier
        depth += 1
    return out


def is_ancestor(actor: User, target: User, db: Session) -> bool:
    """True se `actor` è un antenato (genitore, nonno, ...) di `target`."""
    if actor.id == target.id:
        return False
    current_parent_id: Optional[UUID] = target.parent_id
    seen = set()
    depth = 0
    while current_parent_id and depth < _MAX_DEPTH:
        if current_parent_id == actor.id:
            return True
        if current_parent_id in seen:
            break  # ciclo difensivo
        seen.add(current_parent_id)
        parent = db.query(User).filter(User.id == current_parent_id).first()
        if not parent:
            break
        current_parent_id = parent.parent_id
        depth += 1
    return False


def can_manage(actor: User, target: User, db: Session) -> bool:
    """L'attore può gestire il target se è admin oppure un suo antenato."""
    if is_admin_user(actor):
        return True
    return is_ancestor(actor, target, db)


def compute_approver(user: User, db: Session) -> Tuple[Optional[User], bool]:
    """
    Referente che riceve la richiesta crediti di `user`:
      - distributore        -> (None, True)  => pool admin
      - rivenditore/privato -> (genitore, False) [fallback admin se orfano]
    Ritorna (approver_user_or_None, approver_is_admin).
    """
    et = _entity(user)
    if et == ENTITY_DISTRIBUTORE:
        return None, True
    parent = get_parent(user, db)
    if parent is None:
        # Orfano (nessun genitore): la richiesta va all'admin.
        return None, True
    return parent, False


def allowed_child_entity_types(actor: User) -> set:
    """Sottotipi che `actor` può creare come propri figli."""
    if is_admin_user(actor):
        return set(VALID_ENTITY_TYPES)
    et = _entity(actor)
    if et == ENTITY_DISTRIBUTORE:
        return {ENTITY_RIVENDITORE, ENTITY_PRIVATO}
    if et == ENTITY_RIVENDITORE:
        return {ENTITY_PRIVATO}
    return set()


def assert_no_cycle(child: User, new_parent: User, db: Session) -> None:
    """
    Impedisce cicli: `new_parent` non può essere `child` stesso né un suo discendente.
    Solleva HTTPException 400 in caso di violazione.
    """
    if new_parent.id == child.id:
        raise HTTPException(status_code=400, detail="Un utente non può essere genitore di se stesso.")
    descendant_ids = {d.id for d in get_descendants(child, db)}
    if new_parent.id in descendant_ids:
        raise HTTPException(status_code=400, detail="Associazione non valida: creerebbe un ciclo nell'albero.")
