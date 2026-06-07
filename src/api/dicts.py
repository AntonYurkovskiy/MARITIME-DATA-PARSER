import logging
from src.api.client import _get_session
from src.config import API_BASE_URL

logger = logging.getLogger(__name__)

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


def _add_value_in_dict(value: str, dict_name: str) -> dict:
    """Добавляет значение в словарь 360Crew API"""
    session = _get_session()  # Кэшированная сессия
    url = f'{API_BASE_URL}/admin/dicts/{dict_name}'

    response = session.post(url, json={"value": value})
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