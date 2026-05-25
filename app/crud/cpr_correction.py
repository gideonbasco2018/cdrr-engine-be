from sqlalchemy.orm import Session
from app.models.main_db import MainDB
from app.schemas.cpr_correction import DTNVerifyResponse,CorrectionSubmitRequest, CorrectionSubmitResponse
from app.models.user import User

ELIGIBLE_STATUS = "COMPLETED"


def _na(value) -> str:
    """Return 'N/A' for None/empty values, otherwise string."""
    if value is None or str(value).strip() == "":
        return "N/A"
    return str(value).strip()


def verify_dtn(dtn: str, db: Session) -> DTNVerifyResponse:
    """
    Look up the DTN in main_db.

    Rules:
    - Not found           → found=False, eligible=False
    - Found but status != COMPLETED → found=True, eligible=False
    - Found and COMPLETED → found=True, eligible=True, full data returned
    """
    try:
        dtn_int = int(dtn.strip())
    except ValueError:
        return DTNVerifyResponse(
            found=False,
            eligible=False,
            message="Invalid DTN format. Please enter a numeric DTN.",
        )

    record: MainDB | None = (
        db.query(MainDB)
        .filter(MainDB.DB_DTN == dtn_int)
        .first()
    )

    # ── Not found ────────────────────────────────────────────────────────────
    if record is None:
        return DTNVerifyResponse(
            found=False,
            eligible=False,
            message=f"DTN {dtn} was not found in the system.",
        )

    status = (record.DB_APP_STATUS or "").strip().upper()

    # ── Found but not eligible ───────────────────────────────────────────────
    if status != ELIGIBLE_STATUS:
        return DTNVerifyResponse(
            found=True,
            eligible=False,
            message=(
                f"Application found but is not eligible for correction. "
                f"Current status: {record.DB_APP_STATUS or 'Unknown'}. "
                f"Only COMPLETED applications can be corrected."
            ),
        )

    # ── Found and eligible — return full details ─────────────────────────────
    return DTNVerifyResponse(
        found=True,
        eligible=True,
        message="Application found and eligible for correction.",

        dtn=str(record.DB_DTN),
        app_status=_na(record.DB_APP_STATUS),
        processing_type=_na(record.DB_PROCESSING_TYPE),
        est_cat=_na(record.DB_EST_CAT),
        app_type=_na(record.DB_APP_TYPE),
        lto_comp=_na(record.DB_EST_LTO_COMP),
        lto_add=_na(record.DB_EST_LTO_ADD),
        eadd=_na(record.DB_EST_EADD),
        tin=_na(record.DB_EST_TIN),
        contact_no=_na(record.DB_EST_CONTACT_NO),
        lto_no=_na(record.DB_EST_LTO_NO),
        validity=_na(record.DB_EST_VALIDITY),
        date_received_cent=_na(record.DB_DATE_RECEIVED_CENT),
        date_received_fdac=_na(record.DB_DATE_RECEIVED_FDAC),
        timeline=record.DB_TIMELINE_CITIZEN_CHARTER,
        date_released=_na(record.DB_DATE_RELEASED),

        # Product
        prod_br_name=_na(record.DB_PROD_BR_NAME),
        prod_gen_name=_na(record.DB_PROD_GEN_NAME),
        prod_dos_str=_na(record.DB_PROD_DOS_STR),
        prod_dos_form=_na(record.DB_PROD_DOS_FORM),
        prod_class_prescript=_na(record.DB_PROD_CLASS_PRESCRIP),
        prod_ess_drug_list=_na(record.DB_PROD_ESS_DRUG_LIST),
        prod_distri_shelf_life=_na(record.DB_PROD_DISTRI_SHELF_LIFE),
        prod_pharma_cat=_na(record.DB_PROD_PHARMA_CAT),
        prod_cat=_na(record.DB_PROD_CAT),
        file=_na(record.DB_FILE),
        storage_cond=_na(record.DB_STORAGE_COND),
        packaging=_na(record.DB_PACKAGING),
        expiry_date=_na(record.DB_EXPIRY_DATE),
        sugg_rp=_na(record.DB_SUGG_RP),
        no_sample=_na(record.DB_NO_SAMPLE),

        # Fees
        fee=_na(record.DB_FEE),
        lrf=_na(record.DB_LRF),
        surc=_na(record.DB_SURC),
        total=_na(record.DB_TOTAL),
        or_no=_na(record.DB_OR_NO),
        date_issued=_na(record.DB_DATE_ISSUED),

        # Manufacturer
        prod_manu=_na(record.DB_PROD_MANU),
        prod_manu_country=_na(record.DB_PROD_MANU_COUNTRY),
        prod_manu_lto_no=_na(record.DB_PROD_MANU_LTO_NO),
        prod_manu_tin=_na(record.DB_PROD_MANU_TIN),
        prod_manu_add=_na(record.DB_PROD_MANU_ADD),

        # Trader
        prod_trader=_na(record.DB_PROD_TRADER),
        prod_trader_country=_na(record.DB_PROD_TRADER_COUNTRY),
        prod_trader_lto_no=_na(record.DB_PROD_TRADER_LTO_NO),
        prod_trader_tin=_na(record.DB_PROD_TRADER_TIN),
        prod_trader_add=_na(record.DB_PROD_TRADER_ADD),

        # Importer
        prod_importer=_na(record.DB_PROD_IMPORTER),
        prod_importer_country=_na(record.DB_PROD_IMPORTER_COUNTRY),
        prod_importer_lto_no=_na(record.DB_PROD_IMPORTER_LTO_NO),
        prod_importer_tin=_na(record.DB_PROD_IMPORTER_TIN),
        prod_importer_add=_na(record.DB_PROD_IMPORTER_ADD),

        # Distributor
        prod_distri=_na(record.DB_PROD_DISTRI),
        prod_distri_country=_na(record.DB_PROD_DISTRI_COUNTRY),
        prod_distri_lto_no=_na(record.DB_PROD_DISTRI_LTO_NO),
        prod_distri_tin=_na(record.DB_PROD_DISTRI_TIN),
        prod_distri_add=_na(record.DB_PROD_DISTRI_ADD),

        # Repacker
        prod_repacker=_na(record.DB_PROD_REPACKER),
        prod_repacker_country=_na(record.DB_PROD_REPACKER_COUNTRY),
        prod_repacker_lto_no=_na(record.DB_PROD_REPACKER_LTO_NO),
        prod_repacker_tin=_na(record.DB_PROD_REPACKER_TIN),
        prod_repacker_add=_na(record.DB_PROD_REPACKER_ADD),

        # Misc
        reg_no=_na(record.DB_REG_NO),
        mother_app_type=_na(record.DB_MOTHER_APP_TYPE),
        old_rsn=_na(record.DB_OLD_RSN),
        certification=_na(record.DB_CERTIFICATION),
        class_=_na(record.DB_CLASS),
        mo=_na(record.DB_MO),
        type_doc_released=_na(record.DB_TYPE_DOC_RELEASED),
        atta_released=_na(record.DB_ATTA_RELEASED),
        secpa=_na(record.DB_SECPA),
        secpa_exp_date=_na(record.DB_SECPA_EXP_DATE),
        secpa_issued_on=_na(record.DB_SECPA_ISSUED_ON),
        cpr_cond=_na(record.DB_CPR_COND),
        cpr_cond_remarks=_na(record.DB_CPR_COND_REMARKS),
        cpr_cond_add_remarks=_na(record.DB_CPR_COND_ADD_REMARKS),
        ammend1=_na(record.DB_AMMEND1),
        ammend2=_na(record.DB_AMMEND2),
        ammend3=_na(record.DB_AMMEND3),
        app_remarks=_na(record.DB_APP_REMARKS),
        remarks1=_na(record.DB_REMARKS_1),
    )


def submit_correction(payload: CorrectionSubmitRequest, db: Session,  current_user: User) -> CorrectionSubmitResponse:
    """
    Validate old_dtn still exists and is COMPLETED,
    then insert a new MainDB row with new_dtn and the corrected fields.
    """
    try:
        old_dtn_int = int(payload.old_dtn.strip())
        new_dtn_int = int(payload.new_dtn.strip())
    except ValueError:
        return CorrectionSubmitResponse(
            success=False,
            message="Invalid DTN format. Both old and new DTN must be numeric.",
        )

    # Re-verify old DTN still exists and is eligible
    original: MainDB | None = (
        db.query(MainDB).filter(MainDB.DB_DTN == old_dtn_int).first()
    )
    if original is None:
        return CorrectionSubmitResponse(
            success=False,
            message=f"Original DTN {payload.old_dtn} no longer exists.",
        )
    if (original.DB_APP_STATUS or "").strip().upper() != "COMPLETED":
        return CorrectionSubmitResponse(
            success=False,
            message="Original application is no longer eligible for correction.",
        )

    # Guard: new DTN must not already exist
    conflict: MainDB | None = (
        db.query(MainDB).filter(MainDB.DB_DTN == new_dtn_int).first()
    )
    if conflict is not None:
        return CorrectionSubmitResponse(
            success=False,
            message=f"New DTN {payload.new_dtn} already exists in the system.",
        )

    # Build the new record — copy original then apply corrections
    new_record = MainDB(
        DB_DTN=new_dtn_int,

        # Carry over unchanged fields from original
        DB_APP_STATUS="ON-PROCESS",
        DB_USER_UPLOADER=current_user.username,
        DB_PROCESSING_TYPE=original.DB_PROCESSING_TYPE,
        DB_EST_CAT=original.DB_EST_CAT,
        DB_APP_TYPE=original.DB_APP_TYPE,
        DB_DATE_RECEIVED_CENT=original.DB_DATE_RECEIVED_CENT,
        DB_DATE_RECEIVED_FDAC=original.DB_DATE_RECEIVED_FDAC,
        DB_TIMELINE_CITIZEN_CHARTER=original.DB_TIMELINE_CITIZEN_CHARTER,
        DB_DATE_RELEASED=original.DB_DATE_RELEASED,
        DB_FEE=original.DB_FEE,
        DB_LRF=original.DB_LRF,
        DB_SURC=original.DB_SURC,
        DB_TOTAL=original.DB_TOTAL,
        DB_OR_NO=original.DB_OR_NO,
        DB_DATE_ISSUED=original.DB_DATE_ISSUED,

        # Correctable fields — use payload value, fall back to original
        DB_EST_LTO_COMP=payload.lto_comp or original.DB_EST_LTO_COMP,
        DB_EST_LTO_ADD=payload.lto_add or original.DB_EST_LTO_ADD,
        DB_EST_EADD=payload.eadd or original.DB_EST_EADD,
        DB_EST_TIN=payload.tin or original.DB_EST_TIN,
        DB_EST_CONTACT_NO=payload.contact_no or original.DB_EST_CONTACT_NO,
        DB_EST_LTO_NO=payload.lto_no or original.DB_EST_LTO_NO,
        DB_EST_VALIDITY=payload.validity or original.DB_EST_VALIDITY,

        DB_PROD_BR_NAME=payload.prod_br_name or original.DB_PROD_BR_NAME,
        DB_PROD_GEN_NAME=payload.prod_gen_name or original.DB_PROD_GEN_NAME,
        DB_PROD_DOS_STR=payload.prod_dos_str or original.DB_PROD_DOS_STR,
        DB_PROD_DOS_FORM=payload.prod_dos_form or original.DB_PROD_DOS_FORM,
        DB_PROD_CLASS_PRESCRIP=payload.prod_class_prescript or original.DB_PROD_CLASS_PRESCRIP,
        DB_PROD_ESS_DRUG_LIST=payload.prod_ess_drug_list or original.DB_PROD_ESS_DRUG_LIST,
        DB_PROD_DISTRI_SHELF_LIFE=payload.prod_distri_shelf_life or original.DB_PROD_DISTRI_SHELF_LIFE,
        DB_PROD_PHARMA_CAT=payload.prod_pharma_cat or original.DB_PROD_PHARMA_CAT,
        DB_PROD_CAT=payload.prod_cat or original.DB_PROD_CAT,
        DB_FILE=payload.file or original.DB_FILE,
        DB_STORAGE_COND=payload.storage_cond or original.DB_STORAGE_COND,
        DB_PACKAGING=payload.packaging or original.DB_PACKAGING,
        DB_EXPIRY_DATE=payload.expiry_date or original.DB_EXPIRY_DATE,
        DB_SUGG_RP=payload.sugg_rp or original.DB_SUGG_RP,
        DB_NO_SAMPLE=payload.no_sample or original.DB_NO_SAMPLE,

        DB_PROD_MANU=payload.prod_manu or original.DB_PROD_MANU,
        DB_PROD_MANU_COUNTRY=payload.prod_manu_country or original.DB_PROD_MANU_COUNTRY,
        DB_PROD_MANU_LTO_NO=payload.prod_manu_lto_no or original.DB_PROD_MANU_LTO_NO,
        DB_PROD_MANU_TIN=payload.prod_manu_tin or original.DB_PROD_MANU_TIN,
        DB_PROD_MANU_ADD=payload.prod_manu_add or original.DB_PROD_MANU_ADD,

        DB_PROD_TRADER=payload.prod_trader or original.DB_PROD_TRADER,
        DB_PROD_TRADER_COUNTRY=payload.prod_trader_country or original.DB_PROD_TRADER_COUNTRY,
        DB_PROD_TRADER_LTO_NO=payload.prod_trader_lto_no or original.DB_PROD_TRADER_LTO_NO,
        DB_PROD_TRADER_TIN=payload.prod_trader_tin or original.DB_PROD_TRADER_TIN,
        DB_PROD_TRADER_ADD=payload.prod_trader_add or original.DB_PROD_TRADER_ADD,

        DB_PROD_IMPORTER=payload.prod_importer or original.DB_PROD_IMPORTER,
        DB_PROD_IMPORTER_COUNTRY=payload.prod_importer_country or original.DB_PROD_IMPORTER_COUNTRY,
        DB_PROD_IMPORTER_LTO_NO=payload.prod_importer_lto_no or original.DB_PROD_IMPORTER_LTO_NO,
        DB_PROD_IMPORTER_TIN=payload.prod_importer_tin or original.DB_PROD_IMPORTER_TIN,
        DB_PROD_IMPORTER_ADD=payload.prod_importer_add or original.DB_PROD_IMPORTER_ADD,

        DB_PROD_DISTRI=payload.prod_distri or original.DB_PROD_DISTRI,
        DB_PROD_DISTRI_COUNTRY=payload.prod_distri_country or original.DB_PROD_DISTRI_COUNTRY,
        DB_PROD_DISTRI_LTO_NO=payload.prod_distri_lto_no or original.DB_PROD_DISTRI_LTO_NO,
        DB_PROD_DISTRI_TIN=payload.prod_distri_tin or original.DB_PROD_DISTRI_TIN,
        DB_PROD_DISTRI_ADD=payload.prod_distri_add or original.DB_PROD_DISTRI_ADD,

        DB_PROD_REPACKER=payload.prod_repacker or original.DB_PROD_REPACKER,
        DB_PROD_REPACKER_COUNTRY=payload.prod_repacker_country or original.DB_PROD_REPACKER_COUNTRY,
        DB_PROD_REPACKER_LTO_NO=payload.prod_repacker_lto_no or original.DB_PROD_REPACKER_LTO_NO,
        DB_PROD_REPACKER_TIN=payload.prod_repacker_tin or original.DB_PROD_REPACKER_TIN,
        DB_PROD_REPACKER_ADD=payload.prod_repacker_add or original.DB_PROD_REPACKER_ADD,

        DB_REG_NO=payload.reg_no or original.DB_REG_NO,
        DB_MOTHER_APP_TYPE=payload.mother_app_type or original.DB_MOTHER_APP_TYPE,
        DB_OLD_RSN=payload.old_dtn or original.DB_OLD_RSN,
        DB_ENTRY_TYPE=payload.DB_ENTRY_TYPE or original.DB_ENTRY_TYPE, 

        DB_CERTIFICATION=payload.certification or original.DB_CERTIFICATION,
        DB_CLASS=payload.class_ or original.DB_CLASS,
        DB_MO=payload.mo or original.DB_MO,
        DB_TYPE_DOC_RELEASED=payload.type_doc_released or original.DB_TYPE_DOC_RELEASED,
        DB_ATTA_RELEASED=payload.atta_released or original.DB_ATTA_RELEASED,
        DB_SECPA=payload.secpa or original.DB_SECPA,
        DB_SECPA_EXP_DATE=payload.secpa_exp_date or original.DB_SECPA_EXP_DATE,
        DB_SECPA_ISSUED_ON=payload.secpa_issued_on or original.DB_SECPA_ISSUED_ON,
        DB_CPR_COND=payload.cpr_cond or original.DB_CPR_COND,
        DB_CPR_COND_REMARKS=payload.cpr_cond_remarks or original.DB_CPR_COND_REMARKS,
        DB_CPR_COND_ADD_REMARKS=payload.cpr_cond_add_remarks or original.DB_CPR_COND_ADD_REMARKS,
        DB_AMMEND1=payload.ammend1 or original.DB_AMMEND1,
        DB_AMMEND2=payload.ammend2 or original.DB_AMMEND2,
        DB_AMMEND3=payload.ammend3 or original.DB_AMMEND3,
        DB_APP_REMARKS=payload.app_remarks or original.DB_APP_REMARKS,
        DB_REMARKS_1=payload.remarks1 or original.DB_REMARKS_1,
    )

    try:
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
    except Exception as e:
        db.rollback()
        return CorrectionSubmitResponse(
            success=False,
            message=f"Database error: {str(e)}",
        )

    return CorrectionSubmitResponse(
        success=True,
        message="Correction submitted successfully. New record created.",
        new_dtn=payload.new_dtn,
        main_db_id=new_record.DB_ID, 
    )