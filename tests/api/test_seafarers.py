# tests/api/test_seafarers.py

import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO
import requests

MODULE_NAME = "src.api.seafarers"


@pytest.fixture
def mock_session():
    """Мокируем requests.Session"""
    session = MagicMock()
    session.post = MagicMock()
    session.send = MagicMock()
    session.prepare_request = MagicMock()
    return session


@pytest.fixture
def mock_get_session(mock_session):
    """Мокируем _get_session из api.client"""
    with patch(f"{MODULE_NAME}._get_session", return_value=mock_session):
        yield mock_session


@pytest.fixture
def mock_stringify_id_fields():
    """Мокируем stringify_id_fields"""
    with patch(f"{MODULE_NAME}.stringify_id_fields") as mock:
        mock.side_effect = lambda x: x  # По умолчанию возвращаем то же самое
        yield mock


@pytest.fixture
def mock_add_value_in_dict():
    """Мокируем _add_value_in_dict"""
    with patch(f"{MODULE_NAME}._add_value_in_dict") as mock:
        yield mock


@pytest.fixture
def mock_logger():
    """Мокируем логгер"""
    with patch(f"{MODULE_NAME}.logger") as mock:
        yield mock


class TestAddSeafarer:
    """Тесты для функции add_seafarer"""

    def test_add_seafarer_success(self, mock_get_session, mock_stringify_id_fields, mock_logger):
        """Успешное добавление моряка"""
        from src.api.seafarers import add_seafarer

        # Подготовка
        main_data = {
            "name": "John",
            "surname": "Doe",
            "rank_id": 1,
            "photo": {"filename": "photo.jpg"},
        }
        expected_response = {
            "id": "uuid-123",
            "name": "John",
            "surname": "Doe",
        }

        mock_stringify_id_fields.return_value = {
            "name": "John",
            "surname": "Doe",
            "rank_id": 1,
        }
        mock_get_session.post.return_value.json.return_value = expected_response
        mock_get_session.post.return_value.status_code = 200

        # Выполнение
        result = add_seafarer(main_data)

        # Проверки
        assert result == expected_response
        mock_stringify_id_fields.assert_called_once_with(main_data)
        mock_get_session.post.assert_called_once()
        call_args = mock_get_session.post.call_args
        assert "/seafarers/" in call_args[0][0]
        mock_get_session.post.return_value.raise_for_status.assert_called_once()

    def test_add_seafarer_removes_photo(self, mock_get_session, mock_stringify_id_fields):
        """Фото должно быть удалено из payload перед отправкой"""
        from src.api.seafarers import add_seafarer

        main_data = {
            "name": "John",
            "surname": "Doe",
            "photo": {"filename": "photo.jpg"},
        }
        expected_response = {"id": "uuid-123"}

        mock_stringify_id_fields.return_value = {
            "name": "John",
            "surname": "Doe",
            "photo": {"filename": "photo.jpg"},
        }
        mock_get_session.post.return_value.json.return_value = expected_response

        # Выполнение
        result = add_seafarer(main_data)

        # Проверяем, что payload не содержит photo
        call_args = mock_get_session.post.call_args
        payload = call_args[1]["json"]
        assert "photo" not in payload

    def test_add_seafarer_api_error(self, mock_get_session, mock_stringify_id_fields):
        """Обработка ошибки API"""
        from src.api.seafarers import add_seafarer

        main_data = {"name": "John"}
        mock_stringify_id_fields.return_value = {"name": "John"}
        mock_get_session.post.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError("400 Client Error")
        )

        # Выполнение и проверка
        with pytest.raises(requests.exceptions.HTTPError):
            add_seafarer(main_data)


class TestUploadSeafarerPhoto:
    """Тесты для функции upload_seafarer_photo"""

    def test_upload_photo_success(self, mock_get_session, mock_logger):
        """Успешная загрузка фото"""
        from src.api.seafarers import upload_seafarer_photo

        # Подготовка
        seafarer_uuid = "uuid-123"
        photo_file = BytesIO(b"fake image data")
        photo = {
            "file_obj": photo_file,
            "filename": "photo.jpg",
            "mime_type": "image/jpeg",
        }
        expected_response = {"status": "success", "id": "photo-uuid"}

        # Мокируем prepare_request и send
        prepared = MagicMock()
        prepared.headers = {}
        mock_get_session.prepare_request.return_value = prepared
        mock_get_session.send.return_value.json.return_value = expected_response
        mock_get_session.send.return_value.status_code = 200

        # Выполнение
        result = upload_seafarer_photo(seafarer_uuid, photo)

        # Проверки
        assert result == expected_response
        mock_get_session.send.assert_called_once()
        mock_get_session.send.return_value.raise_for_status.assert_called_once()

    def test_upload_photo_no_photo(self, mock_get_session):
        """Без фото возвращает статус "no photo" """
        from src.api.seafarers import upload_seafarer_photo

        seafarer_uuid = "uuid-123"

        # Выполнение - без file_obj
        result = upload_seafarer_photo(seafarer_uuid, None)
        assert result == {"status": "no photo"}

        result = upload_seafarer_photo(seafarer_uuid, {})
        assert result == {"status": "no photo"}

        result = upload_seafarer_photo(seafarer_uuid, {"file_obj": None})
        assert result == {"status": "no photo"}

        # Проверяем, что не было запросов
        mock_get_session.prepare_request.assert_not_called()

    def test_upload_photo_http_error(self, mock_get_session):
        """Обработка HTTP ошибок"""
        from src.api.seafarers import upload_seafarer_photo

        seafarer_uuid = "uuid-123"
        photo_file = BytesIO(b"fake image data")
        photo = {
            "file_obj": photo_file,
            "filename": "photo.jpg",
            "mime_type": "image/jpeg",
        }

        prepared = MagicMock()
        prepared.headers = {}
        mock_get_session.prepare_request.return_value = prepared
        mock_get_session.send.return_value.status_code = 500
        mock_get_session.send.return_value.text = "Internal Server Error"
        mock_get_session.send.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError("500 Server Error")
        )

        # Выполнение и проверка
        with pytest.raises(requests.exceptions.HTTPError):
            upload_seafarer_photo(seafarer_uuid, photo)

    def test_upload_photo_seek_position(self, mock_get_session):
        """Проверяем что seek(0) вызывается перед отправкой"""
        from src.api.seafarers import upload_seafarer_photo

        seafarer_uuid = "uuid-123"
        photo_file = MagicMock(spec=BytesIO)
        photo = {
            "file_obj": photo_file,
            "filename": "test.jpg",
            "mime_type": "image/jpeg",
        }

        prepared = MagicMock()
        prepared.headers = {}
        mock_get_session.prepare_request.return_value = prepared
        mock_get_session.send.return_value.json.return_value = {"status": "success"}

        # Выполнение
        upload_seafarer_photo(seafarer_uuid, photo)

        # Проверяем что seek(0) был вызван
        photo_file.seek.assert_called_once_with(0)

    def test_upload_photo_default_values(self, mock_get_session):
        """Проверяем использование значений по умолчанию для filename и mime_type"""
        from src.api.seafarers import upload_seafarer_photo

        seafarer_uuid = "uuid-123"
        photo_file = BytesIO(b"fake image data")
        photo = {"file_obj": photo_file}  # Без filename и mime_type

        prepared = MagicMock()
        prepared.headers = {}
        mock_get_session.prepare_request.return_value = prepared
        mock_get_session.send.return_value.json.return_value = {"status": "success"}

        # Выполнение
        with patch("src.api.seafarers.requests.Request") as mock_request_cls:
            upload_seafarer_photo(seafarer_uuid, photo)

            # Проверяем что Request был создан с правильными параметрами
            mock_request_cls.assert_called_once()
            call_kwargs = mock_request_cls.call_args[1]
            files = call_kwargs["files"]
            # Проверяем что используются значения по умолчанию
            assert files[0][1][0] == "photo.jpg"  # filename по умолчанию
            assert files[0][1][2] == "image/jpeg"  # mime_type по умолчанию


class TestGetId:
    """Тесты для функции get_id"""

    def test_get_id_found_in_dictionary(self):
        """ID найден в словаре"""
        from src.api.seafarers import get_id

        dictionary = [
            {"id": 1, "value": "Captain"},
            {"id": 2, "value": "First Officer"},
            {"id": 3, "value": "Second Officer"},
        ]

        result = get_id(dictionary, "Captain", "ranks")
        assert result == 1

    def test_get_id_found_case_insensitive(self):
        """Поиск регистронезависимый"""
        from src.api.seafarers import get_id

        dictionary = [
            {"id": 1, "value": "Captain"},
            {"id": 2, "value": "First Officer"},
        ]

        result = get_id(dictionary, "CAPTAIN", "ranks")
        assert result == 1

        result = get_id(dictionary, "captain", "ranks")
        assert result == 1

        result = get_id(dictionary, "FiRsT OFfiCeR", "ranks")
        assert result == 2

    def test_get_id_not_found_adds_new(self, mock_add_value_in_dict):
        """Если ID не найден, добавляем новое значение"""
        from src.api.seafarers import get_id

        dictionary = [
            {"id": 1, "value": "Captain"},
            {"id": 2, "value": "First Officer"},
        ]
        mock_add_value_in_dict.return_value = {
            "inserted": {"id": 5, "value": "Quartermaster"}
        }

        result = get_id(dictionary, "Quartermaster", "ranks")

        assert result == 5
        mock_add_value_in_dict.assert_called_once_with("Quartermaster", "ranks")

    def test_get_id_none_value(self):
        """Когда value = None возвращаем None"""
        from src.api.seafarers import get_id

        dictionary = [
            {"id": 1, "value": "Captain"},
            {"id": 2, "value": "First Officer"},
        ]

        result = get_id(dictionary, None, "ranks")
        assert result is None

    def test_get_id_empty_string_value(self):
        """Когда value = пустая строка возвращаем None"""
        from src.api.seafarers import get_id

        dictionary = [
            {"id": 1, "value": "Captain"},
            {"id": 2, "value": "First Officer"},
        ]

        result = get_id(dictionary, "", "ranks")
        assert result is None

    def test_get_id_empty_dictionary(self, mock_add_value_in_dict):
        """Если словарь пустой, добавляем новое значение"""
        from src.api.seafarers import get_id

        dictionary = []
        mock_add_value_in_dict.return_value = {"inserted": {"id": 1, "value": "Captain"}}

        result = get_id(dictionary, "Captain", "ranks")

        assert result == 1
        mock_add_value_in_dict.assert_called_once_with("Captain", "ranks")

    def test_get_id_value_not_in_dict_adds_new(self, mock_add_value_in_dict):
        """Если value не найдено в словаре, добавляем его"""
        from src.api.seafarers import get_id

        dictionary = [
            {"id": 1, "value": "Captain"},
            {"id": 2, "value": "First Officer"},
        ]
        mock_add_value_in_dict.return_value = {
            "inserted": {"id": 10, "value": "New Rank"}
        }

        result = get_id(dictionary, "New Rank", "ranks")

        assert result == 10
        mock_add_value_in_dict.assert_called_once_with("New Rank", "ranks")
