"""
Addresses strategy.

Builds a seafarer registered address payload from the parsed CV data.
The source of truth is the Main info section (Home address + Country of residence / City).
"""

from typing import Dict, Any, List, Tuple, Optional
import logging
import re
import unicodedata

from src.api.geo import search_geo, get_resident_country
from src.api.dicts import get_dict

logger = logging.getLogger(__name__)

_REFERENCE_CACHE: Dict[str, Any] = {}


def _safe_get_dict(key: str) -> List[Dict[str, Any]]:
    """Get dictionary by key without raising when endpoint is unavailable."""
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
        geo_regions = _safe_get_dict("geo/regions")
        if not geo_regions:
            geo_regions = _safe_get_dict("geo_regions")
        _REFERENCE_CACHE = {
            "geo_regions": geo_regions,
            "airports": _safe_get_dict("airports"),
        }
    return _REFERENCE_CACHE


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _norm_ascii(value: Optional[str]) -> str:
    """Lower-case, strip accents and punctuation for robust matching."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9а-яё\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_residence(value: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Split residence string into (country, region, city)."""
    if not value:
        return None, None, None

    text = str(value).strip()
    parts: List[str]
    if "/" in text:
        parts = [item.strip() for item in text.split("/") if item.strip()]
    elif "," in text:
        parts = [item.strip() for item in text.split(",") if item.strip()]
    else:
        parts = [text]

    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], None, parts[1]
    return parts[0], None, None


def _extract_apartment(home_address: str) -> Tuple[str, Optional[str]]:
    """Extract apartment/flat from free-form line1 into line2 if possible."""
    address = (home_address or "").strip()
    if not address:
        return "", None

    # Remove leading separators that can appear in malformed OCR strings.
    address = re.sub(r"^[\s,;/\\|\-]+", "", address)

    explicit_pattern = re.compile(
        r"(?i)(?:,?\s*)(?:apt\.?|apartment|flat|room|кв\.?|квартира)\s*([\w\-/]+)"
    )
    explicit_match = explicit_pattern.search(address)
    if explicit_match:
        apartment = explicit_match.group(1).strip()
        line1 = explicit_pattern.sub("", address).strip(" ,")
        return line1, apartment or None

    tail_pattern = re.compile(r"^(.*?)(\d+)\s*[/-]\s*([\w]+)$")
    tail_match = tail_pattern.match(address)
    if tail_match:
        prefix = re.sub(r"\s+", " ", tail_match.group(1)).strip(" ,")
        house_number = tail_match.group(2).strip()
        apartment = tail_match.group(3).strip()
        line1 = f"{prefix} {house_number}".strip(" ,") if prefix else house_number
        return line1, apartment or None

    return re.sub(r"\s+", " ", address).strip(" ,"), None


def _first_geo_id(term: Optional[str], geo_type: str) -> Optional[int]:
    if not term:
        return None
    results = search_geo(term, geo_type) or []
    if not results:
        return None

    first = results[0]
    if isinstance(first, dict):
        return first.get("id")
    return None


def _search_geo_first(term: Optional[str], geo_type: str) -> Optional[Dict[str, Any]]:
    if not term:
        return None
    results = search_geo(term, geo_type) or []
    if not results:
        return None
    first = results[0]
    return first if isinstance(first, dict) else None


def _get_country_name(item: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    country = item.get("country")
    if isinstance(country, dict):
        return country.get("name")
    if isinstance(country, str):
        return country
    return item.get("country_name")


def _item_name(item: Dict[str, Any]) -> str:
    return str(item.get("name") or item.get("value") or item.get("title") or "")


def _select_best_city(city_term: Optional[str], country_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not city_term:
        return None

    items = [x for x in (search_geo(city_term, "cities") or []) if isinstance(x, dict)]
    if not items:
        return None

    term_norm = _norm_ascii(city_term)
    country_norm = _norm_ascii(country_name)

    exact = [x for x in items if _norm_ascii(_item_name(x)) == term_norm]
    if country_norm:
        exact_country = [x for x in exact if _norm_ascii(_get_country_name(x)) == country_norm]
        if exact_country:
            return exact_country[0]

    if exact:
        return exact[0]

    if country_norm:
        by_country = [x for x in items if _norm_ascii(_get_country_name(x)) == country_norm]
        if by_country:
            return by_country[0]

    return items[0]


def _select_best_geo_item(term: Optional[str], geo_type: str, country_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not term:
        return None

    items = [x for x in (search_geo(term, geo_type) or []) if isinstance(x, dict)]
    if not items:
        return None

    term_norm = _norm_ascii(term)
    country_norm = _norm_ascii(country_name)

    exact = [x for x in items if _norm_ascii(_item_name(x)) == term_norm]
    if country_norm:
        exact_country = [x for x in exact if _norm_ascii(_get_country_name(x)) == country_norm]
        if exact_country:
            return exact_country[0]

    if exact:
        return exact[0]

    if country_norm:
        by_country = [x for x in items if _norm_ascii(_get_country_name(x)) == country_norm]
        if by_country:
            return by_country[0]

    return items[0]


def _looks_civil_airport(item: Dict[str, Any]) -> bool:
    name = _norm_ascii(_item_name(item))
    if not name:
        return False
    has_civil_token = any(token in name for token in ["airport", "international", "aeroport"])
    has_military_token = any(token in name for token in ["military", "air base", "heliport", "airstrip", "airfield"])
    return has_civil_token and not has_military_token


def _extract_iata_code(term: Optional[str]) -> Optional[str]:
    if not term:
        return None
    match = re.search(r"\(([A-Za-z]{3})\)", term)
    if match:
        return match.group(1).upper()

    clean = re.sub(r"[^A-Za-z]", "", term)
    if len(clean) == 3:
        return clean.upper()
    return None


def _airport_matches_iata(item: Dict[str, Any], iata_code: str) -> bool:
    if not iata_code:
        return False
    for key in ("iata", "code"):
        value = item.get(key)
        if isinstance(value, str) and value.upper() == iata_code:
            return True
    return iata_code in _item_name(item).upper()


def _airport_base_name(value: Optional[str]) -> str:
    """Normalize airport name by removing bracketed IATA-like suffixes."""
    if not value:
        return ""
    text = _norm_ascii(value)
    text = re.sub(r"\([a-z]{3}\)", " ", text)
    text = re.sub(r"\b[a-z]{3}$", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _airport_tokens(value: Optional[str]) -> List[str]:
    stop_words = {"airport", "international", "aeroport", "terminal"}
    base = _airport_base_name(value)
    tokens = [tok for tok in re.split(r"\s+", base) if tok and tok not in stop_words]
    return tokens


def _best_airport_by_tokens(items: List[Dict[str, Any]], airport_term: str) -> Optional[Dict[str, Any]]:
    """Pick best airport candidate by token overlap with input phrase."""
    if not items or not airport_term:
        return None

    term_tokens = _airport_tokens(airport_term)
    if not term_tokens:
        return None

    # In phrases like "Kaliningrad Khrabrovo Airport" the last specific token
    # usually corresponds to the airport proper name.
    if len(term_tokens) > 1:
        preferred = term_tokens[-1]
        by_preferred = [x for x in items if preferred in _airport_tokens(_item_name(x))]
        if by_preferred:
            return by_preferred[0]

    best_item: Optional[Dict[str, Any]] = None
    best_score = 0
    for item in items:
        item_tokens = set(_airport_tokens(_item_name(item)))
        score = len(item_tokens.intersection(term_tokens))
        if score > best_score:
            best_score = score
            best_item = item

    return best_item if best_score > 0 else None


def _airport_search_terms(airport_term: Optional[str]) -> List[str]:
    """Build fallback airport search terms for cases where full phrase has no hits."""
    if not airport_term:
        return []

    raw = str(airport_term).strip()
    terms: List[str] = [raw]

    base = _airport_base_name(raw)
    if base and base != _norm_ascii(raw):
        terms.append(base)

    tokens = _airport_tokens(raw)
    if tokens:
        terms.append(tokens[-1])
        terms.append(f"{tokens[-1]} airport")
        if len(tokens) > 1:
            terms.append(" ".join(tokens[-2:]))

    unique: List[str] = []
    seen = set()
    for term in terms:
        norm = _norm_ascii(term)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique.append(term)
    return unique


def _extract_city_from_line1(line1: Optional[str]) -> Optional[str]:
    if not line1:
        return None
    parts = [part.strip() for part in str(line1).split(",") if part and part.strip()]
    if len(parts) < 2:
        return None

    # Usually format: Country, City, street...
    for candidate in parts[1:3]:
        if re.search(r"[A-Za-zА-Яа-яЁё]", candidate):
            return candidate
    return None


def _build_unresolved_comment(existing_comment: Optional[str], unresolved: List[Tuple[str, str]]) -> Optional[str]:
    if not unresolved:
        return existing_comment

    details = ", ".join([f'"{field}" - "{value}"' for field, value in unresolved])
    text = f"Нераспознанные поля: {details}"
    if existing_comment:
        return f"{existing_comment}; {text}"
    return text


def _extract_region_id_from_city(city_obj: Optional[Dict[str, Any]]) -> Optional[int]:
    if not city_obj:
        return None
    if city_obj.get("region_id") is not None:
        return city_obj.get("region_id")
    region = city_obj.get("region")
    if isinstance(region, dict):
        return region.get("id")
    return None


def _find_dict_id(term: Optional[str], dictionary_items: Any) -> Optional[int]:
    if not term or not isinstance(dictionary_items, list):
        return None

    needle = _norm(term)
    for item in dictionary_items:
        if not isinstance(item, dict):
            continue
        for key in ("value", "name", "title", "label"):
            if _norm(item.get(key)) == needle and item.get("id") is not None:
                return item.get("id")

    for item in dictionary_items:
        if not isinstance(item, dict):
            continue
        for key in ("value", "name", "title", "label"):
            candidate = _norm(item.get(key))
            if needle and candidate and (needle in candidate or candidate in needle):
                if item.get("id") is not None:
                    return item.get("id")

    return None


def _resolve_airport_id(airport_term: Optional[str], refs: Dict[str, Any]) -> Optional[int]:
    """Resolve airport with strict matching and country-aware filtering."""
    return None


def _resolve_airport_id_by_country(
    airport_term: Optional[str],
    country_name: Optional[str],
    refs: Dict[str, Any],
) -> Optional[int]:
    if not airport_term:
        return None

    country_norm = _norm_ascii(country_name)
    term_norm = _norm_ascii(airport_term)
    iata_code = _extract_iata_code(airport_term)

    # 0) Prefer exact static dictionary match first.
    # It gives stable IDs and avoids noisy geo results for short terms.
    dict_items = refs.get("airports") if isinstance(refs, dict) else None
    if isinstance(dict_items, list):
        exact_dict_match = None
        for item in dict_items:
            if not isinstance(item, dict):
                continue
            if _norm_ascii(_item_name(item)) == term_norm:
                exact_dict_match = item
                break
        if exact_dict_match and exact_dict_match.get("id") is not None:
            return exact_dict_match.get("id")

    # 1) Prefer geo search because local airports dict can be stale.
    geo_items: List[Dict[str, Any]] = []
    for term in _airport_search_terms(airport_term):
        for item in search_geo(term, "airports") or []:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if any(existing.get("id") == item_id for existing in geo_items):
                continue
            geo_items.append(item)

    if geo_items:
        country_filtered = (
            [x for x in geo_items if _norm_ascii(_get_country_name(x)) == country_norm]
            if country_norm
            else geo_items
        )
        pool = country_filtered or geo_items

        if iata_code:
            by_iata = [x for x in pool if _airport_matches_iata(x, iata_code)]
            if by_iata and by_iata[0].get("id") is not None:
                return by_iata[0].get("id")

        exact_name = [x for x in pool if _norm_ascii(_item_name(x)) == term_norm]
        if exact_name and exact_name[0].get("id") is not None:
            return exact_name[0].get("id")

        # Alias match: e.g. "Kaliningrad Khrabrovo Airport" -> "Khrabrovo Airport (KGD)".
        term_base = _airport_base_name(airport_term)
        if term_base:
            by_alias = [
                x
                for x in pool
                if (
                    _airport_base_name(_item_name(x))
                    and (
                        _airport_base_name(_item_name(x)) in term_base
                        or term_base in _airport_base_name(_item_name(x))
                    )
                )
            ]
            if by_alias and by_alias[0].get("id") is not None:
                return by_alias[0].get("id")

        by_tokens = _best_airport_by_tokens(pool, airport_term)
        if by_tokens and by_tokens.get("id") is not None:
            return by_tokens.get("id")

        civil = [x for x in pool if _looks_civil_airport(x)]
        if civil and civil[0].get("id") is not None:
            return civil[0].get("id")

        if pool[0].get("id") is not None:
            return pool[0].get("id")

    return None


def parse_addresses_raw(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract address-related fields from parsed HTML data."""
    main_info = raw_data.get("Main info", {}) if isinstance(raw_data, dict) else {}
    additional_info = raw_data.get("Additional info", {}) if isinstance(raw_data, dict) else {}

    home_address = main_info.get("Home address:") or additional_info.get("Kin address:")
    residence = main_info.get("Country of residence / City:")
    closest_airport = main_info.get("Closest airport:")
    citizenship = main_info.get("Citizenship:")

    if not any([home_address, residence, closest_airport]):
        return []

    return [
        {
            "type_id": 1,
            "home_address": home_address,
            "residence": residence,
            "closest_airport": closest_airport,
            "citizenship": citizenship,
            "nearest_train_station": None,
            "comment": None,
        }
    ]


def normalize_addresses(raw_addresses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize raw address rows into API-ready structure."""
    normalized: List[Dict[str, Any]] = []
    refs = _load_reference_dicts()

    for raw in raw_addresses or []:
        raw_home_address = (raw.get("home_address") or "").strip()
        line1, apartment = _extract_apartment(raw_home_address)

        residence = raw.get("residence")
        citizenship = raw.get("citizenship")
        closest_airport = raw.get("closest_airport")

        country_name, region_name, city_name = _split_residence(residence)
        original_city_term = city_name
        country_name = get_resident_country(residence, citizenship) or country_name

        # If residence contains only city (e.g. "Uman"), preserve it as city candidate.
        if not city_name and residence and _norm_ascii(residence) != _norm_ascii(country_name):
            city_name = residence

        country_id = _first_geo_id(country_name, "countries") if country_name else None
        city_obj = _select_best_city(city_name, country_name) if city_name else None

        # Fallback: try city from line1 like "Latvia, Jurmala, ...".
        if city_obj is None:
            city_from_line1 = _extract_city_from_line1(line1)
            if city_from_line1:
                city_obj = _select_best_city(city_from_line1, country_name)
                if city_obj is not None and not original_city_term:
                    city_name = city_from_line1

        city_id = city_obj.get("id") if city_obj else None

        airport_id = _resolve_airport_id_by_country(closest_airport, country_name, refs)

        region_id = _extract_region_id_from_city(city_obj)
        if region_id is None:
            # Try geo regions search first (country-aware).
            region_geo = _select_best_geo_item(region_name, "regions", country_name) if region_name else None
            if region_geo and region_geo.get("id") is not None:
                region_id = region_geo.get("id")
        if region_id is None:
            region_id = _find_dict_id(region_name, refs.get("geo_regions"))

        unresolved: List[Tuple[str, str]] = []
        if city_id is None and city_name:
            unresolved.append(("city_id", str(city_name)))
        if region_id is None and region_name:
            unresolved.append(("region_id", str(region_name)))
        if airport_id is None and closest_airport:
            unresolved.append(("nearest_airport_id", str(closest_airport)))
        if country_id is None and country_name:
            unresolved.append(("country_id", str(country_name)))

        comment = _build_unresolved_comment(raw.get("comment"), unresolved)

        entry = {
            "type_id": raw.get("type_id", 1),
            "city_id": city_id,
            "region_id": region_id,
            "country_id": country_id,
            "line1": line1 or None,
            "line2": apartment,
            "zip": None,
            "nearest_airport_id": airport_id,
            "nearest_train_station": raw.get("nearest_train_station"),
            "comment": comment,
        }

        normalized.append(entry)

    return normalized


def validate_addresses(addresses: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate normalized addresses.

    Empty result is not an error: some CVs simply do not provide a usable home address.
    """
    if not addresses:
        return True, []

    errors: List[str] = []
    valid_count = 0

    for index, address in enumerate(addresses):
        entry_errors: List[str] = []
        if not address.get("line1"):
            entry_errors.append(f"entry[{index}]: line1 is required")
        if address.get("type_id") is None:
            entry_errors.append(f"entry[{index}]: type_id is required")

        if entry_errors:
            errors.extend(entry_errors)
        else:
            valid_count += 1

    if valid_count == 0:
        return False, errors or ["no valid addresses found"]

    return True, []


def build_addresses_payload(addresses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build API payloads for addresses block.

    Expected payload shape per item:
    type_id, city_id, region_id, country_id, line1, line2, zip,
    nearest_airport_id, nearest_train_station, comment.
    """
    payloads: List[Dict[str, Any]] = []

    for address in addresses or []:
        if not address.get("line1"):
            logger.warning("Skipping address entry without line1: %s", address)
            continue

        payloads.append(
            {
                "type_id": address.get("type_id", 1),
                "city_id": address.get("city_id"),
                "region_id": address.get("region_id"),
                "country_id": address.get("country_id"),
                "line1": address.get("line1"),
                "line2": address.get("line2"),
                "zip": address.get("zip"),
                "nearest_airport_id": address.get("nearest_airport_id"),
                "nearest_train_station": address.get("nearest_train_station"),
                "comment": address.get("comment"),
            }
        )

    return payloads
