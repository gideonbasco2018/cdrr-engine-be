# app/services/fgmp_claim.py
"""FGMP-only values taken from the Appointment System's form when an
application is claimed.

The general record (`e_application`) keeps the basics plus a raw copy of the
whole form (`form_data`). Everything that belongs to FGMP alone lives in
`e_application_fgmp`; this module cleans the form's answers into those columns.

Nothing here commits. The caller commits or rolls back.
"""

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.e_application import EApplication
from app.models.e_application_fgmp import EApplicationFgmp
from app.models.e_application_ref import EApplicationRef
from app.models.e_process import EProcess

FGMP_PROCESS_CODE = "FGMP"

PH_TZ = timezone(timedelta(hours=8))  # the Philippines has no DST

# The column sizes of e_application_fgmp. A value longer than its column would
# make the whole claim fail, so long answers are cut to fit.
LIMITS = {
    "dtn": 50,
    "related_dtn": 50,
    "category": 100,
    "foreign_manufacturer": 255,
    "foreign_manufacturer_address": 500,
    "foreign_manufacturer_country": 100,
    "product_line": 500,
}


def _text(value, limit: int | None = None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    return value[:limit] if limit else value


def _joined(value, limit: int) -> str | None:
    """A list of answers as one text ("a, b"); a plain text stays as it is."""
    if isinstance(value, (list, tuple)):
        parts = [str(v).strip() for v in value if v is not None and str(v).strip()]
        return _text(", ".join(parts), limit)
    return _text(value, limit)


def _date_received(value) -> date | None:
    """The day the form was received. The form gives a UTC timestamp such as
    "2026-10-14T02:03:54.251Z"; the day is taken in Philippine time."""
    text = _text(value)
    if not text:
        return None
    try:
        if len(text) == 10:  # already a plain date
            return date.fromisoformat(text)
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return stamp.date()
    return stamp.astimezone(PH_TZ).date()


# ───────── the country, read from the end of the address ─────────
#
# The form has no country question, only the address. The country is taken
# from the last words of the address when they are a known country name, and
# left EMPTY otherwise: a missing country is better than a wrong one.
#
# Left out on purpose because they are also places elsewhere and would give a
# wrong answer: "Georgia" (a US state), and words after "New" or "American"
# ("New Mexico", "American Samoa").

COUNTRIES = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola",
    "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
    "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus",
    "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina",
    "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi",
    "Cambodia", "Cameroon", "Canada", "Cape Verde", "Central African Republic",
    "Chad", "Chile", "China", "Colombia", "Comoros", "Congo",
    "Democratic Republic of the Congo", "Costa Rica", "Croatia", "Cuba",
    "Cyprus", "Czech Republic", "Denmark", "Djibouti", "Dominica",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador",
    "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji",
    "Finland", "France", "Gabon", "Gambia", "Germany", "Ghana", "Greece",
    "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti",
    "Honduras", "Hong Kong", "Hungary", "Iceland", "India", "Indonesia", "Iran",
    "Iraq", "Ireland", "Israel", "Italy", "Ivory Coast", "Jamaica", "Japan",
    "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait",
    "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya",
    "Liechtenstein", "Lithuania", "Luxembourg", "Macau", "Madagascar", "Malawi",
    "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania",
    "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia",
    "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru",
    "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria",
    "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau",
    "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru",
    "Philippines", "Poland", "Portugal", "Puerto Rico", "Qatar", "Romania",
    "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Samoa", "San Marino",
    "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles",
    "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands",
    "Somalia", "South Africa", "South Korea", "South Sudan", "Spain",
    "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria",
    "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo",
    "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan",
    "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom",
    "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City",
    "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
]

# Other ways the same country is written -> the name used above
ALIASES = {
    "usa": "United States",
    "u s a": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u k": "United Kingdom",
    "great britain": "United Kingdom",
    "britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "northern ireland": "United Kingdom",
    "uae": "United Arab Emirates",
    "korea": "South Korea",
    "republic of korea": "South Korea",
    "rok": "South Korea",
    "democratic people s republic of korea": "North Korea",
    "prc": "China",
    "pr china": "China",
    "p r china": "China",
    "people s republic of china": "China",
    "russian federation": "Russia",
    "czechia": "Czech Republic",
    "viet nam": "Vietnam",
    "turkiye": "Turkey",
    "cote d ivoire": "Ivory Coast",
    "swaziland": "Eswatini",
    "burma": "Myanmar",
    "holland": "Netherlands",
    "the netherlands": "Netherlands",
    "republic of ireland": "Ireland",
    "macedonia": "North Macedonia",
    "lao pdr": "Laos",
    "lao people s democratic republic": "Laos",
    "hongkong": "Hong Kong",
    "republic of china": "Taiwan",
    "kingdom of saudi arabia": "Saudi Arabia",
    "ksa": "Saudi Arabia",
    "cabo verde": "Cape Verde",
    "east timor": "Timor-Leste",
    "the philippines": "Philippines",
}


def _words(text: str) -> list[str]:
    return [w for w in re.sub(r"[^a-z0-9]+", " ", text.lower()).split() if w]


_BY_WORDS = {" ".join(_words(name)): name for name in COUNTRIES}
_BY_WORDS.update({" ".join(_words(alias)): name for alias, name in ALIASES.items()})
_LONGEST = max(len(k.split()) for k in _BY_WORDS)
# a word before a match that makes it a different place
_NOT_A_COUNTRY_AFTER = {"new", "american"}


def country_from_address(address: str | None) -> str | None:
    """The country named at the end of the address, or None when it is not
    clear. The longest ending wins ("Papua New Guinea" before "Guinea")."""
    words = _words(address or "")
    # a postal code after the country ("Germany 68161") is not part of the name
    while words and any(ch.isdigit() for ch in words[-1]):
        words.pop()
    for size in range(min(_LONGEST, len(words)), 0, -1):
        country = _BY_WORDS.get(" ".join(words[-size:]))
        if not country:
            continue
        before = words[-size - 1] if len(words) > size else ""
        if before in _NOT_A_COUNTRY_AFTER:
            return None
        return country
    return None


# ───────── the FGMP columns ─────────


def _product_line(form: dict) -> str | None:
    """The form asks twice: a pick list ("Product Line") and typed text
    ("Product Line Summary"). The pick list is used when it has entries,
    otherwise the typed text. (To be confirmed with the FGMP unit.)"""
    picked = _joined(form.get("Product Line"), LIMITS["product_line"])
    return picked or _text(form.get("Product Line Summary"), LIMITS["product_line"])


def fgmp_details_from_form(form: dict | None) -> dict:
    """The values for one e_application_fgmp row, from the form's answers.
    Any answer may be missing; that column is then left empty."""
    form = form or {}
    address = _text(
        form.get("Foreign Manufacturer Address"), LIMITS["foreign_manufacturer_address"]
    )
    return {
        # The reference number is the tracking number the screens use. A DTN is
        # only kept if the form ever gives one.
        "dtn": _text(form.get("DTN"), LIMITS["dtn"]),
        "related_dtn": _joined(form.get("Related DTN"), LIMITS["related_dtn"]),
        "date_received": _date_received(form.get("Date Received")),
        "category": _text(form.get("Category"), LIMITS["category"]),
        "foreign_manufacturer": _text(
            form.get("Foreign Manufacturer"), LIMITS["foreign_manufacturer"]
        ),
        "foreign_manufacturer_address": address,
        "foreign_manufacturer_country": country_from_address(address),
        "product_line": _product_line(form),
    }


def create_fgmp_details(db: Session, application: EApplication) -> EApplicationFgmp:
    """Add the e_application_fgmp row for an application, from its saved form."""
    details = EApplicationFgmp(
        application_uuid=application.application_uuid,
        **fgmp_details_from_form(application.form_data),
    )
    db.add(details)
    return details


def applications_missing_fgmp_details(db: Session) -> list[EApplication]:
    """FGMP applications that were claimed before this existed and so have no
    e_application_fgmp row."""
    return (
        db.query(EApplication)
        .join(EApplicationRef, EApplicationRef.ref_uuid == EApplication.application_uuid)
        .join(EProcess, EProcess.process_uuid == EApplicationRef.process_uuid)
        .outerjoin(
            EApplicationFgmp,
            EApplicationFgmp.application_uuid == EApplication.application_uuid,
        )
        .filter(
            EProcess.process_code == FGMP_PROCESS_CODE,
            EApplicationFgmp.fgmp_uuid.is_(None),
        )
        .order_by(EApplication.reference_number)
        .all()
    )


def backfill_missing_fgmp_details(db: Session) -> list[str]:
    """Create the missing rows from each application's saved form. Returns the
    reference numbers it filled. Does NOT commit."""
    filled = []
    for application in applications_missing_fgmp_details(db):
        create_fgmp_details(db, application)
        filled.append(application.reference_number)
    return filled
