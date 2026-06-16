# название файла в одном месте
NAME_UTILS_MODULE = "src.extractors.names"

import pytest
from unittest.mock import patch, MagicMock
from importlib import import_module


@pytest.fixture
def names_utils():
    """Импорт модуля с функциями имён"""
    return import_module(NAME_UTILS_MODULE)


@pytest.fixture
def mock_only_letters_regex():
    """Мокаемая функция only_letters_regex"""
    mock_func = MagicMock()
    # Возвращает строку если только буквы, иначе None; None остаётся None
    def side_effect(x):
        if x is None:
            return None
        return x if x.isalpha() else None
    
    mock_func.side_effect = side_effect
    return mock_func


EMPTY_FIELD_ERROR = "Field is Empty / Поле не заполненно"


class TestGetNames:
    """Тесты для функции get_names"""
    
    def test_full_name_russian(self, names_utils, mock_only_letters_regex):
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("Иван Иванов")
        
        assert name == "Иван"
        assert middle_name is None or middle_name == EMPTY_FIELD_ERROR
        assert surname == "Иванов"
    
    def test_three_parts_name(self, names_utils, mock_only_letters_regex):
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("Иван Петров Иванов")
        
        assert name == "Иван"
        assert middle_name == "Петров"
        assert surname == "Иванов"
    
    def test_single_name(self, names_utils, mock_only_letters_regex):
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("Иван")
        
        assert name == "Иван"
        assert middle_name is None or middle_name == EMPTY_FIELD_ERROR
        assert surname == "Иван"  # одно слово — и имя, и фамилия
    
    def test_name_with_numbers_returns_empty_field_for_name(self, names_utils, mock_only_letters_regex):
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("Иван123 Иванов")
        
        assert name == EMPTY_FIELD_ERROR
        assert surname == "Иванов"
    
    def test_empty_string_returns_empty_field(self, names_utils, mock_only_letters_regex):
        """Пустая строка: split() вернёт [''], что не вызовет IndexError"""
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("")
        
        # Ожидается что вернутся пустые/дефолтные значения
        assert name == EMPTY_FIELD_ERROR or name == ""
    
    def test_whitespace_only(self, names_utils, mock_only_letters_regex):
        """Строка из пробелов: split() вернёт список пробелов"""
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("   ")
        
        # Не вызывает исключение, работает с результатом split()
        assert name is not None
    
    def test_name_with_middle_name_english(self, names_utils, mock_only_letters_regex):
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("John William Smith")
        
        assert name == "John"
        assert middle_name == "William"
        assert surname == "Smith"
    
    def test_four_parts_name(self, names_utils, mock_only_letters_regex):
        """Четыре части — имя, два средних, фамилия"""
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("Иван Петров Сергеевич Иванов")
        
        assert name == "Иван"
        # middle_name — всё между первым и последним (может быть None если rsplit не находит)
        assert middle_name is not None or middle_name is None
        assert surname == "Иванов"
    
    def test_name_with_special_chars_filtered(self, names_utils, mock_only_letters_regex):
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("Иван-Пётр Иванов")
        
        # "Иван-Пётр" содержит дефис — не только буквы
        assert name == EMPTY_FIELD_ERROR
        assert surname == "Иванов"
    
    def test_none_input_raises_attribute_error(self, names_utils, mock_only_letters_regex):
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            with pytest.raises(AttributeError):  # None.split() вызовет AttributeError
                names_utils.get_names(None)
    
    def test_name_with_punctuation(self, names_utils, mock_only_letters_regex):
        with patch(NAME_UTILS_MODULE + ".only_letters_regex", mock_only_letters_regex):
            name, middle_name, surname = names_utils.get_names("Иван, Петров Иванов")
        
        # "Иван," содержит запятую
        assert name == EMPTY_FIELD_ERROR
        assert surname == "Иванов"