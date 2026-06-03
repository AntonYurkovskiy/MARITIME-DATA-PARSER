import base64
import io
from pathlib import Path


def get_photo(soup, save_dir="out_manual", filename="photo.jpg"):
    td = soup.find('td', class_='cvAvatar')
    if not td:
        return None

    img = td.find('img')
    if not img:
        return None

    src = img.get('src')
    if not src or ',' not in src:
        return None

    header, data64 = src.split(',', 1)
    if not header.startswith('data:'):
        return None

    mime_type = header.split(';', 1)[0].split(':', 1)[1]
    image_bytes = base64.b64decode(data64)

    if data64.startswith('iVBORw0KGgoAAAANSUhEUgAAARgAAAEZCAY'):
        return None

    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(mime_type, ".bin")


    # ********************************************
    # сделать версию без сохранения на диск,
    # а просто возвращать байты и mime_type
    # для дальнейшей обработки
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    full_path = save_path / Path(filename).with_suffix(ext)
    with open(full_path, "wb") as f:
        f.write(image_bytes)
    # ********************************************
    
    
    return {
        "mime_type": mime_type,
        "file_obj": io.BytesIO(image_bytes),
        "filename": full_path.name,
        "saved_path": str(full_path), # удалить из версии без сохранения
    }


# def get_photo_simple(soup):
#     """Парсит фото и проверят на наличие заглушки

#     Args:
#         soup (bs4.BeautifulSoup): html файл обработанный с помощью BeautifulSoup(html_content, 'html.parser')

#     Returns:
#         str: mime_type вид изображения (image/jpeg, image/png, ...)
#         base64: img_data битовая строка
#     """

#     src = soup.find('td', class_ = 'cvAvatar').find('img').get('src')
#     header, data64 = src.split(',', 1)
#     mime_type = header.split(';')[0].split(':')[1]  # image/jpeg
#     ext = mime_type.split('/')[1]

#     if not data64.startswith('iVBORw0KGgoAAAANSUhEUgAAARgAAAEZCAY'):
#         img_data = base64.b64decode(data64)
#         return mime_type, img_data
#     else:
#         return None