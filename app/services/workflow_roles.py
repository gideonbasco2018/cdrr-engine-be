# app/services/workflow_roles.py
from sqlalchemy.orm import Session

from app.models.workflow_role_group import WorkflowRoleGroup

ROLE_CASHIER = "cashier"
ROLE_DECKER = "decker"
ROLE_EVALUATOR = "evaluator"
# Who an FGMP decker may assign. FGMP has its own evaluators, so they are not
# in the evaluator role above (which Decking uses for everything else).
ROLE_FGMP_EVALUATOR = "fgmp_evaluator"
ALL_ROLES = (ROLE_CASHIER, ROLE_DECKER, ROLE_EVALUATOR, ROLE_FGMP_EVALUATOR)


def get_role_group_ids(db: Session, role_key: str) -> set[int]:
    rows = (
        db.query(WorkflowRoleGroup.group_id)
        .filter(WorkflowRoleGroup.role_key == role_key)
        .all()
    )
    return {r[0] for r in rows}


def user_has_role(db: Session, user, role_key: str) -> bool:
    # ADAPT: same relationship you used in get_user_group_ids
    user_groups = {g.id for g in (getattr(user, "groups", None) or [])}
    return bool(user_groups & get_role_group_ids(db, role_key))
