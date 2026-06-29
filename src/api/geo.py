# ПОИСК В ГЕОГРАФИЧЕСКИХ СЛОВАРЯХ
from typing import Any, Callable, Dict, List, Optional
import logging
import os

from src.api.client import _get_session
from src.config import API_BASE_URL
from src.domain.languages import COUNTRY_TO_LANGUAGE
from src.utils.validators import only_letters_regex
from src.cache import get_cache

logger = logging.getLogger(__name__)

# Allow disabling cache for tests
_CACHE_DISABLED = os.getenv("DISABLE_CACHE", "false").lower() == "true"


def search_geo(search_term: Optional[str], geo_type: str = "countries") -> Optional[List[Dict[str, Any]]]:
    """Поиск в geo словарях.

    Возвращает:
      - None, если search_term пустой/None;
      - пустой список при HTTP-ошибке;
      - список словарей при успешном запросе.
    """
    # Пустой ввод → None (как требуют тесты empty/None)
    if not search_term:
        return None

    # Try to get from persistent cache first (unless cache disabled)
    if not _CACHE_DISABLED:
        cache = get_cache()
        cache_key = f"geo:{geo_type}:{search_term}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            logger.debug(f"✅ Cache hit for geo search: {search_term} ({geo_type})")
            return cached_result

    session = _get_session()

    base_url = f"{API_BASE_URL}/dict"
    if geo_type in ["countries", "cities", "regions"]:
        url = f"{base_url}/geo/{geo_type}/search/{search_term}"
    else:
        # airports, seaports
        url = f"{base_url}/{geo_type}/search/{search_term}"

    payload = {"term": search_term}
    logger.debug("🔍 GET %s", url)
    response = session.get(url, json=payload)

    logger.debug("Status: %s", response.status_code)
    if response.status_code == 200:
        data = response.json()
        logger.info("✅ Найдено: %s записей", len(data))
        
        # Cache the result (unless cache disabled)
        if not _CACHE_DISABLED:
            cache = get_cache()
            cache_key = f"geo:{geo_type}:{search_term}"
            cache.set(cache_key, data)
            logger.debug(f"💾 Cached geo search: {search_term} ({geo_type})")
        
        return data

    # HTTP-ошибка → [] (по тесту test_search_geo_http_error)
    logger.warning("❌ Ошибка поиска: %s", response.text)
    return []


def search_geo_exact(search_term: str, geo_type: str = "cities") -> List[Dict[str, Any]]:
    """Только ТОЧНЫЕ совпадения по названию."""
    all_results = search_geo(search_term, geo_type) or []

    exact_matches = [
        item
        for item in all_results
        if item.get("name", "").strip().lower() == search_term.lower()
    ]

    return exact_matches


def search_geo_dict(geo_type: str = "countries") -> Optional[List[Dict[str, Any]]]:
    """Поиск в geo словарях без search_term (полный словарь).

    Возвращает:
      - None при некорректном geo_type или HTTP-ошибке;
      - список словарей при успешном запросе.
    """
    if not geo_type:
        return None

    session = _get_session()

    base_url = f"{API_BASE_URL}/dict"
    if geo_type in ["countries", "cities", "regions"]:
        url = f"{base_url}/geo/{geo_type}/search/"
    else:
        # airports, seaports
        url = f"{base_url}/{geo_type}/search/"

    response = session.get(url)

    logger.debug("Status: %s", response.status_code)
    if response.status_code == 200:
        data = response.json()
        logger.debug("✅ Найдено: %s записей", len(data))
        return data
    else:
        logger.warning("❌ Ошибка поиска: %s", response.text)
        return None


def get_resident_country(search_term: str, citizenship: str) -> Optional[str]:
    """Определяет страну проживания по строке и гражданству."""
    if not search_term:
        return None

    if "/" in search_term:
        return search_term.split("/", 1)[0]

    if not only_letters_regex(search_term):
        return None

    if search_term in COUNTRY_TO_LANGUAGE:
        return search_term

    exact_matches = search_geo_exact(search_term)
    if len(exact_matches) == 1:
        return exact_matches[0]["country"]["name"]

    for item in exact_matches:
        if citizenship and item["country"]["name"] == citizenship:
            return citizenship

    return None


def search_country_by_code(
    country_code: str,
    search_geo_func: Callable[[str, str], Optional[List[Dict[str, Any]]]],
) -> List[Dict[str, Any]]:
    """
    Поиск стран по коду через переданную функцию search_geo_func.
    Возвращает список результатов (может быть пустым).
    """
    results = search_geo_func(country_code, "countries") or []
    return results


def resolve_ambiguities(
    results: List[Dict[str, Any]],
    resident_country_id: Optional[int],
    nationality_country_id: Optional[int],
) -> Optional[Dict[str, Any]]:
    """
    Разрешает неоднозначности:
      - если одна страна, возвращает её;
      - если несколько, сначала ищет по resident_country_id,
        затем по nationality_country_id;
      - если ничего не выбрано, возвращает None.
    """
    if not results:
        return None

    if len(results) == 1:
        return results[0]

    chosen = next(
        (x for x in results if x.get("id") == resident_country_id),
        None,
    )

    if chosen is None:
        chosen = next(
            (x for x in results if x.get("id") == nationality_country_id),
            None,
        )

    if chosen is None:
        chosen = results[0]

    return chosen


def build_country_resolution_result(
    chosen: Optional[Dict[str, Any]],
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Строит итоговый словарь результата:
      - country_id
      - dial_code
      - is_ambiguous
      - matches
    """
    if not chosen:
        return {
            "country_id": None,
            "dial_code": None,
            "is_ambiguous": True,
            "matches": [],
        }

    is_ambiguous = len(results) != 1

    return {
        "country_id": chosen.get("id"),
        "dial_code": chosen.get("dial_code"),
        "is_ambiguous": is_ambiguous,
        "matches": results,
    }


def resolve_country_by_code(
    country_code: str,
    resident_country_id: Optional[int],
    nationality_country_id: Optional[int],
    search_geo_func: Callable[[str, str], Optional[List[Dict[str, Any]]]],
) -> Dict[str, Any]:
    """
    Фасад: поиск по коду + разрешение неоднозначностей + выбор приоритетного результата.
    """
    results = search_country_by_code(country_code, search_geo_func)
    chosen = resolve_ambiguities(results, resident_country_id, nationality_country_id)
    return build_country_resolution_result(chosen, results)