"""
Documents strategy.

Uses parsed Certificates section and builds payloads for certificate-like documents.
"""

from typing import Dict, Any, List, Tuple, Optional
import logging
import re

from src.api.dicts import get_dict
from src.api.geo import search_geo
from src.api.seafarers import get_id
from src.extractors.dates import extract_date_to_iso

logger = logging.getLogger(__name__)

_REFERENCE_CACHE: Dict[str, Any] = {}

# Aliases based on observed unresolved source titles from real CVs.
# Key is normalized by _normalize_for_match, value is canonical certificate type title.
_CERTIFICATE_TYPE_ALIASES: Dict[str, str] = {
    "security awareness training": "Security-awareness A-VI/6-1",
    "general operator certificate": "GMDSS restricted operator",
    "communication": "CAA Offshore Radio Operator",
    "lgtank tank specialized training": "COP Gas - Advanced",
    "sailing in ice": "Basic Training for ships operating in polar waters",
    "designated security duties": "Security training with DSD A-VI/6-2",
    "ship carrying dangr hazard cargo": "Liquid Cargo and Ballast Handling",
    "mcrm": "Crisis Management And Human Behaviour Training",
    "security related training and instruction for all seafarers": "Security-awareness A-VI/6-1",
    "advanced training for liquefied gas tanker cargo operations": "COP Gas - Advanced",
    "cop on advanced training for cargo operations on tankers": "COP Oil&Chemical - Advanced",
    "advanced course in gas instruments": "COP Gas - Advanced",
}

_SECTION_TITLE_TYPE_ALIASES: Dict[tuple, str] = {
    ("passports smbk", "international passport"): "Passport",
    ("passports smbk", "national passport"): "Passport",
    ("passports smbk", "seaman s book"): "Seamans Book",
    ("medical certificates", "international medical certificate for seamen"): "Medical Test",
    ("medical certificates", "seafarer s medical certificate"): "Medical Test",
    ("medical certificates", "seafarer medical certificate"): "Medical Test",
    ("medical certificates", "medicial certificate of fitness"): "Medical Test",
    ("medical certificates", "medical certificate viva vita"): "Medical Test",
    ("medical certificates", "covid vaccination 2 doses"): "COVID-19 Vaccination",
}

_DIPLOMA_RANK_TYPE_ALIASES: Dict[str, str] = {
    "officer in charge of navigational watch oow": "OOW of navig. watch on ships of 500GT or more",
    "chief mate": "Chief mate on ships of 3000GT or more",
    "master": "Master on ship of 3000 GT or more",
    "gmdss operator": "GMDSS",
    "electro technical officer": "Eng. Officer on ships with power of 750 Kw or more",
    "rating forming part of a engineering watch": "Motorman - Engineer watch rating, Grade 1",
}


def _safe_get_dict(key: str) -> List[Dict[str, Any]]:
    """Get dictionary by key without failing the whole block when endpoint is unavailable."""
    try:
        data = get_dict(key)
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("Failed to load dictionary %s: %s", key, exc)
        return []


def _load_reference_dicts() -> Dict[str, Any]:
    """Load and cache certificate dictionaries."""
    global _REFERENCE_CACHE
    if not _REFERENCE_CACHE:
        _REFERENCE_CACHE = {
            "certificate_groups": _safe_get_dict("certificate_groups"),
            "certificate_types": _safe_get_dict("certificate_types"),
        }
    return _REFERENCE_CACHE


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _extract_iso_date(value: Any) -> Optional[str]:
    cleaned = _clean_text(value)
    if not cleaned:
        return None

    extracted = extract_date_to_iso(cleaned)
    if extracted is None:
        return None
    if isinstance(extracted, tuple):
        return extracted[0]
    return None


def _resolve_country_id(country_name: Any) -> Optional[int]:
    term = _clean_text(country_name)
    if not term:
        return None
    matches = search_geo(term, "countries") or []
    if not matches:
        return None
    first = matches[0]
    if isinstance(first, dict):
        return first.get("id")
    return None


def _find_dict_value_exact(dictionary: List[Dict[str, Any]], value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    needle = value.strip().lower()
    for item in dictionary or []:
        item_value = item.get("value")
        if isinstance(item_value, str) and item_value.strip().lower() == needle:
            return item_value
    return None


def _normalize_for_match(value: Optional[str]) -> str:
    if not value:
        return ""
    text = value.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _token_set(value: Optional[str]) -> set:
    normalized = _normalize_for_match(value)
    if not normalized:
        return set()
    return {token for token in normalized.split(" ") if token}


def _find_dict_value_best(dictionary: List[Dict[str, Any]], value: Optional[str]) -> Optional[str]:
    """Resolve dict value by exact/normalized/partial/token-overlap match."""
    exact = _find_dict_value_exact(dictionary, value)
    if exact:
        return exact

    needle_norm = _normalize_for_match(value)
    if not needle_norm:
        return None

    # Normalized exact match (ignores punctuation/extra spaces).
    for item in dictionary or []:
        item_value = item.get("value")
        if isinstance(item_value, str) and _normalize_for_match(item_value) == needle_norm:
            return item_value

    # Substring/containment match for shortened OCR forms.
    for item in dictionary or []:
        item_value = item.get("value")
        if not isinstance(item_value, str):
            continue
        item_norm = _normalize_for_match(item_value)
        if needle_norm in item_norm or item_norm in needle_norm:
            return item_value

    # Best token overlap fallback.
    needle_tokens = _token_set(value)
    if not needle_tokens:
        return None

    best_value: Optional[str] = None
    best_score = 0.0
    for item in dictionary or []:
        item_value = item.get("value")
        if not isinstance(item_value, str):
            continue
        item_tokens = _token_set(item_value)
        if not item_tokens:
            continue

        overlap = len(needle_tokens.intersection(item_tokens))
        score = overlap / max(1, len(needle_tokens))
        if score > best_score:
            best_score = score
            best_value = item_value

    if best_score >= 0.5:
        return best_value
    return None


def _safe_get_id(dictionary: List[Dict[str, Any]], value: Optional[str], dict_name: str) -> Optional[int]:
    """Resolve ID using get_id only for values already present in dictionary."""
    matched_value = _find_dict_value_best(dictionary, value)
    if not matched_value:
        # For certificate_types, try explicit alias mapping from observed source titles.
        if dict_name == "certificate_types":
            normalized = _normalize_for_match(value)
            alias_target = _CERTIFICATE_TYPE_ALIASES.get(normalized)
            if alias_target:
                matched_value = _find_dict_value_best(dictionary, alias_target)

    if not matched_value:
        return None
    return get_id(dictionary, matched_value, dict_name)


def _resolve_first_group_id(refs: Dict[str, Any], candidates: List[str]) -> Optional[int]:
    for candidate in candidates:
        group_id = _safe_get_id(refs.get("certificate_groups", []), candidate, "certificate_groups")
        if group_id:
            return group_id
    return None


def _resolve_type_id(row: Dict[str, Any], refs: Dict[str, Any]) -> Optional[int]:
    title = _clean_text(row.get("Title of document"))
    source_section = _clean_text(row.get("_source_section"))
    type_dict = refs.get("certificate_types", [])

    if title:
        direct = _safe_get_id(type_dict, title, "certificate_types")
        if direct:
            return direct

    section_norm = _normalize_for_match(source_section)
    title_norm = _normalize_for_match(title)

    alias_target = _SECTION_TITLE_TYPE_ALIASES.get((section_norm, title_norm))
    if alias_target:
        alias_id = _safe_get_id(type_dict, alias_target, "certificate_types")
        if alias_id:
            return alias_id

    if section_norm == "diplomas" and title_norm == "professional license":
        rank = _clean_text(row.get("Rank"))
        rank_norm = _normalize_for_match(rank)

        rank_alias = _DIPLOMA_RANK_TYPE_ALIASES.get(rank_norm)
        if rank_alias:
            rank_alias_id = _safe_get_id(type_dict, rank_alias, "certificate_types")
            if rank_alias_id:
                return rank_alias_id

        if rank:
            by_rank = _safe_get_id(type_dict, rank, "certificate_types")
            if by_rank:
                return by_rank

    return None


def _resolve_certificate_group_id(
    title: Optional[str], refs: Dict[str, Any], source_section: Optional[str] = None
) -> Optional[int]:
    if not title:
        title_lower = ""
    else:
        title_lower = title.lower()

    section_norm = _normalize_for_match(source_section)

    if section_norm == "passports smbk":
        return _resolve_first_group_id(refs, ["Travel Documents", "Certificate", "no group"])

    if section_norm == "medical certificates":
        return _resolve_first_group_id(refs, ["Medical", "Certificate", "no group"])

    if section_norm == "diplomas":
        if "endorsement" in title_lower:
            return _resolve_first_group_id(refs, ["Endorsements", "Certificate of Competency", "Certificate"])
        return _resolve_first_group_id(refs, ["Certificate of Competency", "Certificate", "no group"])

    if "endorsement" in title_lower:
        return _resolve_first_group_id(refs, ["Endorsements", "Certificate"])

    return _resolve_first_group_id(refs, ["Certificate", "no group"])


def parse_documents_raw(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract document-like rows from parsed HTML data.

    Includes sections:
    - Certificates
    - Passports / Smbk
    - Diplomas
    - Medical certificates
    """
    if not isinstance(raw_data, dict):
        return []

    section_names = [
        "Certificates",
        "Passports / Smbk",
        "Diplomas",
        "Medical certificates",
    ]

    result: List[Dict[str, Any]] = []
    for section_name in section_names:
        section_items = raw_data.get(section_name)
        if not isinstance(section_items, list):
            continue
        for row in section_items:
            if not isinstance(row, dict):
                continue
            enriched = dict(row)
            enriched["_source_section"] = section_name
            result.append(enriched)

    return result


def normalize_documents(raw_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize certificate rows into API-ready document entries."""
    refs = _load_reference_dicts()
    normalized: List[Dict[str, Any]] = []

    for row in raw_documents or []:
        title = _clean_text(row.get("Title of document"))
        source_section = _clean_text(row.get("_source_section"))
        number = _clean_text(row.get("No."))
        issuer = _clean_text(row.get("Issuer") or row.get("Issued by") or row.get("Issued by:") )
        notes = _clean_text(row.get("Notes") or row.get("Comment") or row.get("Details"))

        issued_date = _extract_iso_date(row.get("Date of issue"))
        expires_date = _extract_iso_date(row.get("Valid up"))
        issued_country_id = _resolve_country_id(row.get("Country of issue"))

        type_id = _resolve_type_id(row, refs)
        group_id = _resolve_certificate_group_id(title, refs, source_section)

        normalized.append(
            {
                "group_id": group_id,
                "type_id": type_id,
                "number": number,
                "issued_date": issued_date,
                "expires_date": expires_date,
                "issued_country_id": issued_country_id,
                "issuer": issuer,
                "notes": notes,
                "files": [],
            }
        )

    return normalized


def validate_documents(documents: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate normalized certificate entries."""
    if not documents:
        return True, []

    errors: List[str] = []
    valid_count = 0

    for index, doc in enumerate(documents):
        entry_errors: List[str] = []
        if not doc.get("type_id"):
            entry_errors.append(f"entry[{index}]: type_id is required")
        if not doc.get("group_id"):
            entry_errors.append(f"entry[{index}]: group_id is required")

        if entry_errors:
            errors.extend(entry_errors)
        else:
            valid_count += 1

    if valid_count == 0:
        return False, errors or ["no valid documents found"]

    return True, []


def build_documents_payload(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build API payload list for /seafarers/<seafarer_uuid>/certificates-like documents."""
    payloads: List[Dict[str, Any]] = []

    for doc in documents or []:
        if not doc.get("type_id") or not doc.get("group_id"):
            logger.warning("Skipping document without required IDs: %s", doc)
            continue

        payloads.append(
            {
                "group_id": doc.get("group_id"),
                "type_id": doc.get("type_id"),
                "number": doc.get("number"),
                "issued_date": doc.get("issued_date"),
                "expires_date": doc.get("expires_date"),
                "issued_country_id": doc.get("issued_country_id"),
                "issuer": doc.get("issuer"),
                "notes": doc.get("notes"),
                "files": doc.get("files", []),
            }
        )

    return payloads
