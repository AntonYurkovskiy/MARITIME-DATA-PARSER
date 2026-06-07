import json

import requests

import logging
logger = logging.getLogger(__name__)

from src.api.client import _get_session
from src.api.dicts import _add_value_in_dict
from src.config import API_BASE_URL, API_TIMEOUT
from src.domain.builder import stringify_id_fields


def add_seafarer(main:dict[str, any])-> dict[str, any]:
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


def upload_seafarer_photo(seafarer_uuid: str, photo: dict[str, any]) -> dict[str, any]:
    """Загружает фото моряка отдельным запросом"""
    if not photo or not photo.get("file_obj"):
        return {"status": "no photo"}

    session = _get_session()  
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


def get_id(dictionary, value, dict_name: str):
    if value:
        found_id = next(
            (item['id'] for item in dictionary if item['value'].lower() == value.lower()),
            None
        )
        if found_id is not None:
            return found_id
        return _add_value_in_dict(value, dict_name)['inserted']['id']
    else:
        return None