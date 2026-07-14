import logging
from src.config import API_BASE_URL, API_TIMEOUT
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

# Retry statistics
_retry_stats = {
    "total_attempts": 0,
    "total_retries": 0,
    "total_retry_time": 0.0
}

# HTTP request counter
_http_stats = {
    "total_requests": 0,
    "start_time": None,
}

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

    # Wrap request method to track HTTP call count
    _original_request = session.request
    def _tracked_request(method, url, **kwargs):
        if _http_stats["start_time"] is None:
            _http_stats["start_time"] = time.perf_counter()
        _http_stats["total_requests"] += 1
        return _original_request(method, url, **kwargs)
    session.request = _tracked_request

    # Wrap send so every API call can recover once from an expired token.
    _original_send = session.send
    def _send_with_auth_refresh(request, **kwargs):
        response = _original_send(request, **kwargs)
        if response.status_code != 401 or _is_auth_login_request(request) or getattr(request, "_auth_retry", False):
            return response

        logger.warning("🔐 API returned 401 for %s %s; refreshing token and retrying once", request.method, request.url)
        response.close()
        setattr(request, "_auth_retry", True)
        login_and_set_auth_headers(session)
        if "Authorization" in session.headers:
            request.headers["Authorization"] = session.headers["Authorization"]
        if "Accept" in session.headers:
            request.headers["Accept"] = session.headers["Accept"]
        return _original_send(request, **kwargs)
    session.send = _send_with_auth_refresh

    # Custom retry strategy with tracking
    class RetryWithStats(Retry):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def increment(self, *args, **kwargs):
            _retry_stats["total_attempts"] += 1
            _retry_stats["total_retries"] += 1
            return super().increment(*args, **kwargs)

    retry_strategy = RetryWithStats(
        total=10,
        backoff_factor=1,
        status_forcelist=[429, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=2, pool_maxsize=2, pool_block=True)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _is_auth_login_request(request: requests.PreparedRequest) -> bool:
    """Return True for the login request itself to avoid recursive auth refresh."""
    return str(request.url or "").rstrip("/") == f"{API_BASE_URL.rstrip('/')}/auth/login"


def get_retry_stats() -> dict:
    """Get retry statistics."""
    return _retry_stats.copy()


def log_retry_stats():
    """Log retry and HTTP request statistics summary."""
    logger.info("=" * 70)
    logger.info("📊 HTTP REQUEST STATISTICS")
    logger.info("=" * 70)
    total_req = _http_stats["total_requests"]
    start = _http_stats["start_time"]
    if total_req > 0 and start is not None:
        elapsed = time.perf_counter() - start
        rps = total_req / elapsed if elapsed > 0 else 0
        logger.info(f"� Total HTTP requests: {total_req}")
        logger.info(f"⏱️  Elapsed time: {elapsed:.1f}s")
        logger.info(f"🚀 Average RPS: {rps:.2f} req/sec")
    else:
        logger.info("📊 No HTTP statistics available")
    if _retry_stats["total_retries"] > 0:
        logger.info(f"� Retries: {_retry_stats['total_retries']}")
    logger.info("=" * 70)


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
        try:
            login_response.raise_for_status()
            token = login_response.json().get("access_token")
        finally:
            login_response.close()
    except requests.exceptions.Timeout:
        logger.error("⏰ TIMEOUT: API не отвечает! Проверьте: интернет, VPN, firewall")
        raise
    except requests.exceptions.ConnectionError as e:
        logger.error("🌐 ConnectionError: %s", e)
        raise
    except Exception as e:
        logger.error("❌ Login failed: %s", e)
        raise

    assert_token_present(token)

    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Connection": "close",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })


def assert_token_present(token):
    """Проверяет наличие токена, выбрасывает ValueError при отсутствии."""
    if not token:
        raise ValueError("Нет access_token в ответе!")


