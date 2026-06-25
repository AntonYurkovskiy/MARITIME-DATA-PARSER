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


def parse_main_additional_section(table):
    title_row = table.find('tr', class_='cv-title')
    if not title_row:
        return None

    table_title = title_row.get_text(strip=True)
    if table_title not in ['Main info', 'Additional info']:
        return None

    keys = [
        text_cleaning(td.get_text(strip=True))
        for td in table.find_all('td', class_='col-title')
    ]

    values = [
        [text_cleaning(div.get_text(strip=True)) for div in td.find_all('div')]
        if td.find_all('div') else text_cleaning(td.get_text(strip=True))
        for td in table.find_all('td', class_='cv-content')
    ]

    return table_title, dict(zip(keys, values))


def parse_biometrics_section(table):
    title_row = table.find('tr', class_='cv-title')
    if not title_row:
        return None

    table_title = title_row.get_text(strip=True)
    if table_title != 'Biometrics':
        return None

    section_data = {}
    rows = table.find_all('tr')
    for row in rows[1:]:
        cells = row.find_all('td')
        for cell in cells:
            text = cell.get_text(strip=True)
            parts = text.split(':', 1)
            if len(parts) > 1:
                section_data[parts[0]] = parts[1]
            else:
                section_data[parts[0]] = None

    return table_title, section_data


def _extract_rank_from_tbody(tbody):
    """Извлекает значение Rank из первой строки tbody"""
    rows = tbody.find_all('tr')
    if rows and rows[0].find('td', class_='strong'):
        first_cell = rows[0].find('td', class_='strong')
        if first_cell and first_cell.get_text(strip=True) == 'Rank':
            rank_cell = rows[0].find('td', class_='cv-content')
            if rank_cell:
                return text_cleaning(rank_cell.get_text(strip=True))
    return None


def parse_generic_table_section(table):
    title_row = table.find('tr', class_='cv-title')
    if not title_row:
        return None

    table_title = title_row.get_text(strip=True)
    if table_title in ['Main info', 'Additional info', 'Biometrics']:
        return None

    rows = table.find_all('tr')
    if len(rows) < 2:
        return table_title, None

    headers = [th.get_text(strip=True) for th in rows[1].find_all(['td', 'th'])]
    if not headers:
        return table_title, None

    section_data = []
    
    # Специальная обработка для Diplomas с Rank в отдельных tbody
    if table_title == 'Diplomas':
        tbodies = table.find_all('tbody')
        for tbody in tbodies:
            if tbody.get('class') and 'diplomaRow' in tbody.get('class', []):
                rank = _extract_rank_from_tbody(tbody)
                rows_data = tbody.find_all('tr')[1:]  # Пропускаем первую строку с Rank
                
                for row in rows_data:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) == len(headers):
                        row_dict = dict(
                            zip(headers, [text_cleaning(cell.get_text(strip=True)) for cell in cells])
                        )
                        if rank:
                            row_dict['Rank'] = rank
                        section_data.append(row_dict)
    else:
        for row in rows[2:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) == len(headers):
                row_dict = dict(
                    zip(headers, [text_cleaning(cell.get_text(strip=True)) for cell in cells])
                )
                section_data.append(row_dict)

    return table_title, section_data


def _store_parsed_section(all_sections: dict, parsed_result):
    if parsed_result is not None:
        table_title, section_data = parsed_result
        all_sections[table_title] = section_data
        return True
    return False

# TODO:[refactor] нужна ли константа PARSERS 

PARSERS = (
    parse_main_additional_section,
    parse_biometrics_section,
    parse_generic_table_section,
)

def main_parser(soup):
    all_sections = {}
    tables = soup.find_all('table')

    for table in tables:
        for parser in PARSERS:
            if _store_parsed_section(all_sections, parser(table)):
                break  # как только один парсер сработал — переходим к следующей таблице

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


