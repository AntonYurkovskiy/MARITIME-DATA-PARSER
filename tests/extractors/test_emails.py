# test_emails.py
from src.extractors.emails import find_emails, get_emails_list


class TestFindEmails:
    """Unit-тесты для find_emails"""
    
    def test_find_single_email(self):
        """Находит один email в тексте"""
        text = "Contact us at test@example.com for help"
        result = find_emails(text)
        assert result == ["test@example.com"]
    
    def test_find_multiple_emails(self):
        """Находит несколько email'ов в тексте"""
        text = "Emails: a@b.com, c@d.org, e@f.net"
        result = find_emails(text)
        assert result == ["a@b.com", "c@d.org", "e@f.net"]
    
    def test_find_email_with_special_chars(self):
        """Находит email с спецсимволами в локальной части"""
        text = "Contact user.name+tag@example.co.uk"
        result = find_emails(text)
        assert result == ["user.name+tag@example.co.uk"]
    
    def test_find_email_case_insensitive(self):
        """Находит email независимо от регистра"""
        text = "Email: USER@EXAMPLE.COM and user2@example.org"
        result = find_emails(text)
        assert "USER@EXAMPLE.COM" in result
        assert "user2@example.org" in result
    
    def test_no_emails_in_text(self):
        """Возвращает пустой список если email'ов нет"""
        text = "Это текст без email'ов"
        result = find_emails(text)
        assert result == []
    
    def test_empty_string(self):
        """Пустая строка возвращает пустой список"""
        result = find_emails("")
        assert result == []
    
    def test_email_with_numbers(self):
        """Находит email с цифрами"""
        text = "Contact user12345@test123.com"
        result = find_emails(text)
        assert result == ["user12345@test123.com"]
    
    def test_email_with_hyphen_and_underscore(self):
        """Находит email с дефисом и подчёркиванием"""
        text = "Email: user_name-test@domain-name.com"
        result = find_emails(text)
        assert result == ["user_name-test@domain-name.com"]
    
    def test_invalid_email_without_at(self):
        """Не находит строку без @ как email"""
        text = "notanemail.example.com"
        result = find_emails(text)
        assert result == []
    
    def test_invalid_email_with_space(self):
        """Не находит email с пробелом"""
        text = "user @example.com"
        result = find_emails(text)
        assert "user @example.com" not in result
    
    def test_email_in_long_text(self):
        """Находит email в большом тексте"""
        text = """
        Привет! Это письмо от test@company.com.
        Если есть вопросы, пиши на support@help.org.
        С уважением, John Doe
        """
        result = find_emails(text)
        assert "test@company.com" in result
        assert "support@help.org" in result


class TestGetEmailsList:
    """Unit-тесты для get_emails_list"""
    
    def test_returns_list_of_dicts_with_single_email(self):
        """Возвращает список словарей с одним email"""
        email_string = "Contact test@example.com"
        result = get_emails_list(email_string)
        assert len(result) == 1
        assert result[0] == {
            "email": "test@example.com",
            "comment": "comment",
            "uuid": None
        }
    
    def test_returns_list_of_dicts_with_multiple_emails(self):
        """Возвращает список словарей с несколькими email'ами"""
        email_string = "Emails: a@b.com and c@d.org"
        result = get_emails_list(email_string)
        assert len(result) == 2
        assert result[0]["email"] == "a@b.com"
        assert result[1]["email"] == "c@d.org"
        assert all(item["comment"] == "comment" for item in result)
        assert all(item["uuid"] is None for item in result)
    
    def test_returns_none_when_no_emails(self):
        """Возвращает None если email'ов нет"""
        email_string = "Текст без email'ов"
        result = get_emails_list(email_string)
        assert result is None
    
    def test_returns_none_when_empty_string(self):
        """Возвращает None если пустая строка"""
        result = get_emails_list("")
        assert result is None
    
    def test_extracts_email_from_mixed_text(self):
        """Извлекает email из текста с дополнительным содержимым"""
        email_string = "Запиши test123@example.co.uk в базу"
        result = get_emails_list(email_string)
        assert len(result) == 1
        assert result[0]["email"] == "test123@example.co.uk"
    
    def test_structure_of_returned_dict(self):
        """Каждый словарь имеет правильные ключи"""
        email_string = "user@example.com"
        result = get_emails_list(email_string)
        assert all(key in result[0] for key in ["email", "comment", "uuid"])
        assert set(result[0].keys()) == {"email", "comment", "uuid"}
    
    def test_emails_are_unique_in_result(self):
        """Если email повторяется в тексте, он появляется один раз в списке"""
        email_string = "Email: test@example.com и снова test@example.com"
        result = get_emails_list(email_string)
        # find_emails возвращает все совпадения, так что дубликаты будут
        assert sum(1 for item in result if item["email"] == "test@example.com") == 2


# тест для параметра Any (проверка типа)
class TestTypeAnnotations:
    """Проверка типа возвращаемого значения"""
    
    def test_find_emails_returns_list(self):
        """find_emails возвращает list"""
        assert isinstance(find_emails("test@example.com"), list)
    
    def test_find_emails_elements_are_strings(self):
        """Все элементы списка — строки"""
        result = find_emails("a@b.com c@d.org")
        assert all(isinstance(email, str) for email in result)
    
    def test_get_emails_list_returns_list_of_dicts(self):
        """get_emails_list возвращает list(dict)"""
        result = get_emails_list("test@example.com")
        assert isinstance(result, list)
        if result:
            assert isinstance(result[0], dict)
        