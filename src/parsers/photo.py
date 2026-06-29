import base64
import io
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _extract_base64_image(soup) -> Optional[Tuple[bytes, str]]:
    """Находит base64‑картинку в soup, возвращает (image_bytes, mime_type) или None."""
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

    # игнорируем дефолтный плейсхолдер-аватар
    if data64.startswith('iVBORw0KGgoAAAANSUhEUgAAARgAAAEZCAY'):
        return None

    image_bytes = base64.b64decode(data64)
    return image_bytes, mime_type


def _guess_extension(mime_type: str) -> str:
    """Определяет расширение файла по mime_type."""
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(mime_type, ".bin")


def _save_image_to_disk(image_bytes: bytes, mime_type: str, save_dir: str, filename: str) -> Path:
    """Сохраняет байты изображения на диск и возвращает полный путь к файлу."""
    ext = _guess_extension(mime_type)
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)
    full_path = save_path / Path(filename).with_suffix(ext)

    with open(full_path, "wb") as f:
        f.write(image_bytes)

    return full_path


def _build_photo_object(image_bytes: bytes, mime_type: str, filename: str, saved_path: Optional[Path] = None) -> Dict[str, Any]:
    """Готовит объект для загрузки (file_obj + метаданные)."""
    result: Dict[str, Any] = {
        "mime_type": mime_type,
        "file_obj": io.BytesIO(image_bytes),
        "filename": filename,
    }
    if saved_path is not None:
        result["saved_path"] = str(saved_path)
    return result


def get_photo(soup, save_dir: str = "out_manual", filename: str = "photo.jpg") -> Optional[Dict[str, Any]]:
    """
    Разбор base64-изображения + определение типа + сохранение файла на диск
    + подготовка объекта для загрузки.
    """
    extracted = _extract_base64_image(soup)
    if not extracted:
        return None

    image_bytes, mime_type = extracted

    full_path = _save_image_to_disk(image_bytes, mime_type, save_dir, filename)

    return _build_photo_object(
        image_bytes=image_bytes,
        mime_type=mime_type,
        filename=full_path.name,
        saved_path=full_path,
    )