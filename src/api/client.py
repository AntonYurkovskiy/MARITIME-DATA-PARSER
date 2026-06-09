import logging
from src.config import API_BASE_URL, API_TIMEOUT
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _get_session():
    """Единая авторизация для всех запросов"""
    session = create_session_with_retries()

    login_and_set_auth_headers(session)

    logger.info("✅ Авторизация успешна!")
    return session


def create_session_with_retries():
    """Создаёт requests.Session с настроенной стратегией retry."""
    session = requests.Session()

    retry_strategy = Retry(
        total=10,
        backoff_factor=1,  
        status_forcelist=[429, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def login_and_set_auth_headers(session):
    """Выполняет логин на API и устанавливает заголовки авторизации в сессии.

    Выбрасывает исключения при ошибках сети или при отсутствии токена.
    """
    login_data = {
        "email": os.getenv("CREWING_EMAIL"),
        "password": os.getenv("CREWING_PASSWORD"),
        "forced": True,
    }

    headers = {"Content-Type": "application/json"}

    try:
        login_response = session.post(
            f"{API_BASE_URL}/auth/login",
            json=login_data,
            headers=headers,
            timeout=API_TIMEOUT,
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

    token = login_response.json().get("access_token")
    assert_token_present(token)

    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })


def assert_token_present(token):
    """Проверяет наличие токена, выбрасывает ValueError при отсутствии."""
    if not token:
        raise ValueError("Нет access_token в ответе!")
    
    
    