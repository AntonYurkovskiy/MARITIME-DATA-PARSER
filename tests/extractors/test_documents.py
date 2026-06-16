# test_documents.py
from src.extractors.documents import get_personal_id_by_passport, get_ranks
from src.utils.validators import only_letters_digits_spaces

class TestGetPersonalIdByPassport:
    """Тесты для get_personal_id_by_passport"""
    
    def test_returns_international_passport_first(self):
        """Проверяет приоритет: International passport должен быть первым"""
        docs = [
            {'Title of document': 'National passport', 'No.': 'N123'},
            {'Title of document': 'International passport', 'No.': 'I456'},
        ]
        result, doc_type = get_personal_id_by_passport(docs)
        assert result == 'I456'
        assert doc_type == 'International passport'
    
    def test_returns_national_passport_when_no_international(self):
        """Возвращает National passport если нет International"""
        docs = [
            {'Title of document': 'National passport', 'No.': 'N123'},
        ]
        result, doc_type = get_personal_id_by_passport(docs)
        assert result == 'N123'
        assert doc_type == 'National passport'
    
    def test_returns_seaman_book_when_no_passports(self):
        """Возвращает Seaman's book если нет паспортов"""
        docs = [
            {'Title of document': "Seaman's book", 'No.': 'S789'},
        ]
        result, doc_type = get_personal_id_by_passport(docs)
        assert result == 'S789'
        assert doc_type == "Seaman's book"
    
    def test_returns_none_when_invalid_no(self):
        """Возвращает None если No. содержит недопустимые символы"""
        docs = [
            {'Title of document': 'International passport', 'No.': 'I-123'},
        ]
        result, doc_type = get_personal_id_by_passport(docs)
        assert result is None
        assert doc_type == 'International passport'
    
    def test_returns_no_documents_when_empty_list(self):
        """Возвращает None и 'No documents' при пустом списке"""
        result, doc_type = get_personal_id_by_passport([])
        assert result is None
        assert doc_type == 'No documents'
    
    def test_returns_no_documents_when_none(self):
        """Возвращает None и 'No documents' при None"""
        result, doc_type = get_personal_id_by_passport(None)
        assert result is None
        assert doc_type == 'No documents'
    
    def test_returns_no_documents_when_no_priority_docs(self):
        """Возвращает None и 'No documents' если нет документов приоритетного типа"""
        docs = [
            {'Title of document': 'Driver license', 'No.': 'D123'},
            {'Title of document': 'ID card', 'No.': 'I456'},
        ]
        result, doc_type = get_personal_id_by_passport(docs)
        assert result is None
        assert doc_type == 'No documents'
    
    def test_valid_no_with_letters_digits_spaces(self):
        """No. с буквами, цифрами и пробелами считается валидным"""
        docs = [
            {'Title of document': 'International passport', 'No.': 'A1 B2 C3'},
        ]
        result, doc_type = get_personal_id_by_passport(docs)
        assert result == 'A1 B2 C3'
        assert doc_type == 'International passport'
    
    def test_valid_no_with_only_digits(self):
        """No. только с цифрами считается валидным"""
        docs = [
            {'Title of document': 'International passport', 'No.': '12345678'},
        ]
        result, doc_type = get_personal_id_by_passport(docs)
        assert result == '12345678'
        assert doc_type == 'International passport'


class TestGetRanks:
    """Тесты для get_ranks"""
    
    def test_splits_ranks_by_slash(self):
        """Разделяет ранги по '/'"""
        ranks = ['Captain/Major', 'Sergeant']
        result = get_ranks(ranks)
        assert result == ['Captain', 'Major', 'Sergeant']
    
    def test_strips_whitespace(self):
        """Удаляет пробелы вокруг рангов"""
        ranks = [' Captain / Major ', ' Sergeant ']
        result = get_ranks(ranks)
        assert result == ['Captain', 'Major', 'Sergeant']
    
    def test_empty_list(self):
        """Пустой список возвращает пустой список"""
        result = get_ranks([])
        assert result == []
    
    def test_single_rank_no_slash(self):
        """Список с одним рангом без '/'"""
        ranks = ['Captain']
        result = get_ranks(ranks)
        assert result == ['Captain']
    
    def test_multiple_slashes(self):
        """Несколько '/' в одном ранге"""
        ranks = ['A/B/C', 'D']
        result = get_ranks(ranks)
        assert result == ['A', 'B', 'C', 'D']
    
    def test_empty_parts_after_split(self):
        """Пустые части после split не добавляются"""
        ranks = ['A//B', 'C']
        result = get_ranks(ranks)
        # Пустые строки после strip будут включены
        assert result == ['A', '', 'B', 'C']
    
    def test_only_whitespace_parts(self):
        """Части только с пробелами становятся пустыми строками"""
        ranks = ['A/   /B']
        result = get_ranks(ranks)
        assert result == ['A', '', 'B']


# Если нужно тестировать only_letters_digits_spaces отдельно:
class TestOnlyLettersDigitsSpaces:
    """Тесты для only_letters_digits_spaces"""
    
    def test_valid_letters_digits_spaces(self):
        assert only_letters_digits_spaces('A1 B2') is True
    
    def test_valid_only_digits(self):
        assert only_letters_digits_spaces('12345') is True
    
    def test_valid_only_letters(self):
        assert only_letters_digits_spaces('ABC') is True
    
    def test_invalid_special_chars(self):
        assert only_letters_digits_spaces('A-1') is False
        assert only_letters_digits_spaces('A_1') is False
        assert only_letters_digits_spaces('A.1') is False
    
    def test_empty_string(self):
        assert only_letters_digits_spaces('') is False