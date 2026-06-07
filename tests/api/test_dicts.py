import pytest
from unittest.mock import MagicMock, patch
from importlib import import_module

MODULE_NAME = "src.api.dicts"  


@pytest.fixture
def dicts_module():
    return import_module(MODULE_NAME)


@pytest.fixture
def mock_logger():
    mock = MagicMock()
    with patch(f"{MODULE_NAME}.logger", mock):
        yield mock


@pytest.fixture
def mock_session():
    """
    Мокаем _get_session так, чтобы он возвращал один и тот же mock session.
    """
    session = MagicMock()
    with patch(f"{MODULE_NAME}._get_session", return_value=session):
        yield session


class TestCleanLanguages:
    def test_clean_languages_deletes_empty_and_returns_filtered(
        self, dicts_module, mock_session, mock_logger
    ):
        languages = [
            {"id": 1, "value": ""},                 # пустой -> удалить
            {"id": 2, "value": "   "},              # пустой (пробелы) -> удалить
            {"id": 3, "value": "English"},          # оставить
            {"id": 4, "value": "portuguesse"},      # оставить (особый кейс)
            {"id": 5, "value": "  Spanish  "},      # оставить
        ]

        result = dicts_module.clean_languages(languages)

        # Проверяем, что delete вызван только для id=1 и 2
        delete_calls = [call.args[0] for call in mock_session.delete.call_args_list]
        base_url = dicts_module.API_BASE_URL + "/admin/dicts/languages/"
        assert base_url + "1" in delete_calls
        assert base_url + "2" in delete_calls
        assert base_url + "3" not in delete_calls
        assert base_url + "4" not in delete_calls
        assert base_url + "5" not in delete_calls

        # Возвращённый список должен содержать только элементы с непустым value
        assert result == [
            {"id": 3, "value": "English"},
            {"id": 4, "value": "portuguesse"},
            {"id": 5, "value": "  Spanish  "},
        ]

    def test_clean_languages_delete_error_logged(
        self, dicts_module, mock_session, mock_logger
    ):
        languages = [
            {"id": 1, "value": ""},
        ]

        mock_session.delete.side_effect = Exception("network error")

        result = dicts_module.clean_languages(languages)

        assert result == []

        mock_logger.warning.assert_called()
        # call_args: (args, kwargs); args[0] — форматная строка
        warned_args, warned_kwargs = mock_logger.warning.call_args
        msg = warned_args[0]
        assert "Не удалось удалить ID" in msg


class TestAddValueInDict:
    def test_add_value_in_dict_success(self, dicts_module, mock_session):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": 10, "value": "English"}
        mock_session.post.return_value = mock_response

        result = dicts_module._add_value_in_dict("English", "languages")

        # Проверяем правильный URL и тело запроса
        url = f"{dicts_module.API_BASE_URL}/admin/dicts/languages"
        mock_session.post.assert_called_once_with(url, json={"value": "English"})
        mock_response.raise_for_status.assert_called_once()
        assert result == {"id": 10, "value": "English"}

    def test_add_value_in_dict_raises_on_error(self, dicts_module, mock_session):
        mock_response = MagicMock()
        def _raise():
            raise Exception("400 Bad Request")
        mock_response.raise_for_status = _raise
        mock_session.post.return_value = mock_response

        with pytest.raises(Exception, match="400 Bad Request"):
            dicts_module._add_value_in_dict("English", "languages")


class TestGetDict:
    def test_get_dict_success(self, dicts_module, mock_session, mock_logger):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"id": 1, "value": "English"}]
        mock_session.get.return_value = mock_response

        result = dicts_module.get_dict("languages")

        url = f"{dicts_module.API_BASE_URL}/dict/languages"
        mock_session.get.assert_called_once_with(url, timeout=(10, 30))
        mock_response.raise_for_status.assert_called_once()
        assert result == [{"id": 1, "value": "English"}]
        mock_logger.error.assert_not_called()

    def test_get_dict_logs_and_raises_on_error(
        self, dicts_module, mock_session, mock_logger
    ):
        def _raise():
            raise Exception("500 Server Error")

        mock_response = MagicMock()
        mock_response.raise_for_status = _raise
        mock_session.get.return_value = mock_response

        with pytest.raises(Exception, match="500 Server Error"):
            dicts_module.get_dict("languages")

        mock_logger.error.assert_called()
        error_args, error_kwargs = mock_logger.error.call_args
        msg = error_args[0]
        assert "Ошибка получения" in msg
        # Дополнительно можем проверить, что в аргументах есть key
        assert "languages" in error_args[1:]


class TestGetDictsList:
    def test_get_dicts_list_success(self, dicts_module, mock_session):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            {"name": "languages"},
            {"name": "countries"},
        ]
        mock_session.get.return_value = mock_response

        result = dicts_module.get_dicts_list(is_static=False)

        url = f"{dicts_module.API_BASE_URL}/admin/dicts?is_static=False"
        mock_session.get.assert_called_once_with(url)
        mock_response.raise_for_status.assert_called_once()
        assert result == [
            {"name": "languages"},
            {"name": "countries"},
        ]