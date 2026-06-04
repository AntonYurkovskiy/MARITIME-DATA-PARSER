from src.utils.validators import clean_letters_commas


import re
from datetime import datetime


def get_birth_day_place(birth_day_place_string):
    if len(birth_day_place_string.split(' ',1))==2:
        day, place = birth_day_place_string.split(' ',1)
    return day, place


def extract_date_to_iso(text):
    """
    Ищет дату в строке, конвертирует в ISO (YYYY-MM-DD), возвращает кортеж:
    (iso_date или None, остальная_строка_без_даты)
    """
    if not text:                   # Проверяем на пустую строку
        return None         # Возвращаем None 

    cleaned = text.strip()         # Удаляем пробелы по краям

    # Паттерн для дат: DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY
    date_pattern = r'\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b'
                                   # \b - граница слова
                                   # (\d{1,2}) - день (группа 1)
                                   # [./-] - разделитель
                                   # (\d{1,2}) - месяц (группа 2)
                                   # (\d{4}) - год (группа 3)

    match = re.search(date_pattern, cleaned)
                                   # Ищем первую дату в строке

    if not match:                  # Если дата не найдена
        return None, clean_letters_commas(cleaned)       # Возвращаем None и всю строку

    day, month, year = match.groups()
                                   # Извлекаем день, месяц, год из групп

    try:                           # Пробуем создать дату
        # Парсим дату в формате DD.MM.YYYY
        date_obj = datetime(int(year), int(month), int(day))
                                   # int() преобразует строки в числа
                                   # datetime проверяет корректность (29.02 в невисокосный)

        iso_date = date_obj.strftime('%Y-%m-%d')
                                   # Конвертируем в ISO: YYYY-MM-DD

        # Удаляем найденную дату из строки
        start, end = match.span()  # Получаем позиции даты в строке
        remaining_text = cleaned[:start].strip() + ' ' + cleaned[end:].strip()
                                   # Обрезаем дату, склеиваем остаток
        remaining_text = ' '.join(remaining_text.split())
                                   # Нормализуем множественные пробелы

        return iso_date, remaining_text



                                   # Возвращаем ISO дату и остаток текста

    except ValueError:             # Если дата невалидна (32.13.2025)
        return None      # Возвращаем None и исходную строку