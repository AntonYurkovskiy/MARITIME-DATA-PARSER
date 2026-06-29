"""
Relatives strategy.

Builds payloads for seafarer relatives / kin records.
Uses existing extractors and reuses the addresses strategy for nested address payloads.
"""

from typing import Dict, Any, List, Tuple, Optional
import logging
import re

from src.api.dicts import get_dict
from src.api.geo import get_resident_country, search_geo
from src.api.seafarers import get_id
from src.domain.languages import country_to_language
from src.extractors.dates import extract_date_to_iso
from src.extractors.emails import get_emails_list
from src.extractors.names import get_names
from src.extractors.phones import get_phones
from src.orchestration.strategies.addresses import (
    build_addresses_payload,
    normalize_addresses,
    parse_addresses_raw,
    validate_addresses,
)

logger = logging.getLogger(__name__)

_REFERENCE_CACHE: Dict[str, Any] = {}


def _safe_get_dict(key: str) -> List[Dict[str, Any]]:
    """Load a dictionary without failing the whole block when endpoint is unavailable."""
    try:
        data = get_dict(key)
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("Failed to load dictionary %s: %s", key, exc)
        return []


def _load_reference_dicts() -> Dict[str, Any]:
    """Load and cache reference dictionaries from API."""
    global _REFERENCE_CACHE
    if not _REFERENCE_CACHE:
        relatives_types = _safe_get_dict("relatives_types")
        if not relatives_types:
            relatives_types = _safe_get_dict("relationship_types")
        _REFERENCE_CACHE = {
            "gender": _safe_get_dict("gender"),
            "languages": _safe_get_dict("languages"),
            "relatives_types": relatives_types,
        }
    return _REFERENCE_CACHE


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_candidate_value(source: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _find_personal_id(raw: Dict[str, Any]) -> Optional[str]:
    candidates = [
        "Kin personal id:",
        "Kin ID:",
        "Kin national id:",
        "Personal ID:",
        "ID:",
        "Document No.:",
    ]
    for key in candidates:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_main_info_context(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    main_info = raw_data.get("Main info", {}) if isinstance(raw_data, dict) else {}
    additional_info = raw_data.get("Additional info", {}) if isinstance(raw_data, dict) else {}

    return {
        "main_info": main_info,
        "additional_info": additional_info,
        "citizenship": _extract_candidate_value(main_info, ["Citizenship:"]),
        "residence": _extract_candidate_value(main_info, ["Country of residence / City:"]),
        "phones": _extract_candidate_value(main_info, ["Phones:"]),
        "email": _extract_candidate_value(main_info, ["E-mail:"]),
    }


def _build_relative_record(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    main_context = _extract_main_info_context(raw_data)
    additional_info = main_context["additional_info"]

    relationship = _extract_candidate_value(
        additional_info,
        ["Next of kin:", "Relationship:", "Kin relationship:"]
    )
    kin_name = _extract_candidate_value(
        additional_info,
        ["Kin name, Surname:", "Kin name:", "Kin surname:"]
    )
    kin_phone = _extract_candidate_value(additional_info, ["Kin phone:", "Kin phone number:"])
    kin_address = _extract_candidate_value(additional_info, ["Kin address:", "Kin home address:"])
    kin_email = _extract_candidate_value(additional_info, ["Kin e-mail:", "Kin email:"])
    kin_dob = _extract_candidate_value(additional_info, ["Kin date of birth:", "Kin birthday:"])
    kin_gender = _extract_candidate_value(additional_info, ["Kin gender:", "Kin sex:"])
    kin_language = _extract_candidate_value(additional_info, ["Kin language:", "Kin spoken language:"])
    personal_id = _find_personal_id(additional_info)

    if not any([relationship, kin_name, kin_phone, kin_address, kin_email, kin_dob, kin_gender, personal_id]):
        return {}

    return {
        "relationship": relationship,
        "name_raw": kin_name,
        "phone_raw": kin_phone,
        "address_raw": kin_address,
        "email_raw": kin_email,
        "dob_raw": kin_dob,
        "gender_raw": kin_gender,
        "language_raw": kin_language,
        "personal_id": personal_id,
        **main_context,
    }


def parse_relatives_raw(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract relative-related fields from parsed HTML data."""
    relative = _build_relative_record(raw_data)
    return [relative] if relative else []


def _normalize_phone_numbers(
    phone_raw: Optional[str],
    resident_country_id: Optional[int],
    nationality_country_id: Optional[int],
) -> List[Dict[str, Any]]:
    if not phone_raw:
        return []
    return get_phones(phone_raw, resident_country_id, nationality_country_id, search_geo) or []


def _normalize_addresses_for_relative(raw_address: Optional[str], main_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not raw_address:
        return []

    synthetic_raw = {
        "Main info": {
            "Home address:": raw_address,
            "Country of residence / City:": main_context.get("residence"),
            "Closest airport:": None,
            "Citizenship:": main_context.get("citizenship"),
        },
        "Additional info": {},
    }
    parsed_addresses = parse_addresses_raw(synthetic_raw)
    if not parsed_addresses:
        return []
    normalized_addresses = normalize_addresses(parsed_addresses)
    is_valid, _ = validate_addresses(normalized_addresses)
    return build_addresses_payload(normalized_addresses) if is_valid else []


def normalize_relatives(parsed: List[Dict[str, Any]], context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Normalize relative data for payload building."""
    refs = _load_reference_dicts()
    
    # Get intra-file cache from context
    file_cache = context.get("_file_cache", {}) if context else {}
    normalized: List[Dict[str, Any]] = []

    for raw in parsed or []:
        if not isinstance(raw, dict) or not raw:
            continue

        name = None
        surname = None
        middle_name = None
        if raw.get("name_raw"):
            name, middle_name, surname = get_names(raw["name_raw"])

        relationship_type_id = None
        if raw.get("relationship"):
            relationship_type_id = get_id(refs.get("relatives_types", []), raw.get("relationship"), "relatives_types")

        gender_id = None
        if raw.get("gender_raw"):
            gender_id = get_id(refs.get("gender", []), raw.get("gender_raw"), "gender")

        language_id = None
        if raw.get("language_raw"):
            language_id = get_id(refs.get("languages", []), raw.get("language_raw"), "languages")
        elif raw.get("citizenship"):
            language_id = get_id(
                refs.get("languages", []),
                country_to_language(raw.get("citizenship")),
                "languages",
            )

        date_of_birth = None
        if raw.get("dob_raw"):
            extracted = extract_date_to_iso(raw.get("dob_raw"))
            if isinstance(extracted, tuple):
                date_of_birth = extracted[0]

        resident_country_id = None
        nationality_country_id = None
        if raw.get("residence"):
            cache_key = f"resident_relative:{raw.get('residence')}:{raw.get('citizenship')}"
            if cache_key not in file_cache:
                resident_country = get_resident_country(raw.get("residence"), raw.get("citizenship"))
                geo_resident = search_geo(resident_country, "countries") if resident_country else []
                file_cache[cache_key] = geo_resident[0]["id"] if geo_resident else None
            resident_country_id = file_cache[cache_key]
        if raw.get("citizenship"):
            cache_key = f"nationality_relative:{raw.get('citizenship')}"
            if cache_key not in file_cache:
                geo_nationality = search_geo(raw.get("citizenship"), "countries") or []
                file_cache[cache_key] = geo_nationality[0]["id"] if geo_nationality else None
            nationality_country_id = file_cache[cache_key]

        phone_numbers = _normalize_phone_numbers(raw.get("phone_raw"), resident_country_id, nationality_country_id)
        emails = get_emails_list(raw.get("email_raw")) if raw.get("email_raw") else []
        addresses = _normalize_addresses_for_relative(raw.get("address_raw"), raw)

        normalized.append(
            {
                "name": name,
                "middle_name": middle_name,
                "surname": surname,
                "personal_id": raw.get("personal_id"),
                "date_of_birth": date_of_birth,
                "gender_id": gender_id,
                "relationship_type_id": relationship_type_id,
                "language_id": language_id,
                "phone_numbers": phone_numbers,
                "emails": emails,
                "addresses": addresses,
            }
        )

    return normalized


def validate_relatives(relatives: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate normalized relative payload data."""
    if not relatives:
        return True, []

    errors: List[str] = []
    valid_count = 0

    for index, relative in enumerate(relatives):
        entry_errors: List[str] = []
        has_core_data = any(
            [
                relative.get("name"),
                relative.get("surname"),
                relative.get("relationship_type_id"),
                relative.get("personal_id"),
                relative.get("date_of_birth"),
                relative.get("gender_id"),
                relative.get("phone_numbers"),
                relative.get("emails"),
                relative.get("addresses"),
            ]
        )
        if not has_core_data:
            entry_errors.append(f"entry[{index}]: no relative data found")
        if not relative.get("name") and not relative.get("surname"):
            entry_errors.append(f"entry[{index}]: name or surname is required")
        if not relative.get("relationship_type_id"):
            entry_errors.append(f"entry[{index}]: relationship_type_id is required")

        if entry_errors:
            errors.extend(entry_errors)
        else:
            valid_count += 1

    if valid_count == 0:
        return False, errors or ["no valid relatives found"]

    return True, []


def build_relatives_payload(relatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build API payloads for relatives block."""
    payloads: List[Dict[str, Any]] = []

    for relative in relatives or []:
        if not relative.get("relationship_type_id") and not relative.get("name") and not relative.get("surname"):
            logger.warning("Skipping relative entry without usable data: %s", relative)
            continue

        payloads.append(
            {
                "name": relative.get("name"),
                "surname": relative.get("surname"),
                "personal_id": relative.get("personal_id"),
                "date_of_birth": relative.get("date_of_birth"),
                "gender_id": relative.get("gender_id"),
                "relationship_type_id": relative.get("relationship_type_id"),
                "language_id": relative.get("language_id"),
                "phone_numbers": relative.get("phone_numbers", []),
                "emails": relative.get("emails", []),
                "addresses": relative.get("addresses", []),
            }
        )

    return payloads
