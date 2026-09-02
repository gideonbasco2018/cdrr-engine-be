# app/models/__init__.py
from app.models.main_db import MainDB
from app.models.application_delegation import ApplicationDelegation
from app.models.application_logs import ApplicationLogs
from app.models.user import User
from app.models.group import Group
from app.models.user_groups import UserGroup
from app.models.menu_permissions import MenuItem, menu_group_permissions
from app.models.cdrr_report import CDRRReport, FROOReport, CDRRSecondary
from app.models.field_audit_log import ApplicationFieldAuditLog
from app.models.notification import Notification
from app.models.bulk_upload_history_records import BulkUploadHistoryRecord
from app.models.bulk_upload_history import BulkUploadHistory
from app.models.closed_tasks import ClosedTask
from app.models.lead_assignment import LeadAssignment
from app.models.application_document import ApplicationDocument
from app.models.bulk_upload_log import BulkUploadLog
from app.models.target_assignment import TargetAssignment
from app.models.directors_target import DirectorsTarget
from app.models.unit import Unit
from app.models.gmp_record import (
    GMPRecord,
    GMPDelegation,
    GMPApplicationLogs,
    GMPFieldAuditLog,
)
from app.models.oauth_otp import OAuthOTP
from app.models.cpr_app_history import CPRAppHistory
from app.models.cpr_app_parties import CPRAppParty
from app.models.cpr_application import CPRApplication
from app.models.cpr_app_document import CPRAppDocument

__all__ = [
    "MainDB",
    "ApplicationDelegation",
    "ApplicationLogs",
    "User",
    "Group",
    "UserGroup",
    "MenuItem",
    "menu_group_permissions",
    "CDRRReport",
    "FROOReport",
    "CDRRSecondary",
    "ApplicationFieldAuditLog",
    "Notification",
    "BulkUploadHistoryRecord",
    "BulkUploadHistory",
    "ClosedTask",
    "LeadAssignment",
    "ApplicationDocument",
    "BulkUploadLog",
    "TargetAssignment",
    "DirectorsTarget",
    "Unit",
    "GMPRecord",
    "GMPDelegation",
    "GMPApplicationLogs",
    "GMPFieldAuditLog",
    "OAuthOTP",
    "CPRAppHistory",
    "CPRAppParty",
    "CPRApplication",
    "CPRAppDocument",
]
