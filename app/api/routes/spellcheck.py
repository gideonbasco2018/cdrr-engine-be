import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/api")

LANGUAGETOOL_URL = "https://api.languagetool.org/v2/check"

FIELD_LABELS = {
    "prodBrName": "Brand Name",
    "prodGenName": "Generic Name",
    "prodDosStr": "Dosage Strength",
    "prodDosForm": "Dosage Form",
    "prodClassPrescript": "Classification",
    "prodEssDrugList": "Essential Drug",
    "prodPharmaCat": "Pharma Category",
    "prodCat": "Product Category",
    "storageCond": "Storage Condition",
    "packaging": "Packaging",
    "ltoCompany": "LTO Company",
    "ltoAdd": "LTO Address",
    "eadd": "Email Address",
    "prodManu": "Manufacturer",
    "prodManuAdd": "Manufacturer Address",
    "prodTrader": "Trader",
    "prodTraderAdd": "Trader Address",
    "prodImporter": "Importer",
    "prodImporterAdd": "Importer Address",
    "prodDistri": "Distributor",
    "prodDistriAdd": "Distributor Address",
    "prodRepacker": "Repacker",
    "prodRepackerAdd": "Repacker Address",
}


@router.post("/spellcheck")
async def spellcheck(payload: dict):
    """
    Accepts: { "fields": { "fieldKey": "value", ... } }
    Returns: [ { fieldKey, label, original, corrected, note }, ... ]
    """
    fields: dict = payload.get("fields", {})
    if not fields:
        return []

    results = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for field_key, original_text in fields.items():
            text = str(original_text).strip()
            if not text or text.lower() in ("n/a", "na", ""):
                continue

            try:
                response = await client.post(
                    LANGUAGETOOL_URL,
                    data={
                        "text": text,
                        "language": "en-US",
                        # Disable rules that flag pharma/address formats
                        "disabledRules": "UPPERCASE_SENTENCE_START,PUNCTUATION,EN_QUOTES,COMMA_PARENTHESIS_WHITESPACE",
                    },
                )
                response.raise_for_status()
                data = response.json()
            except Exception:
                continue

            matches = data.get("matches", [])
            if not matches:
                continue

            # Apply all replacements to build the corrected string
            corrected = text
            offset_shift = 0

            first_note = ""
            for i, match in enumerate(matches):
                replacements = match.get("replacements", [])
                if not replacements:
                    continue
                if i == 0:
                    first_note = match.get("message", "")

                best = replacements[0]["value"]
                start = match["offset"] + offset_shift
                end = start + match["length"]
                corrected = corrected[:start] + best + corrected[end:]
                offset_shift += len(best) - match["length"]

            if corrected != text:
                results.append({
                    "fieldKey": field_key,
                    "label": FIELD_LABELS.get(field_key, field_key),
                    "original": text,
                    "corrected": corrected,
                    "note": first_note or "Possible spelling error detected",
                })

    return results