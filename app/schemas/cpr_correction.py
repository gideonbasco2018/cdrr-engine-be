from pydantic import BaseModel
from typing import Optional


class DTNVerifyRequest(BaseModel):
    dtn: str


class DTNVerifyResponse(BaseModel):
    found: bool
    eligible: bool                   # True only when DB_APP_STATUS == "COMPLETED"
    message: str

    # Application details — only populated when found=True & eligible=True
    dtn: Optional[str]               = None
    app_status: Optional[str]        = None
    processing_type: Optional[str]   = None
    est_cat: Optional[str]           = None
    app_type: Optional[str]          = None
    lto_comp: Optional[str]          = None
    lto_add: Optional[str]           = None
    eadd: Optional[str]              = None
    tin: Optional[str]               = None
    contact_no: Optional[str]        = None
    lto_no: Optional[str]            = None
    validity: Optional[str]          = None
    date_received_cent: Optional[str]= None
    date_received_fdac: Optional[str]= None
    timeline: Optional[int]          = None
    date_released: Optional[str]     = None

    # Product
    prod_br_name: Optional[str]      = None
    prod_gen_name: Optional[str]     = None
    prod_dos_str: Optional[str]      = None
    prod_dos_form: Optional[str]     = None
    prod_class_prescript: Optional[str] = None
    prod_ess_drug_list: Optional[str]= None
    prod_distri_shelf_life: Optional[str] = None
    prod_pharma_cat: Optional[str]   = None
    prod_cat: Optional[str]          = None
    file: Optional[str]              = None
    storage_cond: Optional[str]      = None
    packaging: Optional[str]         = None
    expiry_date: Optional[str]       = None
    sugg_rp: Optional[str]           = None
    no_sample: Optional[str]         = None

    # Fees
    fee: Optional[str]               = None
    lrf: Optional[str]               = None
    surc: Optional[str]              = None
    total: Optional[str]             = None
    or_no: Optional[str]             = None
    date_issued: Optional[str]       = None

    # Manufacturer
    prod_manu: Optional[str]         = None
    prod_manu_country: Optional[str] = None
    prod_manu_lto_no: Optional[str]  = None
    prod_manu_tin: Optional[str]     = None
    prod_manu_add: Optional[str]     = None

    # Trader
    prod_trader: Optional[str]       = None
    prod_trader_country: Optional[str] = None
    prod_trader_lto_no: Optional[str]= None
    prod_trader_tin: Optional[str]   = None
    prod_trader_add: Optional[str]   = None

    # Importer
    prod_importer: Optional[str]     = None
    prod_importer_country: Optional[str] = None
    prod_importer_lto_no: Optional[str] = None
    prod_importer_tin: Optional[str] = None
    prod_importer_add: Optional[str] = None

    # Distributor
    prod_distri: Optional[str]       = None
    prod_distri_country: Optional[str] = None
    prod_distri_lto_no: Optional[str]= None
    prod_distri_tin: Optional[str]   = None
    prod_distri_add: Optional[str]   = None

    # Repacker
    prod_repacker: Optional[str]     = None
    prod_repacker_country: Optional[str] = None
    prod_repacker_lto_no: Optional[str] = None
    prod_repacker_tin: Optional[str] = None
    prod_repacker_add: Optional[str] = None

    # Misc
    reg_no: Optional[str]            = None
    mother_app_type: Optional[str]   = None
    old_rsn: Optional[str]           = None
    certification: Optional[str]     = None
    class_: Optional[str]            = None     # "class" is a Python keyword
    mo: Optional[str]                = None
    type_doc_released: Optional[str] = None
    atta_released: Optional[str]     = None
    secpa: Optional[str]             = None
    secpa_exp_date: Optional[str]    = None
    secpa_issued_on: Optional[str]   = None
    cpr_cond: Optional[str]          = None
    cpr_cond_remarks: Optional[str]  = None
    cpr_cond_add_remarks: Optional[str] = None
    ammend1: Optional[str]           = None
    ammend2: Optional[str]           = None
    ammend3: Optional[str]           = None
    app_remarks: Optional[str]       = None
    remarks1: Optional[str]          = None

    class Config:
        orm_mode = True