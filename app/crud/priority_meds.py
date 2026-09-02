# app/crud/priority_meds.py
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.main_db import MainDB

CANCER_CATEGORIES = [
    "antineoplastic",
    "antineoplastic agent",
    "antineoplastic agent (protein kinase inhibitor)",
    "antineoplastic (protein kinase inhibitor)",
    "antineoplastic (cell cycle-specific agent)",
    "antineoplastic (folic acid analogue)",
    "antineoplastic (aromatase inhibitor)",
    "antineoplastic (pyrimidine analogue)",
    "antineoplastic agent (taxane)",
    "antineoplastics",
    "antineoplastic (alkylating agent)",
    "antineoplastic agents (protein kinase inhibitors)",
    "antineoplastic agent (proteasome inhibitor)",
    "antineoplastic agent [protein kinase inhibitor (cyclin-dependent kinase (cdk) inhibitor)]",
    "antineoplastic (taxane)",
    "antineoplastic (tyrosine kinase inhibitor)",
    "antineoplastic agent (bcr-abl tyrosine kinase inhibitor)",
    "antineoplastic (protease inhibitor)",
    "detoxifying agent for antineoplastic agent",
    "detoxifying agent for antineoplastic treatment",
    "antineoplastic/gonadotropin-releasing hormone analogue",
    "antineoplastic agents",
    "antineoplastic [anaplastic lymphoma kinase (alk) inhibitor]",
    "antineoplastic agent (platinum compound)",
    "antineoplastic (platinum compound)",
    "antineoplastic (hormone antagonist)",
    "antineoplastic agent (folic acid analogue)",
    "antineoplastic agents (anthracyclines and related substances)",
    "antineoplastic (antimetabolite)",
    "antineoplastic (epidermal growth factor receptor (egfr) tyrosine kinase inhibitor)",
    "antineoplastic agent (kinase inhibitor)",
    "antineoplastic agent (protein kinase inhibitor/cyclin-dependent kinase (cdk) inhibitor)",
    "antineoplastic agents [cd20 (clusters of differentiation 20) inhibitors]",
    "antineoplastic hormone antagonist",
    "antineoplastic and immodulating agents",
    "antineoplastics agents, protein kinase inhibitors",
    "antineoplastic agent (nitrogen mustard analogue)",
    "antineoplastic agents (monoclonal antibodies)",
    "antineoplastic (anthracycline)",
    "antineoplastic agents, protein kinase inhibitors",
    "antineoplastic agent (her2 receptor antagonist",
    "antineoplastic agent/monoclonal antibodies",
    "antineoplastic (hormone antagonist and related agent)",
    "antineoplastic (cell-cycle specific agent)",
    "antineoplastic and immunomodulating agent",
    "antineoplastic (cell cycle specific agent)",
    "antineoplastic agents [cd20 (clusters for differentiation 20) inhibitors]",
    "antineoplastic (cell-cycle specific agents)",
    "antineoplastic agent (protein kinase inhibitor/ cyclin-dependent kinase (cdk) inhibitor)",
    "antineoplastic (cell cycle-nonspecific agent)",
    "antineoplastic agent [phosphatidylinositol-3-kinase (pi3k) inhibitor]",
    "antineoplastic agent (parp inhibitor)",
    "antineoplastic (topoisomerase i inhibitor)",
    "antineoplastic [epidermal growth factor receptor (egfr) tyrosine kinase inhibitor]",
    "antineoplastic/immunomodulating agent (hormone antagonist/related agent)",
    "antineoplastic(podophyllotoxxin derivative)",
    "antineoplastic - tyrosine kinase inhibitors",
    "antineoplastic (anthracycline and related substance)",
    "antineoplastic agent (hedgehog pathway inhibitor)",
    "antineoplastic (proteasome inhibitor)",
    "antineoplastic agent (taxene)",
    "antineoplastic (nitrogen mustard analogue)",
    "antineoplastic agent (poly (adp-ribose) polymerase (parp) inhibitor)",
    "antineoplastic (monoclonal antibody)",
    "antifolate (antineoplastic agent)",
    "antineoplastic agent [poly adp-ribose polymerase (parp) inhibitor]",
    "antineoplastic agents [programmed cell death protein 1/death ligand 1 (pd-1/pd-l1) inhibitors]",
    "antineoplastic agent (monoclonal antibody)",
    "antineoplastic/antiviral",
    "antineoplastic (vinca alkaloid and analouge)",
    "antineoplastic agent (enzyme)",
    "antineoplastic (pyrimidine nucleoside analogue)",
    "antineoplastic (synthetic pyrimidine -based antifolate)",
    "antineoplastic and immunomodulating agent (topoisomerase i inhibitor)",
    "antineoplastic (podophyllotoxin derivatives)",
    "antineoplastic agens (monoclonal antibodies)",
    "antineoplastic ( anthracycline)",
    "tyrosine-kinase inhibitor (antineoplastic)",
    "antineoplastic (anti-metabolite)",
    "antineoplastic (anti-androgen)",
    "antineoplastic agent (heat shock protein 90 inhibitor)",
    "other antineoplastic agent",
    "antineoplastic (andrigen receptor inhibitor)",
    "antineoplastic antibiotic",
    "antineoplastic agents [topoisomerase 1 (top 1) inhibitors]",
    "antineoplastic (hormine antagonist)",
    "antineoplastic (cell cycle-specific agent) [taxane]",
    "antineoplastic agent (folic acid analogues)",
    "antineoplastic agent (alkyl sulfonate)",
    "antineoplastic agent - protein-tyrosine kinase inhibitor",
    "other antineoplastic agents",
    "antineoplastic (non-selective tyrosine kinase inhibitor (tki)",
    "antineoplastic agent (topoisomerase 1 inhibitor)",
    "antineoplastic agent-protein tyrosine inhibitor",
    "antineoplastic agent (anthyacycline and related substance)",
    "antineoplastic agent (anthracycline)",
    "antineoplastic (topoisomerase 1 (top 1) inhibitor)",
    "antineoplastic agents [her2 (human epidermal growth factor receptor 2) inhibitors]",
    "antineoplastic agent (aromatase inhibitor)",
    "antineoplastic agent ( anthracycline & related substance)",
    "antineoplastic agent ( bcr-abl tyrosine kinase inhibitor)",
    "antineoplastic (aromatsase inhibitor)",
    "antineoplastic agent (nitrogen mustrad analogue)",
    "antineoplastic agent (poly (adp-ribose) polymerase inhibitor)",
    "antineoplastic agent (pyrimidine analogues)",
    "antineoplastic injection,sterile",
    "antineoplastic(podophyllotoxin derivative)",
    "antineoplastic agent ( monocional antibodies)",
    "antineoplastic (alkyalating agent)",
    "antineoplastic agent (frî±-directed antibody drug conjugate)",
]

RARE_DISEASE_CATEGORIES = [
    "immunosuppressant",
    "immunosuppressants",
    "selective immunosuppressant",
    "factor viii inhibitor bypassing activity",
    "selective immunosuppressants",
    "immunosuppressants, interleukin inhibitors",
    "human coagulation factor viii",
    "other immunosuppressant",
    "other alimentary tract and metabolism products, enzymes",
    "risdiplam",
    "human coagulation factor ix",
    "recombinant human coagulation factor viii",
    "dried factor viii fraction",
    "immunosupressants, selective immunosuppressants",
    "immunosuppressant (calcineurin inhibitor)",
    "enzymes",
    "immunosuppressant (tumor necrosis factor alpha inhibitor)",
    "immunosuppressant (janus-associated kinase (jak) inhibitor)",
    "immunosuppressants – janus-associated kinase (jak) inhibitor",
    "phenylalanine hydroxylase activator",
    "selective immunosuppressant (janus kinase (jak) 3 inhibitor)",
    "human coagulation factor viii with wfi",
    "onasemnogene abeparvovec",
    "antihaemorrhagic",
    "antihaemorrhagics",
]

RARE_DISEASE_GENERIC_NAMES = [
    "factor viii inhibitor bypassing activity",
    "human coagulation factor viii",
    "risdiplam",
    "human coagulation factor ix",
    "recombinant human coagulation factor viii",
    "dried factor viii fraction",
    "human coagulation factor viii with wfi",
    "onasemnogene abeparvovec",
]


def get_cancer_meds_breakdown(db: Session):
    type_expr = func.trim(MainDB.DB_PROD_PHARMA_CAT)
    total_pending = func.count().label("total_pending")
    type_total = func.sum(func.count()).over(partition_by=type_expr).label("type_total")

    return (
        db.query(
            type_expr.label("type"),
            MainDB.DB_PROD_GEN_NAME.label("generic_name"),
            total_pending,
            type_total,
        )
        .filter(
            MainDB.DB_APP_STATUS == "IN PROGRESS",
            func.lower(type_expr).in_(CANCER_CATEGORIES),
        )
        .group_by(type_expr, MainDB.DB_PROD_GEN_NAME)
        .order_by(type_total.desc(), type_expr, total_pending.desc())
        .all()
    )


def get_rare_disease_breakdown(db: Session):
    cat_expr = func.lower(func.trim(MainDB.DB_PROD_PHARMA_CAT))
    gen_expr = func.lower(func.trim(MainDB.DB_PROD_GEN_NAME))

    type_expr = case(
        (
            cat_expr.in_(["immunosuppressant", "immunosuppressants"]),
            "Immunosuppressant",
        ),
        (
            cat_expr.in_(["antihaemorrhagic", "antihaemorrhagics"]),
            "Antihaemorrhagic",
        ),
        else_=func.trim(MainDB.DB_PROD_PHARMA_CAT),
    )
    total_pending = func.count().label("total_pending")
    type_total = func.sum(func.count()).over(partition_by=type_expr).label("type_total")

    return (
        db.query(
            type_expr.label("type"),
            MainDB.DB_PROD_GEN_NAME.label("generic_name"),
            total_pending,
            type_total,
        )
        .filter(
            MainDB.DB_APP_STATUS == "IN PROGRESS",
            (
                cat_expr.in_(RARE_DISEASE_CATEGORIES)
                | gen_expr.in_(RARE_DISEASE_GENERIC_NAMES)
            ),
        )
        .group_by(type_expr, MainDB.DB_PROD_GEN_NAME)
        .order_by(type_total.desc(), type_expr, total_pending.desc())
        .all()
    )


def get_flu_vaccine_breakdown(db: Session):
    total_count = func.count().label("total_count")

    return (
        db.query(
            MainDB.DB_PROD_GEN_NAME.label("generic_name"),
            MainDB.DB_PROD_PHARMA_CAT.label("pharma_category"),
            total_count,
        )
        .filter(
            (MainDB.DB_PROD_GEN_NAME.like("%influenza%"))
            | (MainDB.DB_PROD_GEN_NAME.like("%influenzae%")),
            func.lower(func.trim(MainDB.DB_APP_STATUS)) == "in progress",
        )
        .group_by(MainDB.DB_PROD_GEN_NAME, MainDB.DB_PROD_PHARMA_CAT)
        .order_by(total_count.desc(), MainDB.DB_PROD_GEN_NAME)
        .all()
    )


def get_pneumococcal_breakdown(db: Session):
    total_count = func.count().label("total_count")

    return (
        db.query(
            MainDB.DB_PROD_PHARMA_CAT.label("pharma_category"),
            MainDB.DB_PROD_GEN_NAME.label("generic_name"),
            total_count,
        )
        .filter(
            MainDB.DB_PROD_GEN_NAME.like("%Pneumococcal%"),
            func.lower(func.trim(MainDB.DB_APP_STATUS)) == "in progress",
        )
        .group_by(MainDB.DB_PROD_GEN_NAME, MainDB.DB_PROD_PHARMA_CAT)
        .order_by(total_count.desc(), MainDB.DB_PROD_GEN_NAME)
        .all()
    )
