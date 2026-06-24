"""
Contracts (sea service) strategy.

Extracts, normalizes, validates and builds payloads for historical contracts block.
Uses existing extractors and vessel/rank lookup functions without modifying them.
"""

import re
import logging
from typing import Dict, Any, List, Tuple, Optional

from src.api.dicts import get_dict
from src.api.seafarers import get_id
from src.api.vessels import get_vessel_uuid, resolve_historical_vessel
from src.extractors.dates import extract_date_to_iso
from src.utils.validators import simple_cleaned_vessel_name

logger = logging.getLogger(__name__)

# Cache reference dicts
_RANKS_CACHE: Optional[Dict[str, Any]] = None
_VESSEL_TYPES_CACHE: Optional[Dict[str, Any]] = None


def _get_ranks_dict() -> Dict[str, Any]:
    global _RANKS_CACHE
    if _RANKS_CACHE is None:
        _RANKS_CACHE = get_dict("ranks")
    return _RANKS_CACHE


def _get_vessel_types_dict() -> Dict[str, Any]:
    global _VESSEL_TYPES_CACHE
    if _VESSEL_TYPES_CACHE is None:
        _VESSEL_TYPES_CACHE = get_dict("vessel_types")
    return _VESSEL_TYPES_CACHE


def _parse_vessel_name_flag(vessel_name_flag: str) -> Tuple[str, str]:
    """Split 'VESSEL NAME / FLAG' into (vessel_name, flag)."""
    if " / " in vessel_name_flag:
        parts = vessel_name_flag.split(" / ", 1)
        return parts[0].strip(), parts[1].strip()
    return vessel_name_flag.strip(), ""


def _parse_vessel_type_dwt(vessel_type_dwt: str) -> Tuple[str, Optional[int]]:
    """Split 'TYPE / DWT' into (vessel_type, dwt_int_or_None)."""
    if " / " in vessel_type_dwt:
        parts = vessel_type_dwt.split(" / ", 1)
        vessel_type = parts[0].strip()
        dwt_str = parts[1].strip()
        try:
            dwt = int(dwt_str) if dwt_str else None
        except ValueError:
            dwt = None
        return vessel_type, dwt
    return vessel_type_dwt.strip(), None


def _parse_period(period_str: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse 'DD.MM.YYYY - DD.MM.YYYY' into (sign_on_iso, sign_off_iso)."""
    if not period_str:
        return None, None
    parts = re.split(r"\s*[-–—]\s*", period_str, maxsplit=1)
    if len(parts) < 2:
        return None, None

    sign_on_raw = extract_date_to_iso(parts[0].strip())
    sign_off_raw = extract_date_to_iso(parts[1].strip())
    sign_on = sign_on_raw[0] if sign_on_raw else None
    sign_off = sign_off_raw[0] if sign_off_raw else None
    return sign_on, sign_off


def parse_sea_service_raw(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract sea service section from parsed HTML data."""
    entries = raw_data.get("Sea service (last 5 years)", [])
    return entries if isinstance(entries, list) else []


def normalize_sea_service(raw_contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize raw contract rows.

    For each entry resolves:
    - rank_id via API dict lookup
    - sign_on_date / sign_off_date via date extractor
    - vessel_name, vessel_flag, vessel_type, dwt from string fields
    """
    if not raw_contracts:
        return []

    ranks = _get_ranks_dict()
    normalized = []

    for row in raw_contracts:
        entry: Dict[str, Any] = {}

        # Rank
        try:
            rank_str = row.get("Position", "")
            entry["rank"] = rank_str
            entry["rank_id"] = get_id(ranks, rank_str, "ranks") if rank_str else None
        except Exception as e:
            logger.warning("Failed to resolve rank '%s': %s", row.get("Position"), e)
            entry["rank"] = row.get("Position", "")
            entry["rank_id"] = None

        # Vessel name and flag
        try:
            vessel_name_flag = row.get("Vessel Name / Flag", "")
            vessel_name, vessel_flag = _parse_vessel_name_flag(vessel_name_flag)
            entry["vessel_name"] = vessel_name
            entry["vessel_flag"] = vessel_flag
            entry["vessel_name_raw"] = vessel_name_flag
        except Exception as e:
            logger.warning("Failed to parse vessel name/flag '%s': %s", row.get("Vessel Name / Flag"), e)
            entry["vessel_name"] = row.get("Vessel Name / Flag", "")
            entry["vessel_flag"] = ""
            entry["vessel_name_raw"] = row.get("Vessel Name / Flag", "")

        # Vessel type and DWT
        try:
            vessel_type_dwt = row.get("Vessel type / DWT", "")
            vessel_type, dwt = _parse_vessel_type_dwt(vessel_type_dwt)
            entry["vessel_type"] = vessel_type
            entry["dwt"] = dwt
        except Exception as e:
            logger.warning("Failed to parse vessel type/dwt '%s': %s", row.get("Vessel type / DWT"), e)
            entry["vessel_type"] = row.get("Vessel type / DWT", "")
            entry["dwt"] = None

        # Dates
        try:
            sign_on, sign_off = _parse_period(row.get("From - Till", ""))
            entry["sign_on_date"] = sign_on
            entry["sign_off_date"] = sign_off
        except Exception as e:
            logger.warning("Failed to parse period '%s': %s", row.get("From - Till"), e)
            entry["sign_on_date"] = None
            entry["sign_off_date"] = None

        # Shipowner / Country
        try:
            shipowner_country = row.get("Shipowner / Country", "")
            if " / " in shipowner_country:
                parts = shipowner_country.split(" / ", 1)
                entry["shipowner"] = parts[0].strip()
                entry["shipowner_country"] = parts[1].strip()
            else:
                entry["shipowner"] = shipowner_country.strip()
                entry["shipowner_country"] = ""
        except Exception as e:
            logger.warning("Failed to parse shipowner '%s': %s", row.get("Shipowner / Country"), e)
            entry["shipowner"] = ""
            entry["shipowner_country"] = ""

        normalized.append(entry)

    return normalized


def validate_contracts(contracts: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate normalized sea service contracts.

    Returns (True, []) if at least one valid entry exists,
    or (False, [errors]) if all entries are invalid.
    """
    if not contracts:
        return False, ["no sea service entries found"]

    errors = []
    valid_count = 0

    for i, contract in enumerate(contracts):
        entry_errors = []
        if not contract.get("vessel_name"):
            entry_errors.append(f"entry[{i}]: vessel_name is required")
        if not contract.get("sign_on_date"):
            entry_errors.append(f"entry[{i}]: sign_on_date is required")
        if not contract.get("sign_off_date"):
            entry_errors.append(f"entry[{i}]: sign_off_date is required")
        if entry_errors:
            errors.extend(entry_errors)
        else:
            valid_count += 1

    if valid_count == 0:
        return False, errors or ["no valid sea service entries"]

    return True, []


def build_contracts_payloads(contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build API payloads for contracts block.

    Returns list of individual contract dicts for POST /contracts.
    Each dict represents one historical contract (seafarer_uuid injected by pipeline from context).
    Vessel UUID is resolved via API lookup; falls back to raw name if not found.
    """
    payloads = []

    vessel_types = _get_vessel_types_dict()

    for contract in contracts:
        # Skip entries without minimum required fields
        if not contract.get("vessel_name") or not contract.get("sign_on_date") or not contract.get("sign_off_date"):
            logger.warning(
                "Skipping contract entry due to missing required fields: vessel=%s on=%s off=%s",
                contract.get("vessel_name"),
                contract.get("sign_on_date"),
                contract.get("sign_off_date"),
            )
            continue

        # Resolve vessel UUID with legacy parity:
        # 1) search known vessel
        # 2) if not found in historical source, create historical vessel
        vessel_uuid: Optional[str] = None
        source = "historical"
        try:
            cleaned_name = simple_cleaned_vessel_name(contract["vessel_name"])
            raw_name = contract.get("vessel_name_raw") or contract.get("vessel_name") or ""
            if cleaned_name:
                vessel_uuid, found_source, _ = get_vessel_uuid(cleaned_name)
                if vessel_uuid and found_source == "historical":
                    source = found_source
                else:
                    vessel_uuid = None
            if not vessel_uuid:
                vessel_uuid, source = resolve_historical_vessel(cleaned_name, raw_name, vessel_types)
        except Exception as e:
            logger.warning("Vessel UUID lookup failed for '%s': %s", contract.get("vessel_name"), e)
            # Keep payload generation resilient for partially normalized/manual test inputs.
            # Runtime API compatibility is handled later in pipeline adaptation.
            vessel_uuid = None
            source = "historical"

        payload: Dict[str, Any] = {
            "is_historical": True,
            "rank_id": contract.get("rank_id"),
            "vessel": {
                "uuid": vessel_uuid,
                "source": source or "historical",
                "name": contract.get("vessel_name"),
                "flag": contract.get("vessel_flag"),
            },
            "sign_on_date": contract["sign_on_date"],
            "sign_off_date": contract["sign_off_date"],
            "is_automatic": True,
            "off_reason_id": 0,
            "details": "Imported from CV",
        }
        payloads.append(payload)

    return payloads
