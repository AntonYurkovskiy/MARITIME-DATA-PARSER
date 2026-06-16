# название файла в одном месте
DATE_UTILS_MODULE = "src.extractors.dates"

import pytest
from unittest.mock import patch, MagicMock
from importlib import import_module


@pytest.fixture
def date_utils():
    """Импорт модуля с функциями дат"""
    return import_module(DATE_UTILS_MODULE)


@pytest.fixture
def mock_clean_letters_commas():
    """Мокаемая функция clean_letters_commas"""
    mock_func = MagicMock()
    mock_func.side_effect = lambda x: x.strip() if x else x
    return mock_func


class TestGetBirthDayPlace:
    """Тесты для функции get_birth_day_place"""
    
    def test_valid_input(self, date_utils):
        day, place = date_utils.get_birth_day_place("15 января 1990 года Москва")
        assert day == "15"
        assert place == "января 1990 года Москва"
    
    def test_single_space_separator(self, date_utils):
        day, place = date_utils.get_birth_day_place("01 somewhere")
        assert day == "01"
        assert place == "somewhere"
    
    def test_no_space_raises_error(self, date_utils):
        # Если нет пробела, split вернет список из 1 элемента
        # Функция упадёт с UnboundLocalError
        with pytest.raises(Exception):  # UnboundLocalError
            date_utils.get_birth_day_place("nospace")
    
    def test_only_day_raises_error(self, date_utils):
        # Одиночный элемент без пробела
        with pytest.raises(Exception):  # UnboundLocalError
            date_utils.get_birth_day_place("25")


class TestExtractDateToIso:
    """Тесты для функции extract_date_to_iso"""
    
    def test_valid_date_dd_mm_yyyy(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("Родился 15.03.1990 в Москве")
        
        assert iso_date == "1990-03-15"
        assert "15.03.1990" not in remaining
        assert "Москве" in remaining
    
    def test_valid_date_with_slashes(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("Дата 25/12/2000")
        
        assert iso_date == "2000-12-25"
    
    def test_valid_date_with_dashes(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("Дата 01-06-2015")
        
        assert iso_date == "2015-06-01"
    
    def test_no_date_in_string(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas) as mock_func:
            mock_func.return_value = "просто текст без даты"
            iso_date, remaining = date_utils.extract_date_to_iso("просто текст без даты")
        
        assert iso_date is None
        assert "текст" in remaining
    
    def test_empty_string_returns_none(self, date_utils):
        # Функция возвращает None для пустой строки
        result = date_utils.extract_date_to_iso("")
        assert result is None
    
    def test_none_input_returns_none(self, date_utils):
        # Функция возвращает None для None
        result = date_utils.extract_date_to_iso(None)
        assert result is None
    
    def test_invalid_date_32_13_2025_returns_none(self, date_utils):
        # Функция возвращает None для невалидной даты
        result = date_utils.extract_date_to_iso("32.13.2025")
        assert result is None
    
    def test_invalid_date_29_02_non_leap_year_returns_none(self, date_utils):
        # Функция возвращает None для 29.02 в невисокосный год
        result = date_utils.extract_date_to_iso("29.02.2023")
        assert result is None
    
    def test_valid_date_29_02_leap_year(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("29.02.2024")
        
        assert iso_date == "2024-02-29"
        assert remaining is not None
    
    def test_multiple_dates_returns_first(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("15.03.1990 и 20.05.2000")
        
        assert iso_date == "1990-03-15"
        assert "20.05.2000" in remaining
    
    def test_whitespace_normalization(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("Текст   15.03.1990    еще текст")
        
        assert iso_date == "1990-03-15"
        assert "  " not in remaining
    
    def test_date_at_start_of_string(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("01.01.2020 год")
        
        assert iso_date == "2020-01-01"
        assert "год" in remaining
    
    def test_date_at_end_of_string(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("рожден 15.03.1990")
        
        assert iso_date == "1990-03-15"
    
    def test_day_without_leading_zero(self, date_utils, mock_clean_letters_commas):
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso("5.3.1990")
        
        assert iso_date == "1990-03-05"


class TestIntegration:
    """Интеграционные тесты для комбинирования функций"""
    
    def test_full_birth_date_extraction(self, date_utils, mock_clean_letters_commas):
        """Полный сценарий: извлечение даты из строки с местом рождения"""
        birth_string = "Родился 15.03.1990 в Москве, Россия"
        
        with patch(DATE_UTILS_MODULE + ".clean_letters_commas", mock_clean_letters_commas):
            iso_date, remaining = date_utils.extract_date_to_iso(birth_string)
        
        assert iso_date == "1990-03-15"
        assert "Москве" in remaining
        assert "Россия" in remaining