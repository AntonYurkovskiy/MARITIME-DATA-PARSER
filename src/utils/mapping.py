from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_MAPPING_FILE = Path(__file__).resolve().parents[2] / "data" / "country_map.json"


def normalize_key(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"[^\w\s]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def load_mapping(path: str | Path = DEFAULT_MAPPING_FILE, default: dict[str, str] | None = None) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return default.copy() if default else {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {normalize_key(k): v for k, v in data.items()}


def save_mapping(mapping: dict[str, str], path: str | Path = DEFAULT_MAPPING_FILE) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {normalize_key(k): v for k, v in mapping.items()}
    with path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2, sort_keys=True)


def get_value(key: str | None, mapping: dict[str, str] | None = None, path: str | Path = DEFAULT_MAPPING_FILE, default: Any = None):
    if mapping is None:
        mapping = load_mapping(path)
    return mapping.get(normalize_key(key), default)


def set_value(key: str, value: str, path: str | Path = DEFAULT_MAPPING_FILE, merge: bool = True) -> dict[str, str]:
    mapping = load_mapping(path) if merge else {}
    mapping[normalize_key(key)] = value
    save_mapping(mapping, path)
    return mapping


def update_mapping(new_items: dict[str, str], path: str | Path = DEFAULT_MAPPING_FILE, merge: bool = True) -> dict[str, str]:
    mapping = load_mapping(path) if merge else {}
    for k, v in new_items.items():
        mapping[normalize_key(k)] = v
    save_mapping(mapping, path)
    return mapping


def remove_key(key: str, path: str | Path = DEFAULT_MAPPING_FILE) -> dict[str, str]:
    mapping = load_mapping(path)
    mapping.pop(normalize_key(key), None)
    save_mapping(mapping, path)
    return mapping