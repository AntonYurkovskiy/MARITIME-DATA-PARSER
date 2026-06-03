from bs4 import BeautifulSoup

from src.utils.validators import text_cleaning


def get_html_content(file_path):
    """
    возвращает объект bs4 для дальнейшего обращения разными парсерами

    """
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup


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


