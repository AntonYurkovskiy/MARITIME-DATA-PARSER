import json
from typing import Any, Dict, Tuple, Optional
import requests
import logging

logger = logging.getLogger(__name__)

from src.api.client import _get_session
from src.api.dicts import _add_value_in_dict
from src.config import API_BASE_URL, API_TIMEOUT
from src.domain.builder import stringify_id_fields
from src.cache import get_cache, is_cache_enabled


def add_seafarer(main:dict[str, Any])-> dict[str, Any]:
    """Добавляет данные о моряке на 360Crew API"""
    session = _get_session()  

    url = f'{API_BASE_URL}/seafarers/'

    payload = stringify_id_fields(main)
    payload.pop("photo", None)

    response = session.post(url, json=payload)
    logger.debug("Response status: %s", response.status_code)
    logger.debug("Response text: %s", response.text)
    response.raise_for_status()
    return response.json()


def validate_photo_payload(photo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Проверяет, есть ли что грузить, и приводит photo к ожидаемому виду.

    Возвращает нормализованный dict или None, если фото нет.
    """
    if not photo or not photo.get("file_obj"):
        return None

    # Можно добавить простую нормализацию дефолтов
    if "filename" not in photo:
        photo["filename"] = "photo.jpg"
    if "mime_type" not in photo:
        photo["mime_type"] = "image/jpeg"

    return photo


def prepare_photo_upload_request(
    seafarer_uuid: str,
    photo: Dict[str, Any],
) -> Tuple[requests.PreparedRequest, requests.Session]:
    """Готовит multipart‑запрос для загрузки фото."""

    session = _get_session()
    url = f"{API_BASE_URL}/seafarers/{seafarer_uuid}/main"

    photo["file_obj"].seek(0)
    payload = {"data": json.dumps({"photo": {"fileRef": "A"}})}
    files = [
        (
            "A",
            (
                photo.get("filename", "photo.jpg"),
                photo["file_obj"],
                photo.get("mime_type", "image/jpeg"),
            ),
        )
    ]

    request_headers = {
        "Accept": "application/json",
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
    logger.debug(
        "upload_seafarer_photo prepared headers: %s", dict(prepared.headers)
    )

    return prepared, session


def send_photo_upload(
    prepared: requests.PreparedRequest,
    session: requests.Session,
) -> Dict[str, Any]:
    """Отправляет запрос с фото и обрабатывает ответ."""

    response = session.send(prepared, timeout=API_TIMEOUT)
    logger.debug("Response status: %s", response.status_code)
    logger.debug("Response text: %s", response.text)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        logger.error(
            "upload_seafarer_photo failed: %s %s",
            response.status_code,
            response.text,
        )
        raise

    return response.json()


def upload_seafarer_photo(seafarer_uuid: str, photo: Dict[str, Any]) -> Dict[str, Any]:
    """Загружает фото моряка отдельным запросом (фасад)."""
    normalized_photo = validate_photo_payload(photo)
    if normalized_photo is None:
        return {"status": "no photo"}

    prepared, session = prepare_photo_upload_request(seafarer_uuid, normalized_photo)
    return send_photo_upload(prepared, session)


def get_id(dictionary, value, dict_name: str):
    if value:
        # Try to get from cache first (unless cache disabled)
        if is_cache_enabled():
            cache = get_cache()
            cache_key = f"id:{dict_name}:{value.lower()}"
            cached_id = cache.get(cache_key)
            
            if cached_id is not None:
                logger.debug(f"✅ Cache hit for ID lookup: {value} in {dict_name}")
                return cached_id
        
        # Search in dictionary
        found_id = next(
            (item['id'] for item in dictionary if item['value'].lower() == value.lower()),
            None
        )
        
        if found_id is not None:
            # Cache the found ID (unless cache disabled)
            if is_cache_enabled():
                cache = get_cache()
                cache_key = f"id:{dict_name}:{value.lower()}"
                cache.set(cache_key, found_id)
                logger.debug(f"💾 Cached ID lookup: {value} -> {found_id} in {dict_name}")
            return found_id
        
        # Add new value and cache the result (unless cache disabled)
        new_id = _add_value_in_dict(value, dict_name)['inserted']['id']
        if is_cache_enabled():
            cache = get_cache()
            cache_key = f"id:{dict_name}:{value.lower()}"
            cache.set(cache_key, new_id)
            logger.debug(f"💾 Cached new ID: {value} -> {new_id} in {dict_name}")
        return new_id
    else:
        return None