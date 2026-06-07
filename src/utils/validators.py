import re
from typing import Optional

def _normalize(text: str) -> str:

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def simple_cleaned_vessel_name(raw_vessel_name):
    return raw_vessel_name.replace('mv ','',1).replace('Mv/','',1)


def text_cleaning(raw_text) -> str:
    """очищает текст от непечатаемых спец символов

    Args:
        raw_text (str): неочищенная строка

    Returns:
        str: очищенная строка
    """
    text = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]+|\s+', ' ', raw_text.strip())
    return text



def only_letters_regex(text) -> Optional[str]:
    result = re.sub(r'[^а-яА-ЯёЁa-zA-Z]', '', text) if text else None
    return result if result else None


def clean_letters_commas(text) -> Optional[str]:
    """
    Оставляет только буквы и запятые:
    - Удаляет пробелы после букв и перед запятыми
    - После запятых оставляет 1 пробел
    """
    # Проверка на пустую строку
    if not text:
        return None

    # Этап 1: Оставляем ТОЛЬКО буквы, запятые и пробелы
    text = re.sub(r'[^а-яА-ЯёЁa-zA-Z,\s]', '', text)

    # Этап 2: Удаляем пробелы перед запятыми (, )
    text = re.sub(r'\s+,', ',', text)

    # Этап 3: Удаляем пробелы после букв перед запятыми (буква ,)
    text = re.sub(r'([а-яА-ЯёЁa-zA-Z]),', r'\1,', text)

    # Этап 4: После запятых → 1 пробел (если нет пробела)
    text = re.sub(r',([^ ])', r', \1', text)

    # Этап 5: Удаляем множественные пробелы
    text = re.sub(r'\s+', ' ', text)

    # Этап 6: Удаляем пробелы в начале/конце
    result = text.strip()

    return result if result else None

# def find_emails(text) -> list[Any]:>>> .\src\extractors\emails.py

def only_letters_digits_spaces(text:str) -> bool:
    """Проверяет: только буквы, цифры, пробелы"""
    if not text:
        return False
    # ^ начало, $ конец, [] любой из символов
    pattern = r'^[а-яА-ЯёЁa-zA-Z0-9\s]+$'
    return bool(re.match(pattern, text.strip()))


def only_digits_spaces_plus_minus(text) -> bool:
    """Проверяет: только цифры, пробелы, плюсы, минусы"""
    if not text:                   # Пустая строка → False
        return False
    # ^ начало, $ конец, [] любой из символов
    pattern = r'^[0-9+\-\s]+$'
    return bool(re.match(pattern, text))#.strip()))