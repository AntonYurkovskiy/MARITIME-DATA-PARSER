import pytest
from typing import Any, Optional

from src.extractors.emails import find_emails
from src.utils.validators import (
    _normalize,
    simple_cleaned_vessel_name,
    text_cleaning,
    only_letters_regex,
    clean_letters_commas,
    only_letters_digits_spaces,
    only_digits_spaces_plus_minus,
)


# ---------- _normalize ----------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("Hello", "hello"),
        ("  HELLO  ", "hello"),
        ("Hello World", "hello world"),
        ("Hello, World!", "hello world"),
        ("Hello!!!", "hello"),
        ("Hello  World", "hello world"),
        ("COUNTRY-NAME", "country name"),
        ("test123", "test123"),
        ("Test123!@#", "test123"),
    ],
)
def test_normalize(text: str, expected: str) -> None:
    assert _normalize(text) == expected


# ---------- simple_cleaned_vessel_name ----------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("mv test", "test"),
        ("Mv/test", "test"),  # заменяет только "Mv/" один раз в начале
        ("MV test", "MV test"),
        ("test mv", "test mv"),
        ("mv mv test", "mv test"),  # только первое "mv " заменяется
        ("", ""),
        ("  mv test", "  test"),
    ],
)
def test_simple_cleaned_vessel_name(raw: str, expected: str) -> None:
    assert simple_cleaned_vessel_name(raw) == expected


# ---------- text_cleaning ----------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("Hello World", "Hello World"),
        ("Hello  World", "Hello World"),
        ("Hello\tWorld", "Hello World"),
        ("Hello\nWorld", "Hello World"),
        ("Hello\x00World", "Hello World"),  # невидимый символ
        ("Тест 123", "Тест 123"),
        ("Тест\x00123", "Тест 123"),
    ],
)
def test_text_cleaning(raw: str, expected: str) -> None:
    result = text_cleaning(raw)
    assert result == expected


# ---------- only_letters_regex ----------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("Hello", "Hello"),
        ("Hello123", "Hello"),
        ("Hello, World!", "HelloWorld"),
        ("Тест123", "Тест"),
        ("Тест, 123!", "Тест"),
        ("abc123DEF", "abcDEF"),
    ],
)
def test_only_letters_regex(text: Optional[str], expected: Optional[str]) -> None:
    result = only_letters_regex(text)
    assert result == expected


# ---------- clean_letters_commas ----------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("Hello", "Hello"),
        ("Hello World", "Hello World"),
        ("Hello,World", "Hello, World"),
        ("Hello ,World", "Hello, World"),
        ("Hello,World,Test", "Hello, World, Test"),
        ("Hello  ,  World", "Hello, World"),
        ("Тест,123", "Тест,"),  # цифры удаляются
        ("Тест, , ,", "Тест, ,,"),  # лишние запятые остаются как буквы+запятые
        ("a,b,c", "a, b, c"),
    ],
)
def test_clean_letters_commas(text: Optional[str], expected: Optional[str]) -> None:
    result = clean_letters_commas(text)
    assert result == expected


# ---------- find_emails ----------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("no email", []),
        ("email: test@example.com", ["test@example.com"]),
        ("a@b.com and c@d.org", ["a@b.com", "c@d.org"]),
        ("test@example.com test@example.com", ["test@example.com", "test@example.com"]),
        ("USER@EXAMPLE.COM", ["USER@EXAMPLE.COM"]),
    ],
)
def test_find_emails(text: str, expected: list[str]) -> None:
    result = find_emails(text)
    assert result == expected


# ---------- only_letters_digits_spaces ----------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", False),
        (None, False),  # если функция вызывает not text, то None тоже False
        ("   ", False),
        ("Hello", True),
        ("Hello 123", True),
        ("Тест 123", True),
        ("Hello!", False),
        ("Hello,World", False),
        ("Hello\tWorld", True),  # \t не входит в \s? в regex \s включает табы
        ("a1б2В3", True),
    ],
)
def test_only_letters_digits_spaces(text: Optional[str], expected: bool) -> None:
    assert only_letters_digits_spaces(text) == expected


# ---------- only_digits_spaces_plus_minus ----------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", False),
        ("   ", True),
        ("123", True),
        ("123 456", True),
        ("+123 -456", True),
        ("+ -", True),
        ("123+", True),
        ("123-", True),
        ("Hello", False),
        ("Hello 123", False),
        ("12.3", False),  # точка не разрешена
        ("12+3-4", True),
    ],
)
def test_only_digits_spaces_plus_minus(text: str, expected: bool) -> None:
    assert only_digits_spaces_plus_minus(text) == expected
