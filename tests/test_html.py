from bs4 import BeautifulSoup
import pytest

from src.utils.validators import text_cleaning
from src.parsers.html import get_html_content
from src.parsers.html import parse_notes


def test_get_html_content_returns_soup(tmp_path):
    # создаём временный html-файл
    html = """
    <html>
      <head><title>Test page</title></head>
      <body>
        <h1>Hello</h1>
        <p class="msg">World</p>
      </body>
    </html>
    """
    file_path = tmp_path / "test.html"
    file_path.write_text(html, encoding="utf-8")

    soup = get_html_content(file_path)

    # проверяем тип
    assert isinstance(soup, BeautifulSoup)
    # проверяем, что содержимое распарсилось
    assert soup.title.string == "Test page"
    assert soup.find("h1").get_text(strip=True) == "Hello"
    assert soup.find("p", class_="msg").get_text(strip=True) == "World"


def test_get_html_content_raises_file_not_found(tmp_path):
    # путь к несуществующему файлу
    file_path = tmp_path / "no_such_file.html"

    # функция должна пробросить стандартную ошибку FileNotFoundError
    # (вы её не ловите в коде — значит, её поведение такое)
    import pytest

    with pytest.raises(FileNotFoundError):
        get_html_content(file_path)


def make_soup(html: str):
    return BeautifulSoup(html, "html.parser")


def test_parse_notes_found():
    html = """
    <html>
      <body>
        <table>
          <tr class="cv-title"><td>Other info</td></tr>
          <tr><td>Skip me</td></tr>
        </table>

        <table>
          <tr class="cv-title"><td>Additional info</td></tr>
          <tr class="cv-title"><td>Notes</td></tr>
          <tr><td>First line<br>Second line</td></tr>
        </table>
      </body>
    </html>
    """
    soup = make_soup(html)

    result = parse_notes(soup)

    assert result == "First lineSecond line"


def test_parse_notes_returns_none_when_no_additional_info():
    html = """
    <html>
      <body>
        <table>
          <tr class="cv-title"><td>Something else</td></tr>
          <tr class="cv-title"><td>Notes</td></tr>
          <tr><td>Value</td></tr>
        </table>
      </body>
    </html>
    """
    soup = make_soup(html)

    result = parse_notes(soup)

    assert result is None


def test_parse_notes_returns_none_when_no_notes_row():
    html = """
    <html>
      <body>
        <table>
          <tr class="cv-title"><td>Additional info</td></tr>
          <tr><td>No notes here</td></tr>
        </table>
      </body>
    </html>
    """
    soup = make_soup(html)

    result = parse_notes(soup)

    assert result is None


def test_parse_notes_returns_none_when_notes_has_no_value_row():
    html = """
    <html>
      <body>
        <table>
          <tr class="cv-title"><td>Additional info</td></tr>
          <tr class="cv-title"><td>Notes</td></tr>
        </table>
      </body>
    </html>
    """
    soup = make_soup(html)

    result = parse_notes(soup)

    assert result is None


def test_parse_notes_ignores_other_tables():
    html = """
    <html>
      <body>
        <table>
          <tr class="cv-title"><td>Additional info</td></tr>
          <tr class="cv-title"><td>Something else</td></tr>
          <tr><td>Wrong value</td></tr>
        </table>

        <table>
          <tr class="cv-title"><td>Additional info</td></tr>
          <tr class="cv-title"><td>Notes</td></tr>
          <tr><td>Correct value</td></tr>
        </table>
      </body>
    </html>
    """
    soup = make_soup(html)

    result = parse_notes(soup)

    assert result == "Correct value"
