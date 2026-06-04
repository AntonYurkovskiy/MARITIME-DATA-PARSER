# название файла в одном месте
PHONE_UTILS_MODULE = "src.extractors.phones"

import pytest
from unittest.mock import Mock, patch, MagicMock
from importlib import import_module


@pytest.fixture
def phone_utils():
    """Импорт модуля с телефонами"""
    return import_module(PHONE_UTILS_MODULE)


@pytest.fixture
def mock_resolve_country_func():
    """Мокаемая функция resolve_country_by_code"""
    mock_func = MagicMock()
    mock_func.return_value = {
        "country_id": 1,
        "country_name": "Sweden",
        "country_code": "SE"
    }
    return mock_func


@pytest.fixture
def mock_search_geo():
    """Фикстура для мока search_geo_func"""
    mock_func = Mock()
    mock_func.return_value = {"id": 1, "name": "Sweden"}
    return mock_func


class TestNormalizePhone:
    """Тесты для функции normalize_phone"""
    
    def test_add_plus_if_starts_with_digit(self, phone_utils):
        assert phone_utils.normalize_phone("79991234567") == "+79991234567"
    
    def test_replace_00_with_plus(self, phone_utils):
        assert phone_utils.normalize_phone("0079991234567") == "+79991234567"
    
    def test_remove_non_digits_except_plus(self, phone_utils):
        assert phone_utils.normalize_phone("+7 (999) 123-45-67") == "+79991234567"
        assert phone_utils.normalize_phone("7-999-123-45-67") == "+79991234567"
    
    def test_empty_string(self, phone_utils):
        assert phone_utils.normalize_phone("") == ""
    
    def test_none_input(self, phone_utils):
        assert phone_utils.normalize_phone(None) == ""
    
    def test_whitespace_stripped(self, phone_utils):
        assert phone_utils.normalize_phone("  +79991234567  ") == "+79991234567"


class TestParsePhone:
    """Тесты для функции parse_phone"""
    
    def test_valid_phone_sweden(self, phone_utils, mock_resolve_country_func, mock_search_geo):
        with patch(PHONE_UTILS_MODULE + ".resolve_country_by_code", mock_resolve_country_func):
            result = phone_utils.parse_phone("+46701234567", 1, 1, mock_search_geo)
        
        assert result is not None
        assert result["dial_code"] == "+46"
        assert result["country_id"] == 1
        assert result["country_name"] == "Sweden"
        assert result["country_code"] == "SE"
    
    def test_invalid_phone_returns_none(self, phone_utils, mock_search_geo):
        result = phone_utils.parse_phone("not_a_phone", 1, 1, mock_search_geo)
        assert result is None
    
    def test_empty_phone_returns_none(self, phone_utils, mock_search_geo):
        result = phone_utils.parse_phone("", 1, 1, mock_search_geo)
        assert result is None
    
    def test_phone_without_plus_parsed_correctly(self, phone_utils, mock_resolve_country_func, mock_search_geo):
        with patch(PHONE_UTILS_MODULE + ".resolve_country_by_code", mock_resolve_country_func):
            result = phone_utils.parse_phone("46701234567", 1, 1, mock_search_geo)
        
        assert result["dial_code"] == "+46"
        assert result["country_code"] == "SE"
    
    def test_00_prefix_converted(self, phone_utils, mock_resolve_country_func, mock_search_geo):
        with patch(PHONE_UTILS_MODULE + ".resolve_country_by_code", mock_resolve_country_func):
            result = phone_utils.parse_phone("0046701234567", 1, 1, mock_search_geo)
        
        assert result["dial_code"] == "+46"
        assert result["country_code"] == "SE"


class TestGetPhones:
    """Тесты для функции get_phones"""
    
    def test_multiple_phones(self, phone_utils, mock_resolve_country_func, mock_search_geo):
        phones_str = "+46701234567 +79991234567"
        
        with patch(PHONE_UTILS_MODULE + ".resolve_country_by_code", mock_resolve_country_func):
            result = phone_utils.get_phones(phones_str, 1, 1, mock_search_geo)
        
        assert len(result) == 2
        assert all(item["type_id"] == 1 for item in result)
        assert all(item["comment"] == "comment" for item in result)
        assert all(item["uuid"] is None for item in result)
    
    def test_invalid_phones_skipped(self, phone_utils, mock_resolve_country_func, mock_search_geo):
        phones_str = "+46701234567 invalid +79991234567"
        
        with patch(PHONE_UTILS_MODULE + ".resolve_country_by_code", mock_resolve_country_func):
            result = phone_utils.get_phones(phones_str, 1, 1, mock_search_geo)
        
        # Только два валидных номера (invalid пропускается)
        assert len(result) == 2
    
    def test_empty_phones_string(self, phone_utils, mock_search_geo):
        result = phone_utils.get_phones("", 1, 1, mock_search_geo)
        assert result == []
    
    def test_phones_with_country_id_none_skipped(self, phone_utils, mock_search_geo):
        phones_str = "+46701234567"
        
        mock_func = MagicMock()
        mock_func.return_value = {"country_id": None}
        
        with patch(PHONE_UTILS_MODULE + ".resolve_country_by_code", mock_func):
            result = phone_utils.get_phones(phones_str, 1, 1, mock_search_geo)
        
        assert result == []
    
    def test_returns_correct_structure(self, phone_utils, mock_resolve_country_func, mock_search_geo):
        with patch(PHONE_UTILS_MODULE + ".resolve_country_by_code", mock_resolve_country_func):
            result = phone_utils.get_phones("+46701234567", 1, 1, mock_search_geo)
        
        assert len(result) == 1
        item = result[0]
        assert "uuid" in item
        assert "country_id" in item
        assert "number" in item
        assert "type_id" in item
        assert "comment" in item