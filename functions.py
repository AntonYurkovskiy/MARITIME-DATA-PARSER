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

def soup_extractor(soup,key):
    tables = soup.find_all('table')

    values = []
    result = []
    
    for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) > 0:
                        text = cells[0].get_text(strip=True)

                        if key in text:
                            if len(cells) > 1:
                                divs = cells[1].find_all('div')
                                if divs:
                                    for div in divs:
                                        dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ', div.get_text(strip=True))
                                        value = re.sub(r'\s+', ' ', dirty_value.strip())
                                        values.append(value)
                                    
                                else:
                                    dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ', cells[1].get_text(strip=True))
                                    value = re.sub(r'\s+', ' ', dirty_value.strip())
                                    values.append(value)
                                    
                            elif len(cells)==1:
                                value = cells[0].get_text(strip=True)
                                values.append(value)
                                
                                
                                
                            
    for value in values:
        if '/' in value:
            result.extend(value.split('/'))
        else:
            result.append(value)
            
    return result 

# УБРАТЬ
def from_biometrics(soup,key):
    tables = soup.find_all('table')
    
    for table in tables:
        title_row = table.find('tr',class_ ='cv-title')
        if title_row:
            table_title = title_row.text.strip()
            if table_title and table_title == 'Biometrics':
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    for cell in cells:
                        text = cell.get_text(strip=True)
                    
                        if key in text:
                            return text.split(':')[1]
#   УБРАТЬ                          
def from_add_info(soup,key):
    tables = soup.find_all('table')
    
    for table in tables:
        title_row = table.find('tr',class_ ='cv-title')
        if title_row:
            table_title = title_row.text.strip()
            if table_title and table_title == 'Additional info':
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    for cell in cells:
                        title_cell = cell.find('td',class_ ='col-title')
                        if title_cell:
                            text = title_cell.get_text(strip=True)

                            if key in text:

                                div = cells[cells.index(cell)+1]
                                dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ',div.get_text(strip=True))
                                value = re.sub(r'\s+', ' ', dirty_value).strip()
                                return value   
                        else:
                            return None
# УБРАТЬ
def soup_table_extractor2(soup, table_name, key):
    tables = soup.find_all('table')
    values = []
    result = []
    
    for table in tables:
        title_row = table.find('tr', class_='cv-title')
        if title_row and title_row.text.strip() == table_name:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) > 1:  # Минимум 2 ячейки
                    text = cells[0].get_text(strip=True)
                    
                    if key in text:
                        # Берем ВСЕ div из cells[1], не break после первого
                        divs = cells[1].find_all('div')
                        for div in divs:
                            dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ', 
                                               div.get_text(strip=True))
                            value = re.sub(r'\s+', ' ', dirty_value).strip()
                            if value:  # Только непустые
                                values.append(value)
                        break  # break ПОСЛЕ обработки строки (OK)
    
    # Разбиваем по / (из вашего кода)
    for value in values:
        if '/' in value:
            result.extend(value.split('/'))
        else:
            result.append(value)
    
    return result

# УБРАТЬ
def extract_text_by_key(soup, search_text):
    """парсер текста по клчевому слову"""
    
    # Полный текст → ищем паттерн "ключ: значение"
    full_text = soup.get_text()
    pattern = re.escape(search_text) + r'\s*[:\-]?\s*([^\n\r]+?)(?=\n|$)'
    match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
    
    if match:
        return re.sub(r'\s+', ' ', match.group(1)).strip()
    
    return None

# УБРАТЬ
def extract_under_cell(soup, search_text):
    """
    Универсальный парсер: ищет ключ И извлекает значение из следующей строки того же столбца.
    
    Args:
        soup: BeautifulSoup объект
        search_text: искомый текст ('Birthday / Place of birth:')
        
    Returns:
        Значение из следующей строки/ячейки или None
    """
    
    # МЕТОД 1: Таблицы (тот же столбец)
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for i, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            for j, cell in enumerate(cells):
                if search_text in cell.get_text(strip=True):
                    # Ищем значение в следующей строке ТОГО ЖЕ столбца
                    if i + 1 < len(rows):
                        next_row = rows[i + 1]
                        next_cells = next_row.find_all(['td', 'th'])
                        if j < len(next_cells):
                            value = next_cells[j].get_text(strip=True)
                            return re.sub(r'\s+', ' ', value).strip()
    
    # МЕТОД 2: Regex в полном тексте (если таблицы не сработали)
    full_text = soup.get_text()
    pattern = re.escape(search_text) + r'\s*[:\-]?\s*([^\n\r]+?)(?=\n|$)'
    match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
    
    if match:
        return re.sub(r'\s+', ' ', match.group(1)).strip()
    
    return None

# УБРАТЬ
def extract_text_by_key_multi(soup, search_text, max_lines=10):
    """
    Парсит многострочные значения с умной остановкой.
    
    Args:
        max_lines: максимум строк для значения (защита от жадности)
    """
    full_text = soup.get_text()
    
    # Захватывает до следующего заголовка ИЛИ пустой строки
    pattern = (
        re.escape(search_text) + 
        r'\s*[:\-]?\s*' + 
        r'([\s\S]*?)(?=' + 
        r'(?:\n\s*[A-Z][a-z][\w\s]*:\s*|\n{2,}|\Z))'
    )
    
    match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
    
    if match:
        value = match.group(1).strip()
        # Очищаем множественные пробелы/переносы
        return re.sub(r'\s+', ' ', value).strip()
    
    return None

# УБРАТЬ
def parse_cv_content(cell):
    """Извлекает ВСЕ значения из cv-content (многострочные)"""
    values = []
    
    # Все div внутри ячейки
    divs = cell.find_all('div', recursive=False)
    for div in divs:
        text = div.get_text(strip=True)
        if text:
            values.append(text)
    
    # Если div нет - берем весь текст
    if not values:
        text = cell.get_text(strip=True)
        if text:
            values = [re.sub(r'\s+', ' ', text).strip()]
    
    return values if len(values) > 1 else values[0] if values else None

# УБРАТЬ
def extract_by_cv_title(soup, title_key):
    """
    Ищет ячейку cv-title с ключом → возвращает значение из следующей cv-content
    
    Args:
        soup: BeautifulSoup
        title_key: 'Position applied for', 'Birthday', etc.
    
    Returns:
        str/list: значение из cv-content (поддержка многострочных)
    """
    # Ищем ВСЕ таблицы
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            
            # Ищем cv-title с нужным ключом
            for i, cell in enumerate(cells):
                if (cell.get('class') and 'cv-title' in cell.get('class') and 
                    title_key in cell.get_text(strip=True)):
                    
                    # Ищем cv-content в той же строке (следующая ячейка)
                    for j in range(i + 1, len(cells)):
                        content_cell = cells[j]
                        if content_cell.get('class') and 'cv-content' in content_cell.get('class'):
                            return parse_cv_content(content_cell)
    
    return None



# def general_parser(html_content,key):
#     value = None
#     tables = html_content.find_all('table')
#     for table in tables:
#                 rows = table.find_all('tr')
#                 for row in rows:
#                     cells = row.find_all('td')
#                     if len(cells) > 0:
#                         text = cells[0].get_text(strip=True)
                        
#                         if key in text and len(cells) > 1:
#                             dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ', cells[1].get_text(strip=True))
#                             value = re.sub(r'\s+', ' ', dirty_value.strip())
#                             break  # Найдено — выходим
#                 if value:  # Проверяем
#                     break
#     return value
    
# def general_parser_2(html_content, key):
#     value = None  # ✅ Инициализируем
#     tables = html_content.find_all('table')
#     for table in tables:
#         for row in table.find_all('tr'):
#             cells = row.find_all('td')
#             if len(cells) >= 2 and key in cells[0].get_text():
#                 dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ', cells[1].get_text(strip=True))
#                 value = re.sub(r'\s+', ' ', dirty_value.strip())
#                 break  # Найдено — выходим
#         if value:  # Проверяем
#             break
        
#     return value  # ✅ Всегда определена
    
    
    
# def get_dicts_list(is_static=False):
#     url = f'https://staffdev.crew-man.com/api/v1/admin/dicts?is_static={is_static}'
#     # url = domain + key
#     session = requests.Session()

#     headers = {'Content-Type': 'application/json',
#                'Authorization': f'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX3V1aWQiOiJiNWIyY2Y2My02N2FmLTQ0NDgtYTRmMy1hNzQ1YzJiMjQ4ZDkiLCJleHAiOjE3Njc1NDk5MjEsImlhdCI6MTc2NzQ2MzUyMSwianRpIjoiOTYwYmRjNmItMTZiNS00MzljLWFhNDUtMjc0ZWNmZjJiMGZiIiwidHlwZSI6ImFjY2VzcyJ9.-oQ-xiYXb1FAgCP43DhhM2IS-2-ynK_DF3-Pf5P7MW0'}

#     response = session.get(url, headers=headers)
#     response.raise_for_status()
#     data = response.json()
#     return data


# ПАРСЕР ФОТО  ОСНОВНОЙ
def get_photo_simple(soup):
    
    # is_placeholder = img.startswith('iVBORw0KGgoAAAANSUhEUgAAARgAAAEZCAY')
    
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
# ДОПИЛИТЬ

def personal_info_parser(soup):
    """Парсит все таблицы и создает с словарь Ключ : Значение 

    Args:
        soup (bs4.BeautifulSoup): html файл обработанный с помощью BeautifulSoup(html_content, 'html.parser')

    Returns:
        dict: Общий словарь по трем таблицам Main info, Biometrics, Additional info
    """
    # personal_info = {}
    
    all_sections = {}
    
    tables = soup.find_all('table')
    
    for table in tables:
        title_row = table.find('tr', class_='cv-title')
        if title_row:
            
            table_title = title_row.get_text(strip=True)
            
            # section_data = {}
        
            # Если найдены таблицы 'Main info','Additional info':
            if table_title in ['Main info','Additional info']:
                # if table_title == 'Main info':
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
                    
                    # *******
                    
                    # notes_key_cell = table.find('tr', class_='cv-title', string='Notes')
                    # notes_value_cell = notes_key_cell.find_next_sibling('tr') if ne
                    
                    # section_data[notes_key_cell.get_text(strip=True)] = notes_value_cell.get_text(strip=True) 
                    # *******
                    
                    all_sections[table_title] = section_data
                    
                    
                # else:
                #     # находим строки
                #     rows = table.find_all('tr')
                #     for row in rows:
                #         # в строках находим ячейки
                #         cells = row.find_all('td')
                #         # обращаемся по индексам и элементам
                #         for cell_idx, cell in enumerate(cells):
                #             # проверяем класс ячейки
                #             if cell.get('class') and 'col-title' in cell.get('class', []):
                #                 title_text = text_cleaning(cell.get_text(strip=True))
                #                 # dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ', 
                #                 #                        cell.get_text(strip=True))
                #                 # title_text = re.sub(r'\s+', ' ', dirty_value).strip()

                #                 # создаем пустой список для значений
                #                 values = []
                #                  # Берем следующую ячейку с данными
                #                 if cell_idx + 1 <= len(cells):
                #                     value_cell = cells[cell_idx + 1]

                #                     # если данные в ячейке внутри тега div
                #                     divs = value_cell.find_all('div')
                #                     if divs:
                #                         for div in divs:
                #                             # dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ',
                #                             #                      div.get_text(strip=True))
                #                             # value = re.sub(r'\s+', ' ', dirty_value.strip())
                #                             value = text_cleaning(div.get_text(strip=True))
                #                             values.append(value)
                #                     else:
                #                         # dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ', 
                #                         #                    value_cell.get_text(strip=True))
                #                         # value = re.sub(r'\s+', ' ', dirty_value).strip()
                #                         value = text_cleaning(value_cell.get_text(strip=True))
                #                         if value:
                #                             values.append(value)
                #                         else:
                #                             values.append(None)

                #                         section_data[title_text] = values
            
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
            
            # парсинг остальных таблиц
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

                all_sections[table_title] = section_data  # Список словарей напрямую!    
                
                
                
            
            # section_data = {
            #     table_title : section_data
                
            #     # "TABLE NAME": table_title,  # Название таблицы
            #     # "DATA": section_data  # Данные таблицы
            #     }
            # all_sections.update(section_data)
            
            
            # #   здесь код про парсинг остальных таблиц  
        
    
    
    return all_sections

# ИНКОРПОРИРОВАТЬ В ПАРСЕРЫ
def text_cleaning(raw_text):
    # dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]',
    #                      ' ',
    #                      raw_text)
    # text = re.sub(r'\s+', ' ', dirty_value.strip())
    text = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]+|\s+', ' ', raw_text.strip())
    return text

# ПАРСЕР ТЕКСТА ЗАМЕТОК
def parse_notes(soup):
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
                        
                        
                
            
            




# for cell_idx, cell in enumerate(cells):
#                         # проверяем класс ячейки
#                         if cell.get('class') and 'col-title' in cell.get('class', []):
#                             dirty_value = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\s]', ' ', 
#                                                    cell.get_text(strip=True))
#                             title_text = re.sub(r'\s+', ' ', dirty_value).strip()
                            
#                             # создаем пустой список для значений
#                             values = []
#                              # Берем следующую ячейку с данными
#                             if cell_idx + 1 < len(cells):
#                                 value_cell = cells[cell_idx + 1]
            # for title in table_titles:
            #     if title and title.get_text(strip=True) == 'Notes:':
            #         tds = title.find_all('td')
            #         notes = tds[1].get_text()
            #         return notes

# def parse_notes1(soup):
#     """Извлекает текст заметок из таблицы 'Additional info'"""
#     tables = soup.find_all('table')
    
#     for table in tables:
#         # Ищем таблицу "Additional info"
#         title_row = table.find('tr', class_='cv-title')
#         if title_row and title_row.get_text(strip=True) == 'Additional info':
            
#             # Ищем строку "Notes:" внутри этой таблицы
#             notes_row = table.find('tr', string=lambda text: text and 'Notes:' in text)
#             if notes_row:
#                 tds = notes_row.find_all('td')
#                 if len(tds) > 1:
#                     notes = tds[1].get_text(strip=True)  # Значение в соседней ячейке
#                     return notes.strip()
    
#     return None  # Не найдено
    
     
    









