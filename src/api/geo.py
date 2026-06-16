# ПОИСК В ГЕОГРАФИЧЕСКИХ СЛОВАРЯХ
from typing import Any, Callable, Dict, List, Optional
import logging

from src.api.client import _get_session
from src.config import API_BASE_URL
from src.domain.languages import COUNTRY_TO_LANGUAGE
from src.utils.validators import only_letters_regex

logger = logging.getLogger(__name__)

def search_geo(search_term: str, geo_type: str = "countries") -> list:
    """Поиск в geo словарях"""
    if not search_term:
        return None
    else:
        # search_term = search_term.replace('ksa','Saudi Arabia').replace('uae','United Arab Emirates')
        session = _get_session()

        base_url = f'{API_BASE_URL}/dict'
        if geo_type in ['countries','cities','regions']:
            url = f'{base_url}/geo/{geo_type}/search/{search_term}'
        else:
            url = f'{base_url}/{geo_type}/search/{search_term}'

        payload = {
            "term": search_term,
            # "exact": True  # ← Точное совпадение!
        }
        logger.debug("🔍 GET %s", url)
        response = session.get(url,json=payload)

        logger.debug("Status: %s", response.status_code)
        if response.status_code == 200:
            data = response.json()
            logger.info("✅ Найдено: %s записей", len(data))
            return data
        else:
            logger.warning("❌ Ошибка поиска: %s", response.text)
            return []


def search_geo_exact(search_term: str, geo_type: str = 'cities') -> list[dict]:
    """Только ТОЧНЫЕ совпадения"""
    # Получаем все результаты поиска
    all_results = search_geo(search_term, geo_type)

    # Фильтруем ТОЛЬКО точные совпадения
    exact_matches = [
        item for item in all_results
        if item.get('name', '').strip().lower() == search_term.lower()
    ]

    return exact_matches


def search_geo_dict(geo_type: str = "countries") -> list:#search_term: str, geo_type: str = "countries") -> list:
    """Поиск в geo словарях"""
    if not geo_type:
        return None
    else:
        session = _get_session()

        base_url = f'{API_BASE_URL}/dict'
        if geo_type in ['countries','cities','regions']:
            url = f'{base_url}/geo/{geo_type}/search/'#{search_term}'
        else:
            url = f'{base_url}/{geo_type}/search/'#{search_term}'

        # payload = {
        #     "term": search_term,
        #     "exact": True  # ← Точное совпадение!
        # }
        # print(f"🔍 GET {url}")
        response = session.get(url)#, json=payload)  

        logger.debug("Status: %s", response.status_code)
        if response.status_code == 200:
            data = response.json()
            logger.debug("✅ Найдено: %s записей", len(data))
            return data
        else:
            logger.warning("❌ Ошибка поиска: %s", response.text)


def get_resident_country(search_term: str, citizenship: str):

    if search_term:
        if '/' in search_term:
            return search_term.split('/')[0]
        else:
            if only_letters_regex(search_term):
                if search_term in COUNTRY_TO_LANGUAGE:
                    return search_term
                else:
                    exact_matches = search_geo_exact(search_term)
                    if len(exact_matches)==1:
                        return exact_matches[0]['country']['name']
                    else:
                        for item in exact_matches:
                            if citizenship and item['country']['name'] == citizenship:
                                return citizenship
            else:
                return None

    else:
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

    # сначала ищем по resident_country_id
    chosen = next(
        (x for x in results if x.get("id") == resident_country_id),
        None,
    )

    # если не нашли, ищем по nationality_country_id
    if chosen is None:
        chosen = next(
            (x for x in results if x.get("id") == nationality_country_id),
            None,
        )

    # если всё ещё ничего, берём первый результат
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

    # неоднозначность снимается только если ровно один результат
    is_ambiguous = len(results) != 1

    return {
        "country_id": chosen.get("id"),
        "dial_code": chosen.get("dial_code"),
        "is_ambiguous": is_ambiguous,
        "matches": results,
    }


def resolve_country_by_code(
    country_code: str,
    resident_country_id,
    nationality_country_id,
    search_geo_func,
) -> Dict[str, Any]:
    """
    Фасад: поиск по коду + разрешение неоднозначностей + выбор приоритетного результата.
    """
    results = search_country_by_code(country_code, search_geo_func)
    chosen = resolve_ambiguities(results, resident_country_id, nationality_country_id)
    return build_country_resolution_result(chosen, results)

