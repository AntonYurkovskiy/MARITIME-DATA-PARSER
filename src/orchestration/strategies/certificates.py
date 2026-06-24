"""
Certificates strategy skeleton.
"""

from typing import Dict, Any, List, Tuple


def parse_certificates_raw(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract certificates section from parsed HTML data."""
    raise NotImplementedError("parse_certificates_raw not yet implemented")


def normalize_certificates(raw_certificates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize raw certificate rows."""
    raise NotImplementedError("normalize_certificates not yet implemented")


def validate_certificates(certificates: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate normalized certificates."""
    raise NotImplementedError("validate_certificates not yet implemented")


def build_certificates_payload(certificates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build API payloads for certificates block.

    Expected payload shape per item:
    group_id, type_id, number, issued_date, expires_date,
    issued_country_id, issuer, notes, files.
    """
    raise NotImplementedError("build_certificates_payload not yet implemented")
