import logging
from src.api.client import _get_session
from src.config import API_BASE_URL
from src.cache import get_cache, invalidate_cache, is_cache_enabled

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
    # Check if already cached to avoid duplicate additions (unless cache disabled)
    if is_cache_enabled():
        cache = get_cache()
        cache_key = f"added:{dict_name}:{value.lower()}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            logger.debug(f"✅ Cache hit for added value: {value} in {dict_name}")
            return cached_result
    
    session = _get_session()
    url = f'{API_BASE_URL}/admin/dicts/{dict_name}'

    response = session.post(url, json={"value": value})
    response.raise_for_status()
    result = response.json()
    
    # Cache the result to avoid duplicate additions
    if is_cache_enabled():
        cache = get_cache()
        cache_key = f"added:{dict_name}:{value.lower()}"
        cache.set(cache_key, result)
        logger.debug(f"💾 Cached added value: {value} in {dict_name}")
    
    return result

# ПОЛУЧЕНИЕ СЛОВАРЯ ПО КЛЮЧУ
def get_dict(key):
    # Try to get from persistent cache first (unless cache disabled)
    if is_cache_enabled():
        cache = get_cache()
        cache_key = f"dict:{key}"
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            logger.debug(f"✅ Cache hit for dict: {key}")
            return cached_result
    
    # Cache miss - fetch from API
    session = _get_session()
    domain = f'{API_BASE_URL}/dict/'
    url = domain + key

    try:
        response = session.get(url, timeout=(10, 30))
        response.raise_for_status()
        result = response.json()
        
        if is_cache_enabled():
            cache = get_cache()
            cache_key = f"dict:{key}"
            cache.set(cache_key, result)
            logger.debug(f"💾 Cached dict: {key}")
        
        return result
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