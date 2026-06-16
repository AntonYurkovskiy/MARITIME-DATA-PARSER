import re
from datetime import datetime
from typing import Optional, Tuple

from src.utils.validators import clean_letters_commas


def get_birth_day_place(birth_day_place_string: str) -> Tuple[str, str]:
    parts = birth_day_place_string.split(' ', 1)
    if len(parts) != 2:
        raise ValueError("Invalid birth_day_place_string format, expected 'DAY PLACE'")
    day, place = parts
    return day, place


def find_first_date(text: Optional[str]) -> Tuple[Optional[re.Match], Optional[str], Optional[str], Optional[str]]:
    """Ищет первую дату в строке и возвращает (match, day, month, year) или (None, None, None, None)."""
    if not text:
        return None, None, None, None

    cleaned = text.strip()

    date_pattern = r'\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b'
    match = re.search(date_pattern, cleaned)

    if not match:
        return None, None, None, None

    day, month, year = match.groups()
    return match, day, month, year


def format_date_iso(day: Optional[str], month: Optional[str], year: Optional[str]) -> Optional[str]:
    """Конвертирует строковые день/месяц/год в ISO YYYY-MM-DD или возвращает None, если дата невалидна."""
    if day is None or month is None or year is None:
        return None

    try:
        date_obj = datetime(int(year), int(month), int(day))
        return date_obj.strftime('%Y-%m-%d')
    except ValueError:
        return None


def remove_date_from_text(text: str, match: Optional[re.Match]) -> str:
    """Удаляет найденную дату из текста и чистит пробелы/знаки."""
    cleaned = text.strip()
    if not match:
        # даты нет — просто очищаем строку
        # return clean_letters_commas(cleaned)
        result = clean_letters_commas(cleaned)
        return result or ""

    start, end = match.span()
    remaining_text = cleaned[:start].strip() + ' ' + cleaned[end:].strip()
    # нормализуем пробелы
    remaining_text = ' '.join(remaining_text.split())
    # return clean_letters_commas(remaining_text)
    result = clean_letters_commas(remaining_text)
    return result or ""

def extract_date_to_iso(text: Optional[str]) -> Optional[Tuple[Optional[str], str]]:
    """
    Ищет дату в строке, конвертирует в ISO (YYYY-MM-DD).

    Возвращает:
      - None, если строки нет/пустая или дата есть, но невалидна;
      - (None, cleaned_text), если в непустой строке нет даты;
      - (iso_date, remaining_text), если найдена валидная дата.
    """
    # Пустая строка или None → None
    if text is None or text == "":
        return None

    match, day, month, year = find_first_date(text)

    # Непустая строка, но даты нет → (None, очищенный текст)
    # if not match:
    #     cleaned_rest = clean_letters_commas(text.strip())
    #     return None, cleaned_rest
    
    if not match:
        cleaned_rest_opt = clean_letters_commas(text.strip())
        # если clean_letters_commas вернула None (например, только пробелы),
        # делаем оставшийся текст пустой строкой
        cleaned_rest = cleaned_rest_opt or ""
        return None, cleaned_rest

    iso_date = format_date_iso(day, month, year)

    # Дата по паттерну есть, но невалидна → None
    if iso_date is None:
        return None

    remaining_text = remove_date_from_text(text, match)
    return iso_date, remaining_text