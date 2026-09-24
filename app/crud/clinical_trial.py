# FILE: app/crud/clinical_trial.py
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.models.clinical_trial import ClinicalTrial
from app.models.clinical_trial_drug import ClinicalTrialDrug
from app.schemas.clinical_trial import ClinicalTrialCreate, ClinicalTrialUpdate
from app.crud.clinical_trial_audit_log import create_audit_log
from app.core.clinical_trial_columns import (
    CLINICAL_TRIAL_COLUMNS,
    CLINICAL_TRIAL_DRUG_COLUMNS,
)


def _trial_to_dict(trial: ClinicalTrial) -> dict:
    data = {
        column["field"]: getattr(trial, column["field"])
        for column in CLINICAL_TRIAL_COLUMNS
    }
    data["drugs"] = [
        {f["field"]: getattr(d, f["field"]) for f in CLINICAL_TRIAL_DRUG_COLUMNS}
        for d in trial.drugs
    ]
    return data


def get_by_id(db: Session, trial_id: int) -> Optional[ClinicalTrial]:
    return (
        db.query(ClinicalTrial)
        .options(joinedload(ClinicalTrial.drugs))
        .filter(ClinicalTrial.id == trial_id)
        .first()
    )


def get_by_uuid(db: Session, trial_uuid: str) -> Optional[ClinicalTrial]:
    return (
        db.query(ClinicalTrial)
        .options(joinedload(ClinicalTrial.drugs))
        .filter(ClinicalTrial.uuid == trial_uuid)
        .first()
    )


def get_list(
    db: Session,
    search: Optional[str] = None,
    phase: Optional[str] = None,
    drug_type: Optional[str] = None,
    page: int = 1,
    rows_per_page: int = 10,
) -> Tuple[List[ClinicalTrial], int]:
    query = db.query(ClinicalTrial).options(joinedload(ClinicalTrial.drugs))

    if phase:
        query = query.filter(ClinicalTrial.phase == phase)

    if drug_type:
        # drug_type ngayon nasa child table
        query = query.join(ClinicalTrial.drugs).filter(
            ClinicalTrialDrug.drug_type == drug_type
        )

    if search:
        like = f"%{search}%"
        query = query.outerjoin(ClinicalTrial.drugs).filter(
            or_(
                ClinicalTrial.protocol_no.ilike(like),
                ClinicalTrial.study_title.ilike(like),
                ClinicalTrial.sponsor_name.ilike(like),
                ClinicalTrial.cro_name.ilike(like),
                ClinicalTrial.ct_ref_no.ilike(like),
                ClinicalTrial.il_approval_no.ilike(like),
                ClinicalTrialDrug.ip_name.ilike(like),
            )
        )

    query = query.distinct()
    total = query.count()
    rows = (
        query.order_by(ClinicalTrial.id.desc())
        .offset((page - 1) * rows_per_page)
        .limit(rows_per_page)
        .all()
    )
    return rows, total


def get_all_for_export(
    db: Session,
    search: Optional[str] = None,
    phase: Optional[str] = None,
    drug_type: Optional[str] = None,
) -> List[ClinicalTrial]:
    rows, _ = get_list(
        db,
        search=search,
        phase=phase,
        drug_type=drug_type,
        page=1,
        rows_per_page=1_000_000,
    )
    return rows


def create(
    db: Session, data: ClinicalTrialCreate, user_id: Optional[int] = None
) -> ClinicalTrial:
    payload = data.dict(exclude={"drugs"})
    trial = ClinicalTrial(**payload, created_by=user_id, updated_by=user_id)
    trial.drugs = [ClinicalTrialDrug(**d.dict()) for d in data.drugs]

    db.add(trial)
    db.commit()
    db.refresh(trial)

    create_audit_log(
        db,
        clinical_trial_id=trial.id,
        old_values={},
        new_values=_trial_to_dict(trial),
        changed_by=user_id,
        action="CREATE",
    )
    return trial


def update(
    db: Session,
    trial: ClinicalTrial,
    data: ClinicalTrialUpdate,
    user_id: Optional[int] = None,
) -> ClinicalTrial:
    update_fields = data.dict(exclude_unset=True, exclude={"drugs"})

    old_values = {field: getattr(trial, field) for field in update_fields.keys()}
    for field, value in update_fields.items():
        setattr(trial, field, value)

    old_drugs = None
    if data.drugs is not None:
        old_drugs = [
            {f["field"]: getattr(d, f["field"]) for f in CLINICAL_TRIAL_DRUG_COLUMNS}
            for d in trial.drugs
        ]
        trial.drugs.clear()  # cascade="all, delete-orphan" -> deletes removed rows
        trial.drugs.extend(ClinicalTrialDrug(**d.dict()) for d in data.drugs)

    trial.updated_by = user_id
    db.commit()
    db.refresh(trial)

    new_values = {field: getattr(trial, field) for field in update_fields.keys()}
    if old_drugs is not None:
        old_values["drugs"] = old_drugs
        new_values["drugs"] = [
            {f["field"]: getattr(d, f["field"]) for f in CLINICAL_TRIAL_DRUG_COLUMNS}
            for d in trial.drugs
        ]

    if update_fields or old_drugs is not None:
        create_audit_log(
            db,
            clinical_trial_id=trial.id,
            old_values=old_values,
            new_values=new_values,
            changed_by=user_id,
            action="UPDATE",
        )

    return trial
