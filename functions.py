# =========================
# 0 IMPORTS
# =========================

# Работа с сервером
import requests
from pprint import pprint
import json

# Распаковка и парсинг
import zipfile
import pandas as pd


from urllib.parse import urljoin, urlparse
import os
import shutil
import re

from functools import lru_cache
from dotenv import load_dotenv

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from typing import Optional

from pathlib import Path

import difflib

import rapidfuzz
from rapidfuzz import fuzz, process, utils
from src.domain.builder import stringify_id_fields
from src.extractors.dates import extract_date_to_iso
from src.utils.mapping import get_value, load_mapping, set_value, update_mapping
from src.config import API_BASE_URL, API_TIMEOUT
import logging

from src.utils.validators import (
    _normalize,
    simple_cleaned_vessel_name,
    only_letters_regex)

load_dotenv()
logger = logging.getLogger(__name__)

# =========================
# 1 REQUESTS
# =========================

@lru_cache(maxsize=1)  
def _get_session():
    """Единая авторизация для всех запросов"""
    session = requests.Session()
    
    # ✅ Retry стратегия: 3 попытки с backoff
    retry_strategy = Retry(
        total=10,
        backoff_factor=1,  # 1s, 2s, 4s задержки
        status_forcelist=[429, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    login_data = {
        "email": os.getenv("CREWING_EMAIL"),
        "password": os.getenv("CREWING_PASSWORD"),
        "forced": True
    }
    
    headers = {'Content-Type': 'application/json'}
    
    # ✅ КРИТИЧНО: timeout + обработка ошибок!
    try:
        login_response = session.post(
            f'{API_BASE_URL}/auth/login', 
            json=login_data, 
            headers=headers,
            timeout=API_TIMEOUT  # 10s коннект, 30s ответ
        )
        login_response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("⏰ TIMEOUT: API не отвечает! Проверьте: интернет, VPN, firewall")
        raise
    except requests.exceptions.ConnectionError as e:
        logger.error("🌐 ConnectionError: %s", e)
        raise
    except Exception as e:
        logger.error("❌ Login failed: %s", e)
        raise
    
    # ✅ Заголовки сессии
    token = login_response.json().get("access_token")
    if not token:
        raise ValueError("Нет access_token в ответе!")
        
    session.headers.update({
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    logger.info("✅ Авторизация успешна!")
    # logger.debug("login status: %s", login_response.status_code)
    # logger.debug("login text: %s", login_response.text)
    data = login_response.json()
    # print("keys:", data.keys())
    # print("token:", data.get("access_token"))
    # print("session auth header:", session.headers.get("Authorization"))
    return session


def _add_value_in_dict(value: str, dict_name: str) -> dict:
    """Добавляет значение в словарь 360Crew API"""
    session = _get_session()  # Кэшированная сессия
    url = f'{API_BASE_URL}/admin/dicts/{dict_name}'
    
    response = session.post(url, json={"value": value})
    response.raise_for_status()
    return response.json()

# явное приведение к строковым данным всех id
# def stringify_id_fields(data: dict) -> dict:>>>> .\src\domain\builder.py

def add_seafarer(main:dict[str, any])-> dict[str, any]:
    """Добавляет данные о моряке на 360Crew API"""
    session = _get_session()  # Кэшированная сессия
    
    url = f'{API_BASE_URL}/seafarers/'
            
    payload = stringify_id_fields(main)
    payload.pop("photo", None)
    
    response = session.post(url, json=payload)
    logger.debug("Response status: %s", response.status_code)
    logger.debug("Response text: %s", response.text)
    response.raise_for_status()
    return response.json()

def upload_seafarer_photo(seafarer_uuid: str, photo: dict[str, any]) -> dict[str, any]:
    """Загружает фото моряка отдельным запросом"""
    if not photo or not photo.get("file_obj"):
        return {"status": "no photo"}
    
    session = _get_session()  # Кэшированная сессия с токеном
    url = f'{API_BASE_URL}/seafarers/{seafarer_uuid}/main'

    photo["file_obj"].seek(0)
    payload = {"data": json.dumps({"photo": {"fileRef": "A"}})}
    files = [
        (
            'A',
            (
                photo.get("filename", "photo.jpg"),
                photo["file_obj"],
                photo.get("mime_type", "image/jpeg")
            )
        )
    ]

    # multipart request must not reuse a JSON-only Content-Type header
    request_headers = {
        "Accept": "application/json"
    }

    logger.debug(
        "upload_seafarer_photo request: url=%s, filename=%s, mime_type=%s, payload=%s",
        url,
        photo.get("filename", "photo.jpg"),
        photo.get("mime_type", "image/jpeg"),
        payload,
    )

    request = requests.Request(
        "PUT",
        url,
        data=payload,
        files=files,
        headers=request_headers,
    )
    prepared = session.prepare_request(request)
    logger.debug("upload_seafarer_photo prepared headers: %s", dict(prepared.headers))

    response = session.send(prepared, timeout=API_TIMEOUT)
    logger.debug("Response status: %s", response.status_code)
    logger.debug("Response text: %s", response.text)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        logger.error("upload_seafarer_photo failed: %s %s", response.status_code, response.text)
        raise
    return response.json()
 
 
# ********************  
# ПОИСК СУДНА 
# И 
# ДОБАВЛЕНИЕ 
# vessel_uuid

# начало здесь
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
# def _normalize(text: str) -> str: ------>>>> .\srs\utils\validators.py  
  
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

def get_vessel_uuid(vessel_name: str):
    sources = [
        ("historical", "/historical/search"),
        ("main", "/search"),
        ("external", "/search"),
    ]

    best_item = None
    best_source = None
    best_score = -1

    # 1) Сначала пробуем полный запрос через contains
    for source, route in sources:
        result = search_vessel(vessel_name, source, route)
        items = _extract_items(result)

        if items:
            for item in items:
                candidate = _get_vessel_name(item)
                if not candidate:
                    continue

                if _normalize(candidate) == _normalize(vessel_name):
                    return item.get("uuid"), source, item

            item, score = _best_fuzzy_item(vessel_name, items)
            if item and score > best_score:
                best_item = item
                best_source = source
                best_score = score

    # 2) Если ничего не нашлось, пробуем части имени
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

    if best_item and best_score >= 80:
        return best_item.get("uuid"), best_source, best_item

    return None, None, None

# def simple_cleaned_vessel_name(raw_vessel_name): ------>>>> .\srs\utils\validators.py


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
def add_historical_contract(sea_service:dict, seafarer_uuid:str, ranks, local_vessel_types):
    """Добавляет данные о контракте на 360Crew API"""
    rank_id = get_id(ranks, sea_service.get('Position'), 'ranks')
    if not rank_id:
        raise ValueError("Missing rank_id for historical contract position: %s" % sea_service.get('Position'))

    raw_vessel_name = sea_service.get('Vessel Name / Flag')
    cleaned_vessel_name = simple_cleaned_vessel_name(raw_vessel_name) if raw_vessel_name else None

    if cleaned_vessel_name:
        vessel_uuid, source, _ = get_vessel_uuid(cleaned_vessel_name)
    else:
        vessel_uuid, source = None, 'historical'

    if source != 'historical':
        logger.debug(
            "Historical contract vessel lookup returned non-historical source=%s; creating historical vessel",
            source,
        )
        vessel_uuid = None
        source = 'historical'

    if not vessel_uuid:
        created_vessel = _add_new_vessel(sea_service, local_vessel_types)
        vessel_uuid = created_vessel.get('inserted', {}).get('uuid') or created_vessel.get('uuid') or created_vessel.get('id')
        source = source or 'historical'

    if not vessel_uuid:
        raise ValueError("Unable to resolve or create vessel UUID for historical contract")

    contract_period = sea_service.get('From - Till')
    if not contract_period or not isinstance(contract_period, str):
        raise ValueError("Missing or invalid From - Till value: %r" % contract_period)

    period_parts = [part.strip() for part in re.split(r'\s*[-–—]\s*', contract_period, maxsplit=1) if part.strip()]
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

    if not raw_vessel_name:
        raise ValueError("Missing Vessel Name / Flag for historical contract entry")

    session = _get_session()
    url = f'{API_BASE_URL}/contracts/historical'

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

# ПОЛУЧЕНИЕ СЛОВАРЯ ПО КЛЮЧУ

# @lru_cache(maxsize=128) 
def get_dict(key):
    session = _get_session()  # Кэшированная сессия
    domain = f'{API_BASE_URL}/dict/'
    url = domain + key
    
    try:
        response = session.get(url, timeout=(10, 30))
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("❌ Ошибка получения %s: %s", key, e)
        raise


# ПОЛУЧЕНИЕ ВСЕХ СЛОВАРЕЙ
def get_dicts_list(is_static=False):
    
    session = _get_session() 
    
    url = f'{API_BASE_URL}/admin/dicts?is_static={is_static}'
    
    response = session.get(url)
    response.raise_for_status()
    data = response.json()
    return data

# ПОИСК В ГЕОГРАФИЧЕСКИХ СЛОВАРЯХ
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

    

from typing import Any

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



def get_id(dictionary, value, dict_name: str):
    if value:
        found_id = next(
            (item['id'] for item in dictionary if item['value'].lower() == value.lower()),
            None
        )
        if found_id is not None:
            return found_id
        # dict_name — строка, например "languages"
        return _add_value_in_dict(value, dict_name)['inserted']['id']
    else:
        return None


    

# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОЧИСТКИ ЗНАЧЕНИЙ В СЛОВАРЕ НА СЕРВЕРЕ
def clean_languages(languages_list: list[dict]) -> list[dict]:
    """Очищает пустые + удаляет через API"""
    session = _get_session()
    
    # 1. Собираем ID пустых для удаления
    empty_ids = [
        item['id'] for item in languages_list 
        if not item.get('value', '').strip()
        and item.get('value', '').lower() != 'portuguesse'
    ]
    
    # 2. Удаляем через API (если нужно)
    for empty_id in empty_ids:
        delete_url = f'{API_BASE_URL}/admin/dicts/languages/{empty_id}'
        try:
            session.delete(delete_url)
            logger.info("🗑️ Удалён ID: %s", empty_id)
        except Exception as e:
            logger.warning("Не удалось удалить ID %s: %s", empty_id, e)
    
    # 3. Фильтруем локально
    return [
        item for item in languages_list 
        if item.get('value', '').strip()
    ]

# =========================
# 2 PARSERS
# =========================


# ЧТЕНИЕ HTML ФАЙЛА
# def get_html_content(file_path):>>>> .\srs\parsers\html.py

# ПАРСЕР ФОТО
# def get_photo_simple(soup):>>>> .\srs\parsers\photo.py

# ПАРСЕР ФОТО    
# def get_photo(soup, save_dir="out_manual", filename="photo.jpg"): >>>> .\srs\parsers\photo.py
    
# ОЧИСТКА ТЕКСТА
# def text_cleaning(raw_text): >>>> .\srs\utils\validators.py

# ОСНОВНОЙ ПАРСЕР 
# def main_parser(soup):>>>> .\srs\parsers\html.py

# ПАРСЕР ТЕКСТА ЗАМЕТОК
# def parse_notes(soup):>>>> .\srs\parsers\html.py

# =========================
# 3 DATA HANDLING
# =========================

# вернуть только буквы
# def only_letters_regex(text):>>>> .\src\utils\validators.py


# Разделить ФИО
# def get_names(names_string):>>>> .\src\extractors\names.py

# Дата рождения и место рождения
# def get_birth_day_place(birth_day_place_string):>>>> .\src\extractors\dates.py

# очистка текста
# def clean_letters_commas(text):>>>> .\srs\utils\validators.py

# Главная функция: извлечь дату и вернуть ISO
# def extract_date_to_iso(text):>>>> .\src\extractors\dates.py

# ****************************************
# поиск всех емейлов
# def find_emails(text):>>>> .\srs\utils\validators.py


# def get_emails_list(email_string):>>>> .\src\extractors\emails.py
# ****************************************

# ПОЛУЧЕНИЕ СТРАНЫ ПРОЖИВАНИЯ

# COUNTRY_TO_LANGUAGE  = Path(__file__).parent / 'data' / 'country_to_language.json'
# with open(COUNTRY_TO_LANGUAGE, 'r') as f:
#     COUNTRY_TO_LANGUAGE = json.load(f)

COUNTRY_TO_LANGUAGE = load_mapping((Path(__file__).parent / 'data' / 'country_to_language.json'))

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
    
# ****************************************
# ПОЛУЧЕНИЕ СЛОВАРЕЙ ТЕЛЕФОНОВ
# def normalize_phone(raw: str) -> str:>>>> .\src\extractors\phones.py

def resolve_country_by_code(country_code: str, resident_country_id, nationality_country_id, search_geo_func):
    results = search_geo_func(country_code, "countries") or []

    if len(results) == 1:
        item = results[0]
        return {
            "country_id": item.get("id"),
            "dial_code": item.get("dial_code"),
            "is_ambiguous": False,
            "matches": results,
        }

    chosen = next(
        (x for x in results if x.get("id") == resident_country_id),
        None
    ) or next(
        (x for x in results if x.get("id") == nationality_country_id),
        None
    ) or (results[0] if results else None)

    if not chosen:
        return {
            "country_id": None,
            "dial_code": None,
            "is_ambiguous": True,
            "matches": [],
        }

    return {
        "country_id": chosen.get("id"),
        "dial_code": chosen.get("dial_code"),
        "is_ambiguous": True,
        "matches": results,
    }


# def parse_phone(raw_phone: str, resident_country_id, nationality_country_id, search_geo_func):>>>> .\src\extractors\phones.py

# def get_phones(phones: str, resident_country_id, nationality_country_id, search_geo_func) -> list[dict]:>>>> .\src\extractors\phones.py

# ****************************************
# def only_letters_digits_spaces(text:str) -> bool:>>>> .\srs\utils\validators.py

# def only_digits_spaces_plus_minus(text):>>>> .\srs\utils\validators.py

# def get_personal_id_by_passport(pasports_list_of_dicts):>>>> .\src\extractors\documents.py

# def get_ranks(ranks):>>>> .\src\extractors\documents.py
                              
def get_languages(languages):
    lang_list = re.split(r', |/', languages)
    return [part.split(' ',1)[0] if ' ' in part else part for part in lang_list]

# def country_to_language(country: str) -> Optional[str]:>>>> .\src\domain\languages.py

# def build_seafarer_dict(..>>>> .\src\domain\builder.py

