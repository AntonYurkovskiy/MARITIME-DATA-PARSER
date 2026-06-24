"""
Addresses strategy skeleton.
"""

from typing import Dict, Any, List, Tuple


def parse_addresses_raw(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract address section from parsed HTML data."""
    raise NotImplementedError("parse_addresses_raw not yet implemented")


def normalize_addresses(raw_addresses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize raw address rows."""
    raise NotImplementedError("normalize_addresses not yet implemented")


def validate_addresses(addresses: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate normalized addresses."""
    raise NotImplementedError("validate_addresses not yet implemented")


def build_addresses_payload(addresses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build API payloads for addresses block.

    Expected payload shape per item:
    type_id, city_id, region_id, country_id, line1, line2, zip,
    nearest_airport_id, nearest_train_station, comment.
    """
    raise NotImplementedError("build_addresses_payload not yet implemented")
