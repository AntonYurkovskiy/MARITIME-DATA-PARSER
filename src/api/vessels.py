import re
from typing import Any

from rapidfuzz import fuzz, utils

import logging
logger = logging.getLogger(__name__)
from src.api.client import _get_session
from src.api.geo import search_geo
from src.api.seafarers import get_id
from src.config import API_BASE_URL
from src.extractors.dates import extract_date_to_iso
from src.utils.mapping import get_value
from src.utils.validators import _normalize, simple_cleaned_vessel_name


def search_vessel(vessel_name:str, source:str, route: str):
    """Ищет данные о судне с названием vessel_name
    в базе данных с параметром source
    расположенной на сервере по ручке route

    Args:
        vessel_name (str): Название судна
        source (str): тип источника для параметра metadata
        route (str): ручка где на сервере расположена база данных

    Returns:
        dict: ответ сервера с результатами поискового запроса
    """
    session = _get_session()  # Кэшированная сессия

    url = f'{API_BASE_URL}/vessels'

    search_url = f"{url}{route}"

    payload = {
        "pagination":{"page":1,"per_page":25},
        "filters":
            {
                "combinator":"or",
                "rules":[
                    {"field":"details_history.name","operator":"contains","value":vessel_name},
                    {"field":"name","operator":"contains","value":vessel_name},
                    {"field":"imo_no","operator":"contains","value":vessel_name}
                    ]
                },
            "metadata":{"source":source}
            }

    response = session.post(search_url, json=payload)
    # print(response.status_code)
    response.raise_for_status()
    return response.json()




def _extract_items(result):
    if isinstance(result, dict):
        return result.get("items", []) or []
    if isinstance(result, list):
        return result
    return []


def _get_vessel_name(item):
    if not isinstance(item, dict):
        return ""

    details = item.get("details_history") or {}
    return (
        item.get("name")
        or details.get("name")
        or item.get("imo_no")
        or ""
    )


def _name_variants(vessel_name: str):
    parts = _normalize(vessel_name).split()

    variants = [vessel_name]

    if len(parts) >= 2:
        variants.append(parts[0])          # prince
        variants.append(parts[-1])         # bassel
        variants.append(" ".join(parts[:2]))   # prince bassel
        variants.append(" ".join(parts[-2:]))  # prince bassel

    seen = set()
    result = []
    for v in variants:
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            result.append(v)
    return result


def _best_fuzzy_item(query: str, items: list):
    best_item = None
    best_score = -1

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

        if score > best_score:
            best_score = score
            best_item = item

    return best_item, best_score


def find_exact_vessel_uuid(vessel_name: str, sources: list):
    """Поиск судна по точному совпадению полного имени.
    
    Args:
        vessel_name: Полное имя для поиска
        sources: Список кортежей (source, route)
    
    Returns:
        tuple: (best_item, best_source, best_score)
    """
    best_item = None
    best_source = None
    best_score = -1
    
    for source, route in sources:
        result = search_vessel(vessel_name, source, route)
        items = _extract_items(result)
        
        if items:
            # Ищем точное совпадение
            for item in items:
                candidate = _get_vessel_name(item)
                if not candidate:
                    continue
                
                if _normalize(candidate) == _normalize(vessel_name):
                    return item, source, 100  # Точное совпадение - макс балл
            
            # Если точного нет, ищем лучший fuzzy match в результатах
            item, score = _best_fuzzy_item(vessel_name, items)
            if item and score > best_score:
                best_item = item
                best_source = source
                best_score = score
    
    return best_item, best_source, best_score


def search_by_name_variants(vessel_name: str, sources: list, best_item, best_source, best_score):
    """Поиск судна по вариантам имени (первое слово, последнее, пары слов).
    
    Args:
        vessel_name: Полное имя для поиска вариантов
        sources: Список кортежей (source, route)
        best_item, best_source, best_score: Лучший результат из предыдущего поиска
    
    Returns:
        tuple: (best_item, best_source, best_score)
    """
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
                
                if score > best_score:
                    best_item = item
                    best_source = source
                    best_score = score
    
    return best_item, best_source, best_score


def get_vessel_uuid(vessel_name: str):
    """Ищет UUID судна: сначала exact match, затем fuzzy search по вариантам имени.
    
    Args:
        vessel_name: Название судна для поиска
    
    Returns:
        tuple: (uuid, source, item) или (None, None, None)
    """
    sources = [
        ("historical", "/historical/search"),
        ("main", "/search"),
        ("external", "/search"),
    ]
    
    # Phase 1: поиск по полному имени (exact + fuzzy)
    best_item, best_source, best_score = find_exact_vessel_uuid(vessel_name, sources)
    
    # Если найдено точное совпадение, возвращаем сразу
    if best_item and best_score >= 100:
        return best_item.get("uuid"), best_source, best_item
    
    # Phase 2: поиск по вариантам имени
    best_item, best_source, best_score = search_by_name_variants(
        vessel_name, sources, best_item, best_source, best_score
    )
    
    # Принимаем результат если score >= 80
    if best_item and best_score >= 80:
        return best_item.get("uuid"), best_source, best_item
    
    return None, None, None


def resolve_historical_vessel(cleaned_vessel_name: str, raw_vessel_name: str, local_vessel_types: dict):
    """Разрешает UUID исторического судна: поиск или создание.
    
    Returns:
        tuple: (vessel_uuid, source)
    """
    vessel_uuid = None
    source = 'historical'
    
    if cleaned_vessel_name:
        vessel_uuid, search_source, _ = get_vessel_uuid(cleaned_vessel_name)
        # Если найдено не-историческое судно, создаём историческое
        if search_source != 'historical':
            logger.debug(
                "Historical contract vessel lookup returned non-historical source=%s; creating historical vessel",
                search_source,
            )
            vessel_uuid = None
    
    if not vessel_uuid:
        # Создаём новое историческое судно
        created_vessel = _add_new_vessel(
            {'Vessel Name / Flag': raw_vessel_name, 'Vessel type / DWT': raw_vessel_name},
            local_vessel_types
        )
        vessel_uuid = (
            created_vessel.get('inserted', {}).get('uuid') 
            or created_vessel.get('uuid') 
            or created_vessel.get('id')
        )
    
    if not vessel_uuid:
        raise ValueError("Unable to resolve or create vessel UUID for historical contract")
    
    return vessel_uuid, source


def parse_contract_period(contract_period: str):
    """Парсит период контракта (From - Till) в две ISO даты.
    
    Returns:
        tuple: (sign_on_date, sign_off_date)
    """
    if not contract_period or not isinstance(contract_period, str):
        raise ValueError("Missing or invalid From - Till value: %r" % contract_period)

    period_parts = [
        part.strip() 
        for part in re.split(r'\s*[-–—]\s*', contract_period, maxsplit=1) 
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
    raw_vessel_name: str
):
    """Формирует payload для контракта.
    
    Returns:
        dict: готовый payload для API
    """
    if not raw_vessel_name:
        raise ValueError("Missing Vessel Name / Flag for historical contract entry")

    payload = {
        "is_historical": True,
        "seafarer_uuid": seafarer_uuid,
        "rank_id": rank_id,
        "vessel": {
            "uuid": vessel_uuid,
            "source": source
        },
        "is_automatic": True,
        "sign_on_date": sign_on_date,
        "sign_off_date": sign_off_date,
        "off_reason_id": 0,
        "is_historical": 1,
        "details": "Imported from CV"
    }
    
    return payload


def post_historical_contract(url: str, payload: dict):
    """Отправляет контракт на API и возвращает ответ.
    
    Returns:
        dict: ответ сервера
    """
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


def _add_new_vessel(contract_details:dict, local_vessel_types:dict):
    name_and_flag = contract_details.get('Vessel Name / Flag')
    if not name_and_flag:
        raise ValueError("Missing Vessel Name / Flag in historical contract entry")

    if ' / ' not in name_and_flag:
        raise ValueError("Unsupported Vessel Name / Flag format: %r" % name_and_flag)

    name = simple_cleaned_vessel_name(name_and_flag.rsplit(' / ',1)[0].strip()).upper()
    flag_country = name_and_flag.rsplit(' / ',1)[1].strip()

    flag_search = search_geo(flag_country)
    if flag_search:
        flag_country_id = flag_search[0]['id']
    else:
        mapped_flag = get_value(flag_country)
        if not mapped_flag:
            raise ValueError("Unable to resolve vessel flag country: %r" % flag_country)
        flag_search = search_geo(mapped_flag)
        flag_country_id = flag_search[0]['id'] if flag_search else None

    if flag_country_id is None:
        raise ValueError("Unable to resolve flag country id for: %r" % flag_country)

    vessel_type = contract_details.get('Vessel type / DWT')
    if not vessel_type or ' / ' not in vessel_type:
        raise ValueError("Missing or unsupported Vessel type / DWT format: %r" % vessel_type)

    type_id = get_id(local_vessel_types, vessel_type.rsplit(' / ',1)[0].strip(), 'vessel_types')
    if type_id is None:
        raise ValueError("Unable to resolve vessel type id for: %r" % vessel_type)

    session = _get_session()
    url = f'{API_BASE_URL}/vessels/historical'
    payload = {
        "name": name,
        "imo_no": 'No info',
        "type_id": type_id,
        "gt": 1,
        "flag_country_id": flag_country_id
    }

    response = session.post(url, json=payload)
    logger.debug("Response status: %s", response.status_code)
    logger.debug("Response text: %s", response.text)
    response.raise_for_status()
    return response.json()


# для одного запроса работает
def add_historical_contract(sea_service: dict, seafarer_uuid: str, ranks, local_vessel_types):
    """Добавляет данные о контракте на 360Crew API"""
    rank_id = get_id(ranks, sea_service.get('Position'), 'ranks')
    if not rank_id:
        raise ValueError("Missing rank_id for historical contract position: %s" % sea_service.get('Position'))

    raw_vessel_name = sea_service.get('Vessel Name / Flag')
    cleaned_vessel_name = simple_cleaned_vessel_name(raw_vessel_name) if raw_vessel_name else None

    # 1. Разрешить UUID судна
    vessel_uuid, source = resolve_historical_vessel(cleaned_vessel_name, raw_vessel_name, local_vessel_types)

    # 2. Парсить период контракта
    contract_period = sea_service.get('From - Till')
    sign_on_date, sign_off_date = parse_contract_period(contract_period)

    # 3. Построить payload
    url = f'{API_BASE_URL}/contracts/historical'
    payload = build_historical_contract_payload(
        seafarer_uuid, rank_id, vessel_uuid, source, 
        sign_on_date, sign_off_date, raw_vessel_name
    )

    # 4. Отправить контракт
    return post_historical_contract(url, payload)


def search_external_vessel(name_or_imo: str) -> list[dict[str, Any]]:
    if not name_or_imo:
        return None
    else:
        session = _get_session()

        url = f'{API_BASE_URL}/vessels/search'
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
        return data.get("items", [])