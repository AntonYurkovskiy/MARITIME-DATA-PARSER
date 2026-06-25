"""
Main info strategy skeleton.

Extracts, normalizes, validates and builds payload for main seafarer info block.
Uses existing extractors from src/ without modifying them.
"""

from typing import Dict, Any, List, Tuple
import logging

from src.api.dicts import get_dict, _add_value_in_dict
from src.api.geo import get_resident_country, search_geo
from src.api.seafarers import get_id
from src.domain.languages import country_to_language
from src.extractors.dates import extract_date_to_iso
from src.extractors.documents import get_personal_id_by_passport, get_ranks
from src.extractors.emails import get_emails_list
from src.extractors.names import get_names
from src.extractors.phones import get_phones
from src.parsers.photo import get_photo

logger = logging.getLogger(__name__)

# Cache for reference dicts (loaded once)
_REFERENCE_CACHE: Dict[str, Any] = {}


def _load_reference_dicts() -> Dict[str, Any]:
    """Load and cache reference dictionaries from API."""
    global _REFERENCE_CACHE
    if not _REFERENCE_CACHE:
        _REFERENCE_CACHE = {
            "ranks": get_dict("ranks"),
            "gender": get_dict("gender"),
            "marital_statuses": get_dict("marital_statuses"),
            "languages": get_dict("languages"),
        }
    return _REFERENCE_CACHE


def parse_main_info_raw(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract main info and related data from parsed HTML.
    
    Returns dict with 'main_info', 'biometrics' keys for use in normalize step.
    """
    return {
        "main_info": raw_data.get("Main info", {}),
        "biometrics": raw_data.get("Biometrics", {}),
    }


def normalize_main_info(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize main info fields for payload building.
    
    Expects parsed dict with 'main_info' and 'biometrics' keys.
    
    Handles extraction of:
    - Names (name, middle_name, surname)
    - Dates (date_of_birth, place_of_birth)
    - Contacts (emails, phones)
    - IDs (gender_id, rank_id, nationality, marital_status, language)
    - Biometrics (gender from Sex field)
    """
    raw_main_info = parsed.get("main_info", {})
    biometrics = parsed.get("biometrics", {})
    refs = _load_reference_dicts()
    normalized: Dict[str, Any] = {}

    try:
        # Extract names
        name_str = raw_main_info.get("Name / Surname:", "")
        name, middle_name, surname = get_names(name_str) if name_str else (None, None, None)
        normalized["name"] = name
        normalized["middle_name"] = middle_name
        normalized["surname"] = surname
    except Exception as e:
        logger.warning("Failed to extract names: %s", e)
        normalized["name"] = None
        normalized["middle_name"] = None
        normalized["surname"] = None

    try:
        # Extract birth date
        dob_str = raw_main_info.get("Birthday / Place of birth:", "")
        date_of_birth, place_of_birth = extract_date_to_iso(dob_str) if dob_str else (None, None)
        normalized["date_of_birth"] = date_of_birth
        normalized["place_of_birth"] = place_of_birth
    except Exception as e:
        logger.warning("Failed to extract date of birth: %s", e)
        normalized["date_of_birth"] = None
        normalized["place_of_birth"] = None

    try:
        # Extract emails
        email_str = raw_main_info.get("E-mail:", "")
        emails = get_emails_list(email_str) if email_str else []
        normalized["emails"] = emails
    except Exception as e:
        logger.warning("Failed to extract emails: %s", e)
        normalized["emails"] = []

    try:
        # Extract gender_id from biometrics
        gender_str = biometrics.get("Sex", "")
        gender_id = get_id(refs["gender"], gender_str, "gender") if gender_str else None
        normalized["gender_id"] = gender_id
    except Exception as e:
        logger.warning("Failed to extract gender_id: %s", e)
        normalized["gender_id"] = None

    try:
        # Extract rank_id and additional_ranks
        rank_str = raw_main_info.get("Position applied for:", "")
        if rank_str:
            positions = get_ranks(rank_str)
            normalized["rank_id"] = get_id(refs["ranks"], positions[0], "ranks") if positions else None
            normalized["additional_ranks_id"] = (
                [get_id(refs["ranks"], rank, "ranks") for rank in positions[1:]] if len(positions) > 1 else []
            )
        else:
            normalized["rank_id"] = None
            normalized["additional_ranks_id"] = []
    except Exception as e:
        logger.warning("Failed to extract ranks: %s", e)
        normalized["rank_id"] = None
        normalized["additional_ranks_id"] = []

    try:
        # Extract nationality
        citizenship_str = raw_main_info.get("Citizenship:", "")
        if citizenship_str:
            nationality_country = search_geo(citizenship_str, "countries")
            normalized["nationality_country_id"] = nationality_country[0]["id"] if nationality_country else None
        else:
            normalized["nationality_country_id"] = None
    except Exception as e:
        logger.warning("Failed to extract nationality: %s", e)
        normalized["nationality_country_id"] = None

    try:
        # Extract language by citizenship
        citizenship_str = raw_main_info.get("Citizenship:", "")
        language_id = get_id(refs["languages"], country_to_language(citizenship_str), "languages") if citizenship_str else None
        normalized["language_id"] = language_id
    except Exception as e:
        logger.warning("Failed to extract language_id: %s", e)
        normalized["language_id"] = None

    try:
        # Extract resident country and status
        residence_str = raw_main_info.get("Country of residence / City:", "")
        citizenship_str = raw_main_info.get("Citizenship:", "")
        if residence_str:
            resident_country = get_resident_country(residence_str, citizenship_str)
            geo_resident = search_geo(resident_country, "countries")
            normalized["resident_country_id"] = geo_resident[0]["id"] if geo_resident else None
        else:
            normalized["resident_country_id"] = None
    except Exception as e:
        logger.warning("Failed to extract resident country: %s", e)
        normalized["resident_country_id"] = None

    try:
        # Extract phones
        phones_str = raw_main_info.get("Phones:", "")
        if phones_str:
            phones_list = get_phones(phones_str, normalized.get("resident_country_id"), normalized.get("nationality_country_id"), search_geo)
            normalized["phone_numbers"] = phones_list
        else:
            normalized["phone_numbers"] = []
    except Exception as e:
        logger.warning("Failed to extract phones: %s", e)
        normalized["phone_numbers"] = []

    # Stub fields that would need full HTML/soup (handled elsewhere)
    normalized["photo"] = None
    normalized["fast_note"] = None

    return normalized


def validate_main_info(normalized: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate normalized main info data.
    
    Requires at least: name, surname, rank_id, gender_id, date_of_birth.
    """
    errors = []
    
    # TODO:DRY it with list or tuple of required fields
    if not normalized.get("name"):
        errors.append("name is required")
    if not normalized.get("surname"):
        errors.append("surname is required")
    if not normalized.get("rank_id"):
        errors.append("rank_id is required")
    if not normalized.get("gender_id"):
        errors.append("gender_id is required")
    if not normalized.get("date_of_birth"):
        errors.append("date_of_birth is required")

    return len(errors) == 0, errors


def build_main_info_payload(normalized: Dict[str, Any]) -> Dict[str, Any]:
    """Build API payload for main info block.

    Converts normalized fields into the exact shape expected by POST /seafarers/
    """
    payload = {
        "name": normalized.get("name"),
        "middle_name": normalized.get("middle_name"),
        "surname": normalized.get("surname"),
        "rank_id": normalized.get("rank_id"),
        "additional_ranks_id": normalized.get("additional_ranks_id", []),
        "date_of_birth": normalized.get("date_of_birth"),
        "place_of_birth": normalized.get("place_of_birth"),
        "gender_id": normalized.get("gender_id"),
        "marital_status_id": normalized.get("marital_status_id"),
        "nationality_country_id": normalized.get("nationality_country_id"),
        "emails": [{"email": email, "comment": "", "uuid": None} for email in normalized.get("emails", [])],
        "resident_status_id": normalized.get("resident_country_id"),
        "fast_note": normalized.get("fast_note"),
        "phone_numbers": normalized.get("phone_numbers", []),
        "personal_id": normalized.get("personal_id"),
        "language_id": normalized.get("language_id"),
    }

    if normalized.get("photo"):
        payload["photo"] = normalized["photo"]

    return payload
