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
    # data = login_response.json()
    # print("keys:", data.keys())
    # print("token:", data.get("access_token"))
    # print("session auth header:", session.headers.get("Authorization"))
    return session