import httpx
from fastapi import APIRouter

try:
    import enchant
    ENCHANT_AVAILABLE = True
    _enchant_dict = enchant.Dict("en_US")
except Exception:
    ENCHANT_AVAILABLE = False
    _enchant_dict = None

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
    "prodDistriShelfLife": "Shelf Life",
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

# Words to skip even if enchant flags them —
# pharma/medical terms, abbreviations, known proper nouns
ENCHANT_WHITELIST = {
    "alu", "polypropylene", "blister", "sandoz", "sanofi", "pfizer",
    "novartis", "roche", "bayer", "abbott", "unilab", "mims", "doh",
    "fda", "lto", "fdac", "n/a", "na", "mg", "ml", "mcg", "iu",
    "hcl", "hbr", "sr", "er", "dr", "mr", "ms", "inc", "corp",
    "co", "ph", "mnl", "bgry", "brgy", "st", "ave", "blvd",
}


def _strip_punctuation(word: str) -> str:
    """Strip surrounding punctuation for dictionary lookup only."""
    return word.strip(".,;:()[]{}'\"-/\\!?")


def _is_likely_code(word: str) -> bool:
    """Skip alphanumeric codes, version strings, numbers."""
    stripped = _strip_punctuation(word)
    if not stripped:
        return True
    # All digits
    if stripped.isdigit():
        return True
    # Mixed digits+letters short code e.g. "10S", "B12", "A4"
    if len(stripped) <= 4 and any(c.isdigit() for c in stripped):
        return True
    # Contains slash or dash — likely a code or address fragment
    if "/" in stripped or stripped.startswith("-"):
        return True
    return False


def enchant_check_text(text: str) -> list[dict]:
    """
    Walk each word in text. For any word not recognized by enchant,
    return a match-like dict compatible with build_word_list().
    Returns list of { offset, length, replacements, message }
    """
    if not ENCHANT_AVAILABLE or _enchant_dict is None:
        return []

    matches = []
    pos = 0

    for word in text.split(" "):
        word_start = text.index(word, pos)
        word_end = word_start + len(word)
        pos = word_end

        clean = _strip_punctuation(word)
        lower = clean.lower()

        if not clean or len(clean) < 3:
            continue
        if _is_likely_code(clean):
            continue
        if lower in ENCHANT_WHITELIST:
            continue
        # Skip ALL-CAPS words — likely acronyms
        if clean.isupper():
            continue

        try:
            if not _enchant_dict.check(clean):
                suggestions = _enchant_dict.suggest(clean)[:5]
                if suggestions:
                    matches.append({
                        "offset": word_start,
                        "length": len(word),
                        "replacements": [{"value": s} for s in suggestions],
                        "message": f'Possible spelling mistake. Did you mean "{suggestions[0]}"?',
                        "source": "enchant",
                    })
        except Exception:
            continue

    return matches


def build_word_list(text: str, matches: list) -> list[dict]:
    """
    Splits the text into word tokens and tags each one
    with hasError=True if a match covers it.
    Returns a list of { original, corrected, hasError } dicts.
    """
    error_spans = []
    for match in matches:
        replacements = match.get("replacements", [])
        if not replacements:
            continue
        start = match["offset"]
        end = start + match["length"]
        best = replacements[0]["value"]
        error_spans.append((start, end, best))

    tokens = []
    pos = 0
    for part in text.split(" "):
        token_start = text.index(part, pos)
        token_end = token_start + len(part)
        pos = token_end

        matched_fix = None
        for (s, e, fix) in error_spans:
            if token_start < e and token_end > s:
                matched_fix = fix
                break

        tokens.append({
            "original": part,
            "corrected": matched_fix if matched_fix else None,
            "hasError": matched_fix is not None,
        })

    return tokens


def merge_matches(lt_matches: list, enchant_matches: list) -> list:
    """
    Merge LanguageTool and enchant matches.
    If a span is already covered by LT, skip the enchant match to avoid duplicates.
    """
    lt_spans = set()
    for m in lt_matches:
        start = m["offset"]
        end = start + m["length"]
        lt_spans.add((start, end))

    merged = list(lt_matches)
    for em in enchant_matches:
        start = em["offset"]
        end = start + em["length"]
        # Only add if not already covered by LanguageTool
        already_covered = any(
            s <= start < e or s < end <= e
            for (s, e) in lt_spans
        )
        if not already_covered:
            merged.append(em)

    # Sort by offset so build_word_list processes in order
    merged.sort(key=lambda m: m["offset"])
    return merged


@router.post("/spellcheck")
async def spellcheck(payload: dict):
    """
    Accepts: { "fields": { "fieldKey": "value", ... } }
    Returns: [ { fieldKey, label, original, corrected, words, note }, ... ]

    Uses LanguageTool as primary checker + pyenchant as fallback
    to catch gibberish/unknown words that LT misses.
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

            # ── LanguageTool check ──
            lt_matches = []
            try:
                response = await client.post(
                    LANGUAGETOOL_URL,
                    data={
                        "text": text,
                        "language": "en-US",
                        "disabledRules": "UPPERCASE_SENTENCE_START,PUNCTUATION,EN_QUOTES,COMMA_PARENTHESIS_WHITESPACE",
                    },
                )
                response.raise_for_status()
                lt_matches = response.json().get("matches", [])
            except Exception:
                pass  # LT failed — enchant will still run

            # ── pyenchant fallback ──
            enchant_matches = enchant_check_text(text)

            # ── Merge both sources ──
            all_matches = merge_matches(lt_matches, enchant_matches)

            if not all_matches:
                continue

            # ── Build fully-corrected string ──
            corrected = text
            offset_shift = 0
            first_note = ""

            for i, match in enumerate(all_matches):
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

            if corrected == text:
                continue

            # ── Build word-level token list ──
            words = build_word_list(text, all_matches)

            results.append({
                "fieldKey": field_key,
                "label": FIELD_LABELS.get(field_key, field_key),
                "original": text,
                "corrected": corrected,
                "words": words,
                "note": first_note or "Possible spelling error detected",
            })

    return results