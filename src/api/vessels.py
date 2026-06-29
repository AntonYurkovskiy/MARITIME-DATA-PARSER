import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz, utils

from src.api.client import _get_session
from src.api.geo import search_geo
from src.api.seafarers import get_id
from src.config import API_BASE_URL
from src.extractors.dates import extract_date_to_iso
from src.utils.mapping import get_value
from src.utils.validators import _normalize, simple_cleaned_vessel_name
from src.cache import get_cache, is_cache_enabled

logger = logging.getLogger(__name__)


def _build_search_payload(vessel_name: str, source: str) -> Dict[str, Any]:
    return {
        "pagination": {"page": 1, "per_page": 25},
        "filters": {
            "combinator": "or",
            "rules": [
                {
                    "field": "details_history.name",
                    "operator": "contains",
                    "value": vessel_name,
                },
                {
                    "field": "name",
                    "operator": "contains",
                    "value": vessel_name,
                },
                {
                    "field": "imo_no",
                    "operator": "contains",
                    "value": vessel_name,
                },
            ],
        },
        "metadata": {"source": source},
    }


def _send_search_request(search_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    session = _get_session()
    response = session.post(search_url, json=payload)
    response.raise_for_status()
    return response.json()


def _get_search_url(route: str) -> str:
    url = f"{API_BASE_URL}/vessels"
    return f"{url}{route}"


def search_vessel(vessel_name: str, source: str, route: str) -> Dict[str, Any]:
    search_url = _get_search_url(route)
    payload = _build_search_payload(vessel_name, source)
    return _send_search_request(search_url, payload)


def _extract_items(result: Any) -> List[Dict[str, Any]]:
    if isinstance(result, dict):
        items = result.get("items", []) or []
        if isinstance(items, list):
            return items
        return []
    if isinstance(result, list):
        return result
    return []


def _get_vessel_name(item: Any) -> str:
    if not isinstance(item, dict):
        return ""

    details = item.get("details_history") or {}
    if not isinstance(details, dict):
        details = {}

    return (
        item.get("name")
        or details.get("name")
        or item.get("imo_no")
        or ""
    )


def _name_variants(vessel_name: str) -> List[str]:
    parts = _normalize(vessel_name).split()
    variants: List[str] = [vessel_name]

    if len(parts) >= 2:
        variants.append(parts[0])
        variants.append(parts[-1])
        variants.append(" ".join(parts[:2]))
        variants.append(" ".join(parts[-2:]))

    seen = set()
    result: List[str] = []
    for v in variants:
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            result.append(v)
    return result


from typing import Optional, Dict, Any, List, Tuple

def _best_fuzzy_item(
    query: str,
    items: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], int]:
    best_item: Optional[Dict[str, Any]] = None
    best_score: int = -1

    for item in items:
        candidate = _get_vessel_name(item)
        if not candidate:
            continue

        score = fuzz.WRatio(
            query,
            candidate,
            processor=utils.default_process,
            score_cutoff=0,
        )
        
        score = int(score)

        if score > best_score:
            best_score = score
            best_item = item

    return best_item, best_score


def find_exact_vessel_uuid(
    vessel_name: str,
    sources: List[Tuple[str, str]],
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    best_item: Optional[Dict[str, Any]] = None
    best_source: Optional[str] = None
    best_score: int = -1

    for source, route in sources:
        result = search_vessel(vessel_name, source, route)
        items = _extract_items(result)

        if items:
            for item in items:
                candidate = _get_vessel_name(item)
                if not candidate:
                    continue

                if _normalize(candidate) == _normalize(vessel_name):
                    return item, source, 100

            tmp_item, score = _best_fuzzy_item(vessel_name, items)
            if tmp_item and score > best_score:
                best_item = tmp_item
                best_source = source
                best_score = score

    return best_item, best_source, best_score


def search_by_name_variants(
    vessel_name: str,
    sources: List[Tuple[str, str]],
    best_item: Optional[Dict[str, Any]],
    best_source: Optional[str],
    best_score: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    for query in _name_variants(vessel_name):
        if _normalize(query) == _normalize(vessel_name):
            continue

        for source, route in sources:
            result = search_vessel(query, source, route)
            items = _extract_items(result)

            if not items:
                continue

            for item in items:
                candidate = _get_vessel_name(item)
                if not candidate:
                    continue

                score = fuzz.WRatio(
                    vessel_name,
                    candidate,
                    processor=utils.default_process,
                    score_cutoff=0,
                )
                score = int(score)

                if score > best_score:
                    best_item = item
                    best_source = source
                    best_score = score

    return best_item, best_source, best_score


def get_vessel_uuid(
    vessel_name: str,
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    # Try persistent cache first (vessel lookups are expensive: up to 3 API calls)
    if is_cache_enabled():
        cache = get_cache()
        cache_key = f"vessel_uuid:{vessel_name.lower().strip()}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug(f"✅ Cache hit for vessel: {vessel_name}")
            return cached.get("uuid"), cached.get("source"), cached.get("item")

    sources: List[Tuple[str, str]] = [
        ("historical", "/historical/search"),
        ("main", "/search"),
        ("external", "/search"),
    ]

    best_item: Optional[Dict[str, Any]] = None
    best_source: Optional[str] = None
    best_score: int = -1

    best_item, best_source, best_score = find_exact_vessel_uuid(vessel_name, sources)

    if best_item and best_score >= 100 and best_source:
        result_uuid = best_item.get("uuid")
        if is_cache_enabled():
            cache = get_cache()
            cache_key = f"vessel_uuid:{vessel_name.lower().strip()}"
            cache.set(cache_key, {"uuid": result_uuid, "source": best_source, "item": best_item})
        return result_uuid, best_source, best_item

    best_item, best_source, best_score = search_by_name_variants(
        vessel_name, sources, best_item, best_source, best_score
    )

    if best_item and best_score >= 80 and best_source:
        result_uuid = best_item.get("uuid")
        if is_cache_enabled():
            cache = get_cache()
            cache_key = f"vessel_uuid:{vessel_name.lower().strip()}"
            cache.set(cache_key, {"uuid": result_uuid, "source": best_source, "item": best_item})
        return result_uuid, best_source, best_item

    # Cache negative result too (vessel not found)
    if is_cache_enabled():
        cache = get_cache()
        cache_key = f"vessel_uuid:{vessel_name.lower().strip()}"
        cache.set(cache_key, {"uuid": None, "source": None, "item": None})

    return None, None, None


def resolve_historical_vessel(
    cleaned_vessel_name: str,
    raw_vessel_name: str,
    local_vessel_types: Dict[str, Any],
) -> Tuple[str, str]:
    vessel_uuid: Optional[str] = None
    source = "historical"

    if cleaned_vessel_name:
        vessel_uuid, search_source, _ = get_vessel_uuid(cleaned_vessel_name)
        if search_source and search_source != "historical":
            logger.debug(
                "Historical contract vessel lookup returned non-historical source=%s; creating historical vessel",
                search_source,
            )
            vessel_uuid = None

    if not vessel_uuid:
        created_vessel = _add_new_vessel(
            {"Vessel Name / Flag": raw_vessel_name, "Vessel type / DWT": raw_vessel_name},
            local_vessel_types,
        )
        vessel_uuid = (
            created_vessel.get("inserted", {}).get("uuid")
            or created_vessel.get("uuid")
            or created_vessel.get("id")
        )

    if not vessel_uuid:
        raise ValueError("Unable to resolve or create vessel UUID for historical contract")

    return vessel_uuid, source


def parse_contract_period(contract_period: str) -> Tuple[str, str]:
    if not contract_period or not isinstance(contract_period, str):
        raise ValueError("Missing or invalid From - Till value: %r" % contract_period)

    period_parts = [
        part.strip()
        for part in re.split(r"\s*[-–—]\s*", contract_period, maxsplit=1)
        if part.strip()
    ]
    if len(period_parts) < 2:
        raise ValueError("Unable to split From - Till into two dates: %r" % contract_period)

    sign_on_date_raw = extract_date_to_iso(period_parts[0])
    sign_off_date_raw = extract_date_to_iso(period_parts[1])
    sign_on_date = sign_on_date_raw[0] if sign_on_date_raw else None
    sign_off_date = sign_off_date_raw[0] if sign_off_date_raw else None

    if not sign_on_date or not sign_off_date:
        raise ValueError(
            "Unable to parse contract dates from From - Till: %r (on=%r off=%r)"
            % (contract_period, sign_on_date, sign_off_date)
        )

    return sign_on_date, sign_off_date


def build_historical_contract_payload(
    seafarer_uuid: str,
    rank_id: str,
    vessel_uuid: str,
    source: str,
    sign_on_date: str,
    sign_off_date: str,
    raw_vessel_name: str,
) -> Dict[str, Any]:
    if not raw_vessel_name:
        raise ValueError("Missing Vessel Name / Flag for historical contract entry")

    return {
        "is_historical": True,
        "seafarer_uuid": seafarer_uuid,
        "rank_id": rank_id,
        "vessel": {
            "uuid": vessel_uuid,
            "source": source,
        },
        "is_automatic": True,
        "sign_on_date": sign_on_date,
        "sign_off_date": sign_off_date,
        "off_reason_id": 0,
        "is_historical": 1,
        "details": "Imported from CV",
    }


def post_historical_contract(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    session = _get_session()
    logger.debug("Posting historical contract: %s", payload)

    response = session.post(url, json=payload)
    if response.status_code >= 400:
        logger.error(
            "Historical contract failed (%s): status=%s text=%s payload=%s",
            url,
            response.status_code,
            response.text,
            payload,
        )
    response.raise_for_status()
    return response.json()


def _validate_new_vessel_input(contract_details: Dict[str, Any]) -> Tuple[str, str]:
    name_and_flag = contract_details.get("Vessel Name / Flag")
    if not name_and_flag:
        raise ValueError("Missing Vessel Name / Flag in historical contract entry")

    if " / " not in name_and_flag:
        raise ValueError(f"Unsupported Vessel Name / Flag format: {name_and_flag!r}")

    vessel_name_raw, flag_country = name_and_flag.rsplit(" / ", 1)
    name = simple_cleaned_vessel_name(vessel_name_raw.strip()).upper()
    return name, flag_country.strip()


def _resolve_flag_country_id(flag_country: str) -> int:
    flag_search = search_geo(flag_country)
    if flag_search:
        return flag_search[0]["id"]

    mapped_flag = get_value(flag_country)
    if not mapped_flag:
        raise ValueError(f"Unable to resolve vessel flag country: {flag_country!r}")

    flag_search = search_geo(mapped_flag)
    if not flag_search:
        raise ValueError(f"Unable to resolve flag country id for: {flag_country!r}")

    return flag_search[0]["id"]


def _resolve_vessel_type_id(
    contract_details: Dict[str, Any],
    local_vessel_types: Dict[str, Any],
) -> int:
    vessel_type = contract_details.get("Vessel type / DWT")
    if not vessel_type or " / " not in vessel_type:
        raise ValueError(f"Missing or unsupported Vessel type / DWT format: {vessel_type!r}")

    vessel_type_name = vessel_type.rsplit(" / ", 1)[0].strip()
    type_id = get_id(local_vessel_types, vessel_type_name, "vessel_types")
    if type_id is None:
        raise ValueError(f"Unable to resolve vessel type id for: {vessel_type!r}")

    return type_id


def _build_historical_vessel_payload(
    name: str,
    type_id: int,
    flag_country_id: int,
) -> Dict[str, Any]:
    return {
        "name": name,
        "imo_no": "No info",
        "type_id": type_id,
        "gt": 1,
        "flag_country_id": flag_country_id,
    }


def _create_historical_vessel(payload: Dict[str, Any]) -> Dict[str, Any]:
    session = _get_session()
    url = f"{API_BASE_URL}/vessels/historical"
    response = session.post(url, json=payload)
    logger.debug("Response status: %s", response.status_code)
    logger.debug("Response text: %s", response.text)
    response.raise_for_status()
    return response.json()


def _add_new_vessel(
    contract_details: Dict[str, Any],
    local_vessel_types: Dict[str, Any],
) -> Dict[str, Any]:
    name, flag_country = _validate_new_vessel_input(contract_details)
    flag_country_id = _resolve_flag_country_id(flag_country)
    type_id = _resolve_vessel_type_id(contract_details, local_vessel_types)
    payload = _build_historical_vessel_payload(name, type_id, flag_country_id)
    return _create_historical_vessel(payload)


def add_historical_contract(
    sea_service: Dict[str, Any],
    seafarer_uuid: str,
    ranks: Dict[str, Any],
    local_vessel_types: Dict[str, Any],
) -> Dict[str, Any]:
    rank_id = get_id(ranks, sea_service.get("Position"), "ranks")
    if not rank_id:
        raise ValueError(
            "Missing rank_id for historical contract position: %s" % sea_service.get("Position")
        )

    raw_vessel_name_any = sea_service.get("Vessel Name / Flag")
    cleaned_vessel_name_any = (
        simple_cleaned_vessel_name(raw_vessel_name_any) if raw_vessel_name_any else None
    )

    raw_vessel_name = raw_vessel_name_any or ""
    cleaned_vessel_name = cleaned_vessel_name_any or ""

    vessel_uuid, source = resolve_historical_vessel(
        cleaned_vessel_name,
        raw_vessel_name,
        local_vessel_types,
    )

    contract_period_any = sea_service.get("From - Till")
    contract_period = contract_period_any or ""

    sign_on_date, sign_off_date = parse_contract_period(contract_period)

    url = f"{API_BASE_URL}/contracts/historical"
    payload = build_historical_contract_payload(
        seafarer_uuid,
        str(rank_id),
        vessel_uuid,
        source,
        sign_on_date,
        sign_off_date,
        raw_vessel_name,
    )

    return post_historical_contract(url, payload)


def search_external_vessel(name_or_imo: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not name_or_imo:
        # Тесты ожидают None для пустой строки и None
        return None

    session = _get_session()

    url = f"{API_BASE_URL}/vessels/search"
    payload = {
        "pagination": {"page": 1, "per_page": 25},
        "filters": {
            "combinator": "or",
            "rules": [
                {"field": "name", "operator": "contains", "value": name_or_imo},
                {"field": "imo_no", "operator": "contains", "value": name_or_imo},
            ],
        },
        "metadata": {"external": True},
    }

    response = session.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    items = data.get("items", []) or []
    if isinstance(items, list):
        return items
    return []