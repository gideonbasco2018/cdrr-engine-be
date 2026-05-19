from sqlalchemy.orm import Session
from app.models.main_db import MainDB
from app.schemas.cpr_correction import DTNVerifyResponse

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