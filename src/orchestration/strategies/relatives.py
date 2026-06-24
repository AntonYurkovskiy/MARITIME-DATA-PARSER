"""
Relatives strategy skeleton.
"""

from typing import Dict, Any, List, Tuple


def parse_relatives_raw(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract relatives section from parsed HTML data."""
    raise NotImplementedError("parse_relatives_raw not yet implemented")


def normalize_relatives(raw_relatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize raw relative rows."""
    raise NotImplementedError("normalize_relatives not yet implemented")


def validate_relatives(relatives: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate normalized relatives."""
    raise NotImplementedError("validate_relatives not yet implemented")


def build_relatives_payload(relatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build API payloads for relatives block.

    Expected nested payload shape per item:
    name, surname, personal_id, date_of_birth, gender_id,
    relationship_type_id, language_id, phone_numbers, emails, addresses.
    """
    raise NotImplementedError("build_relatives_payload not yet implemented")
