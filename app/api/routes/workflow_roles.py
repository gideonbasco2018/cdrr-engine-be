# app/routers/workflow_roles.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.group import Group  # ADAPT
from app.models.workflow_role_group import WorkflowRoleGroup
from app.services.workflow_roles import ALL_ROLES, get_role_group_ids


def require_admin(current_user=Depends(get_current_active_user)):
    # ADAPT: same field the frontend checks with getUser()?.role === "Admin"
    if getattr(current_user, "role", None) not in ("Admin", "SuperAdmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


router = APIRouter(
    prefix="/api/admin/workflow-roles",
    tags=["Workflow Roles"],
    dependencies=[Depends(require_admin)],
)


class RoleGroupsUpdate(BaseModel):
    group_ids: list[int]


@router.get("")
def list_workflow_roles(db: Session = Depends(get_db)):
    return {
        "roles": [
            {"role_key": r, "group_ids": sorted(get_role_group_ids(db, r))}
            for r in ALL_ROLES
        ],
        "groups": [
            {"id": g.id, "name": g.name} for g in db.query(Group).order_by(Group.name)
        ],
    }


@router.put("/{role_key}")
def update_workflow_role(
    role_key: str, payload: RoleGroupsUpdate, db: Session = Depends(get_db)
):
    if role_key not in ALL_ROLES:
        raise HTTPException(status_code=404, detail="Unknown role")

    wanted = set(payload.group_ids)
    existing = {g.id for g in db.query(Group).filter(Group.id.in_(wanted))}
    if wanted - existing:
        raise HTTPException(status_code=422, detail="One or more groups do not exist")

    db.query(WorkflowRoleGroup).filter(WorkflowRoleGroup.role_key == role_key).delete()
    db.add_all(WorkflowRoleGroup(role_key=role_key, group_id=gid) for gid in wanted)
    db.commit()
    return {"role_key": role_key, "group_ids": sorted(wanted)}
