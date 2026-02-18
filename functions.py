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
    id = next((item['id'] for item in dictionary if item['value'] == key), None)
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
                            return value_row.get_text(strip=True)
                        else:
                            return None

    
     
    









