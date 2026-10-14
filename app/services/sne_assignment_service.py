# app/services/sne_assignment_service.py

import random
from typing import List, Optional
import re

from sqlalchemy.orm import Session

from app.crud import sne_assignment as crud


def normalize_keyword(value: Optional[str]) -> str:
    return " ".join((value or "").lower().split())


def tokenize(value: Optional[str]) -> List[str]:
    """Lowercase words (letters/digits only). 'Multivitamins + Minerals' -> ['multivitamins', 'minerals']"""
    return re.findall(r"[a-z0-9]+", (value or "").lower())


def contains_phrase(name_tokens: List[str], kw_tokens: List[str]) -> bool:
    """True if kw_tokens appear as consecutive whole words inside name_tokens."""
    n = len(kw_tokens)
    if n == 0:
        return False
    return any(
        name_tokens[i : i + n] == kw_tokens for i in range(len(name_tokens) - n + 1)
    )


def _validate_keyword(raw: str) -> str:
    kw = normalize_keyword(raw)
    if not kw:
        raise ValueError("Keyword cannot be empty.")
    if len(kw) > 100:
        raise ValueError("Keyword is too long (max 100 characters).")
    if not tokenize(kw):
        raise ValueError("Keyword must contain letters or numbers.")
    return kw


def _ensure_sne_member(db: Session, user_id: int):
    if not crud.get_sne_users(db, user_id):
        raise ValueError("User is not an active member of the S&E group.")


def get_members(db: Session, user_id: Optional[int] = None) -> List[dict]:
    users = crud.get_sne_users(db, user_id)
    kw_map = crud.get_keywords_by_users(db, [u.id for u in users])
    return [
        {
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name,
            "surname": u.surname,
            "keywords": kw_map.get(u.id, []),
        }
        for u in users
    ]


def add_keyword(db: Session, user_id: int, keyword: str):
    _ensure_sne_member(db, user_id)
    kw = _validate_keyword(keyword)
    if crud.get_by_user_keyword(db, user_id, kw):
        raise ValueError("This keyword is already assigned to the user.")
    return crud.create(db, user_id, kw)


def set_keywords(db: Session, user_id: int, keywords: List[str]) -> dict:
    _ensure_sne_member(db, user_id)
    clean = sorted({_validate_keyword(k) for k in keywords if normalize_keyword(k)})
    crud.replace_for_user(db, user_id, clean)
    return get_members(db, user_id)[0]


def suggest_assignments(db: Session, items: List[dict]) -> List[dict]:
    """
    For each {id, generic_name}:
      1. split the generic name into whole words
      2. find keywords (single word or phrase) that appear as whole words
      3. keep the most specific one (most words, then longest)
      4. among its users, pick the lowest current workload (random on ties),
         and count the pick so the batch stays even.
    """
    pairs = [(kw, tokenize(kw), uid) for kw, uid in crud.get_active_keyword_pairs(db)]
    pairs = [p for p in pairs if p[1]]  # ignore keywords with no usable words
    workload = crud.get_in_progress_counts(db, list({uid for _, _, uid in pairs}))
    batch_count: dict = {}
    results = []
    for item in items:
        name_tokens = tokenize(item.get("generic_name"))
        matches = (
            [(kw, kt, uid) for kw, kt, uid in pairs if contains_phrase(name_tokens, kt)]
            if name_tokens and name_tokens != ["n", "a"]
            else []
        )
        if not matches:
            results.append({"id": item["id"], "user_id": None, "matched_keyword": None})
            continue

        best_key = max((len(kt), len(kw)) for kw, kt, _ in matches)
        best = [(kw, uid) for kw, kt, uid in matches if (len(kt), len(kw)) == best_key]
        candidates = {uid for _, uid in best}
        group = best[0][0]  # the matched keyword = the group being split evenly
        chosen = min(
            candidates,
            key=lambda uid: (
                batch_count.get((group, uid), 0),  # even split inside this batch first
                workload.get(uid, 0),  # then the lightest current workload
                random.random(),
            ),
        )
        batch_count[(group, chosen)] = batch_count.get((group, chosen), 0) + 1
        workload[chosen] = workload.get(chosen, 0) + 1

        results.append(
            {"id": item["id"], "user_id": chosen, "matched_keyword": best[0][0]}
        )
    return results


def get_workload(db: Session) -> List[dict]:
    users = crud.get_sne_users(db)
    data = crud.get_in_progress_by_step(db, [u.id for u in users])
    return [
        {
            "user_id": u.id,
            "total": sum(data.get(u.id, {}).values()),
            "by_step": data.get(u.id, {}),
        }
        for u in users
    ]
