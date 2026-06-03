# tests/test_get_photo.py
import base64
from pathlib import Path

from bs4 import BeautifulSoup
from src.parsers.photo import get_photo  


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_get_photo_success(tmp_path):
    # простое PNG‑изображение 1x1 (валидная base64‑строка)
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"dummy"
    data64 = base64.b64encode(png_bytes).decode("ascii")
    src = f"data:image/png;base64,{data64}"

    html = f"""
    <html>
      <body>
        <table>
          <tr>
            <td class="cvAvatar">
              <img src="{src}">
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    soup = make_soup(html)

    result = get_photo(soup, save_dir=tmp_path, filename="photo.jpg")

    assert isinstance(result, dict)
    assert result["mime_type"] == "image/png"
    # file_obj содержит те же байты
    assert result["file_obj"].read() == png_bytes
    # имя файла с корректным расширением
    assert Path(result["filename"]).suffix == ".png"


def test_get_photo_no_avatar_td():
    html = """
    <html>
      <body>
        <table>
          <tr>
            <td class="otherClass">
              <img src="data:image/png;base64,AAAA">
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    soup = make_soup(html)

    assert get_photo(soup) is None


def test_get_photo_no_img_inside_td():
    html = """
    <html>
      <body>
        <table>
          <tr>
            <td class="cvAvatar">
              No image here
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    soup = make_soup(html)

    assert get_photo(soup) is None


def test_get_photo_src_missing_or_invalid():
    html_no_src = """
    <html><body>
      <td class="cvAvatar"><img></td>
    </body></html>
    """
    soup_no_src = make_soup(html_no_src)
    assert get_photo(soup_no_src) is None

    html_no_comma = """
    <html><body>
      <td class="cvAvatar"><img src="data:image/png;base64ABCDEF"></td>
    </body></html>
    """
    soup_no_comma = make_soup(html_no_comma)
    assert get_photo(soup_no_comma) is None


def test_get_photo_header_not_data():
    html = """
    <html><body>
      <td class="cvAvatar">
        <img src="image/png;base64,AAAA">
      </td>
    </body></html>
    """
    soup = make_soup(html)

    assert get_photo(soup) is None


def test_get_photo_skips_specific_placeholder():
    # Любой валидный base64, начинающийся с нужного префикса
    data64 = "iVBORw0KGgoAAAANSUhEUgAAARgAAAEZCAYAAAABAAA="
    src = f"data:image/png;base64,{data64}"

    html = f"""
    <html><body>
      <td class="cvAvatar">
        <img src="{src}">
      </td>
    </body></html>
    """
    soup = make_soup(html)

    assert get_photo(soup) is None


def test_get_photo_unknown_mime_type(tmp_path):
    bytes_data = b"test-bytes"
    data64 = base64.b64encode(bytes_data).decode("ascii")
    src = f"data:application/octet-stream;base64,{data64}"

    html = f"""
    <html><body>
      <td class="cvAvatar">
        <img src="{src}">
      </td>
    </body></html>
    """
    soup = make_soup(html)

    result = get_photo(soup, save_dir=tmp_path, filename="photo.xxx")

    assert result["mime_type"] == "application/octet-stream"
    assert result["file_obj"].read() == bytes_data
    assert Path(result["filename"]).suffix == ".bin"