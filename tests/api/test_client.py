# tests/api/test_client.py

MODULE_NAME = "src.api.client"

import os
import pytest
from unittest.mock import MagicMock, patch
from importlib import import_module


@pytest.fixture(autouse=True)
def set_env():
    """Подставляем тестовые переменные окружения для логина."""
    with patch.dict(os.environ, {
        "CREWING_EMAIL": "test@example.com",
        "CREWING_PASSWORD": "secret_password",
    }, clear=False):
        yield


@pytest.fixture
def api_module():
    mod = import_module(MODULE_NAME)
    # очищаем кэш перед каждым тестом, чтобы _get_session заново логинилась
    mod._get_session.cache_clear()
    return mod


@pytest.fixture
def mock_logger():
    mock = MagicMock()
    with patch(f"{MODULE_NAME}.logger", mock):
        yield mock


@pytest.fixture
def mock_session_and_response():
    """
    Мокаем requests.Session и возвращаем (SessionCls, session, response).
    headers делаем обычным dict, чтобы .update() работал, как в реальности.
    """
    with patch(f"{MODULE_NAME}.requests.Session") as SessionCls:
        session = MagicMock()
        session.headers = {}
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"access_token": "test_token_123"}
        response.raise_for_status = MagicMock()

        session.post.return_value = response
        SessionCls.return_value = session

        yield SessionCls, session, response


class TestGetSession:
    def test_get_session_creates_session_with_auth(
        self, api_module, mock_logger, mock_session_and_response
    ):
        SessionCls, session_mock, response_mock = mock_session_and_response

        s = api_module._get_session()

        SessionCls.assert_called_once()
        session_mock.post.assert_called_once()

        assert s is session_mock
        assert s.headers["Authorization"] == "Bearer test_token_123"
        assert s.headers["Accept"] == "application/json"
        assert "User-Agent" in s.headers

    def test_get_session_uses_env_vars(
        self, api_module, mock_logger, mock_session_and_response
    ):
        SessionCls, session_mock, response_mock = mock_session_and_response

        api_module._get_session()

        kwargs = session_mock.post.call_args.kwargs
        assert kwargs["json"]["email"] == "test@example.com"
        assert kwargs["json"]["password"] == "secret_password"
        assert kwargs["json"]["forced"] is True
        assert kwargs["headers"] == {"Content-Type": "application/json"}
        assert kwargs["timeout"] == api_module.API_TIMEOUT

    def test_get_session_retry_strategy_mounted(
        self, api_module, mock_logger, mock_session_and_response
    ):
        SessionCls, session_mock, response_mock = mock_session_and_response

        api_module._get_session()

        # mount должен быть вызван для http и https
        assert session_mock.mount.call_count == 2
        called_urls = [c.args[0] for c in session_mock.mount.call_args_list]
        assert "http://" in called_urls
        assert "https://" in called_urls

    def test_get_session_no_token_raises_error(
        self, api_module, mock_logger
    ):
        with patch(f"{MODULE_NAME}.requests.Session") as SessionCls:
            session = MagicMock()
            session.headers = {}
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {}  # нет access_token
            response.raise_for_status = MagicMock()

            session.post.return_value = response
            SessionCls.return_value = session

            with pytest.raises(ValueError, match="Нет access_token"):
                api_module._get_session()

    def test_get_session_timeout_error(self, api_module, mock_logger):
        import requests

        with patch(f"{MODULE_NAME}.requests.Session") as SessionCls:
            session = MagicMock()
            session.headers = {}
            session.post.side_effect = requests.exceptions.Timeout()
            SessionCls.return_value = session

            with pytest.raises(requests.exceptions.Timeout):
                api_module._get_session()

            mock_logger.error.assert_called()
            # можно дополнительно проверить текст сообщения
            assert "TIMEOUT" in str(mock_logger.error.call_args)

    def test_get_session_connection_error(self, api_module, mock_logger):
        import requests

        with patch(f"{MODULE_NAME}.requests.Session") as SessionCls:
            session = MagicMock()
            session.headers = {}
            session.post.side_effect = requests.exceptions.ConnectionError(
                "Connection refused"
            )
            SessionCls.return_value = session

            with pytest.raises(requests.exceptions.ConnectionError):
                api_module._get_session()

            mock_logger.error.assert_called()
            assert "ConnectionError" in str(mock_logger.error.call_args)

    def test_lru_cache_caches_session(
        self, api_module, mock_logger, mock_session_and_response
    ):
        SessionCls, session_mock, response_mock = mock_session_and_response

        s1 = api_module._get_session()
        s2 = api_module._get_session()

        assert s1 is s2
        SessionCls.assert_called_once()  # Session создаётся только один раз

    def test_get_session_with_bad_status_code(
        self, api_module, mock_logger
    ):
        with patch(f"{MODULE_NAME}.requests.Session") as SessionCls:
            session = MagicMock()
            session.headers = {}
            response = MagicMock()
            response.status_code = 401
            response.json.return_value = {"error": "Unauthorized"}

            def raise_err():
                raise Exception("401 Client Error")

            response.raise_for_status = raise_err
            session.post.return_value = response
            SessionCls.return_value = session

            with pytest.raises(Exception):
                api_module._get_session()

            mock_logger.error.assert_called()