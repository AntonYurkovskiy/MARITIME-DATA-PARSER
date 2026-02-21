# Работа с сервером
import requests
from pprint import pprint
import json

# Распаковка и парсинг
import zipfile
import pandas as pd
import io
from bs4 import BeautifulSoup
from datetime import datetime


from urllib.parse import urljoin, urlparse
import os
import shutil
import base64
import re

# ПОЛУЧЕНИЕ СЛОВАРЯ ПО КЛЮЧУ
def get_dict(key):
     
    session = requests.Session()
    login_url = 'https://staffdev.360crewing.com/api/v1/auth/login'  
    login_data = {
        "email":"owner@staffdev.com",
        "password":"m6fDG4UeMT0q",
        "forced":True
    }

    headers = {
        'Content-Type':'application/json'
    }

    # Токен
    login_response = session.post(login_url, json=login_data, headers=headers)
    login_response.raise_for_status()
    token = login_response.json().get('access_token')
        
    domain = 'https://staffdev.360crewing.com/api/v1/dict/'
    url = domain + key
    

    headers = {'Content-Type': 'application/json',
               'Authorization': f'Bearer {token}'}

    response = session.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data

# СТАРАЯ
def get_id_raw(dictionary,key):
    id = next((item['id'] for item in dictionary if item['value'].lower() == key.lower()), None)
    return id

# НОВАЯ
def get_id(dictionary, key):
    id = next((item['id'] for item in dictionary if item['value'] == key), None)
    if id:
        return id
    
    # Добавляем новый
    # БЕЗ ОБРАЩЕНИЯ НА СЕРВЕР
    else:
            
        new_id = max((item['id'] for item in dictionary), default=0) + 1
        dictionary.append({'department': None, 'id': new_id, 'order': new_id, 'type': None, 'value': key})
        return new_id

# ИСПОЛЬЗОВАТЬ
def get_html_content(file_path):
    """
    возвращает объект bs4 для дальнейшего обращения разными парсерами
    
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, 'html.parser') 
    return soup


# ПАРСЕР ФОТО
def get_photo_simple(soup):
    """Парсит фото и проверят на наличие заглушки

    Args:
        soup (bs4.BeautifulSoup): html файл обработанный с помощью BeautifulSoup(html_content, 'html.parser')

    Returns:
        str: mime_type вид изображения (image/jpeg, image/png, ...)
        base64: img_data битовая строка
    """
      
    src = soup.find('td', class_ = 'cvAvatar').find('img').get('src')
    header, data64 = src.split(',', 1)
    mime_type = header.split(';')[0].split(':')[1]  # image/jpeg
    ext = mime_type.split('/')[1]
    
    if not data64.startswith('iVBORw0KGgoAAAANSUhEUgAAARgAAAEZCAY'):
        img_data = base64.b64decode(data64)
        return mime_type, img_data
    else:
        return None   



# ОСНОВНОЙ ПАРСЕР 
def main_parser(soup):
    """Парсит все таблицы (кроме Notes) и сохраняет данные в словарь 

    Args:
        soup (bs4.BeautifulSoup): html файл обработанный с помощью BeautifulSoup(html_content, 'html.parser')

    Returns:
        dict: Общий словарь по всем таблицам 
    """
    
    all_sections = {}
    
    tables = soup.find_all('table')
    
    for table in tables:
        title_row = table.find('tr', class_='cv-title')
        if title_row:
            
            table_title = title_row.get_text(strip=True)
            
            # Если найдены таблицы 'Main info','Additional info':
            if table_title in ['Main info','Additional info']:
               
                # находим все ключи
                keys = [
                        text_cleaning(td.get_text(strip=True))
                        for td
                        # таблицу  'Main info' находим по классу
                        in table.find_all('td', class_='col-title')
                        # in soup.find('table', class_='cv-body').find_all('td', class_='col-title')
                        ]
                # находим все значения
                values = [
                
                        [text_cleaning(div.get_text(strip=True)) for div in td.find_all('div')]
                        if td.find_all('div') else text_cleaning(td.get_text(strip=True))
                    for td
                    in table.find_all('td', class_='cv-content')
                    # in soup.find('table', class_='cv-body').find_all('td', class_='cv-content')
                    ]
                # пакуем в словарь
                section_data = dict(zip(keys,values))
                
                all_sections[table_title] = section_data
                    
            
            # парсинг таблицы Biometrics
            elif table_title == 'Biometrics':
                section_data = {}
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cells = row.find_all('td')
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if len(text.split(':'))>1:
                            section_data[text.split(':')[0]] = text.split(':')[1]
                        else:
                            section_data[text.split(':')[0]] = None
            
                all_sections[table_title] = section_data
            
            # парсинг остальных таблиц ДОКУМЕНТЫ И СТАЖ
            else:
                rows = table.find_all('tr')
                if len(rows) < 2:
                    all_sections[table_title] = None
                    continue
            
                # Заголовки ИЗ ПЕРВОЙ строки данных (rows[1])
                headers = [th.get_text(strip=True) for th in rows[1].find_all(['td', 'th'])]
                if not headers:
                    all_sections[table_title] = None
                    continue
            
                # Данные начиная со ВТОРОЙ строки данных (rows[2:])
                section_data = []
                for row in rows[2:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) == len(headers):
                        row_dict = dict(zip(headers, [text_cleaning(cell.get_text(strip=True)) for cell in cells]))
                        section_data.append(row_dict)

                all_sections[table_title] = section_data     
 
    return all_sections

# ОЧИСТКА ТЕКСТА
def text_cleaning(raw_text):
    """очищает текст от непечатаемых спец символов

    Args:
        raw_text (str): неочищенная строка

    Returns:
        str: очищенная строка
    """
    text = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]+|\s+', ' ', raw_text.strip())
    return text

# ПАРСЕР ТЕКСТА ЗАМЕТОК
def parse_notes(soup):
    """Парсит значение в поле Notes

    Args:
        soup (bs4.BeautifulSoup): .html файл или его часть перобразованный в bs.4

    Returns:
        str: текст из поля Notes
    """
    tables = soup.find_all('table')
    
    for table in tables:
        title_row = table.find('tr',class_ ='cv-title')
        if title_row and title_row.get_text(strip=True) == 'Additional info':
            
            rows = table.find_all('tr')
            
            for row_idx, row in enumerate(rows):
                if row.get('class') and 'cv-title' in row.get('class', []):
                    if row.get_text(strip=True) =='Notes':
                        if row_idx + 1 < len(rows):
                            value_row = rows[row_idx + 1]
                            return value_row.get_text(strip=True).replace('\n', ' ')
                        else:
                            return None


# ОБРАБОТКА ДАННЫХ

# вернуть только буквы
def only_letters_regex(text):
    result = re.sub(r'[^а-яА-ЯёЁa-zA-Z]', '', text) if text else None
    return result if result else None

# Разделить ФИО
def get_names(names_string):
    # предполагаем что первым идет имя
    name = only_letters_regex(names_string.split(' ')[0])
    # все что в середине здесь
    middle_name = only_letters_regex(names_string.split(' ',1)[1].rsplit(' ',1)[0] if len(names_string.split(' ')) > 2 else None)
    # фамилия в конце
    surname = only_letters_regex(names_string.split(' ')[-1]) 
    return name, middle_name, surname 
    

# Дата рождения и место рождения
def get_birth_day_place(birth_day_place_string):
    if len(birth_day_place_string.split(' ',1))==2:
        day, place = birth_day_place_string.split(' ',1)
    return day, place

# очередна очистка текста
def clean_letters_commas(text):    
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




def extract_date_to_iso(text):     # Главная функция: извлечь дату и вернуть ISO
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

# поиск всех емейлов
def find_emails(text):
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def get_emails_list(email_string):
    """Из строки с емейлами делает словарь по форме 
    {"email":"email", "comment":"comment", "uuid":"uuid"}

    Args:
        email_string (str): строка в которую должен входить email

    Returns:
        _type_: _description_
    """
    emails_list = []
    if find_emails(email_string):
        for email in find_emails(email_string):
            emails_list.append({"email":email, "comment":"comment", "uuid":None})
    else:
        return None
    return emails_list


