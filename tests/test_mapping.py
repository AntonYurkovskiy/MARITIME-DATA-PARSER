# tests/test_country_mapping.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.mapping import ( 
    normalize_key,
    load_mapping,
    save_mapping,
    get_value,
    set_value,
    update_mapping,
    remove_key,
)


# ---------- tests for normalize_key ----------

@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("Hello", "hello"),
        ("  HELLO  ", "hello"),
        ("Hello World", "hello world"),
        ("Hello, World!", "hello world"),
        ("Hello!!!", "hello"),
        ("Hello  World", "hello world"),
        # ("مثال 123", "пример 123"),  # если кириллица
        ("test@example.com", "testexamplecom"),
        ("COUNTRY-NAME", "countryname"),
    ],
)
def test_normalize_key(input_val: str | None, expected: str) -> None:
    assert normalize_key(input_val) == expected


# ---------- tests for load_mapping ----------

def test_load_mapping_file_exists(tmp_path: Path) -> None:
    data = {"Hello World": "value1", "Test!": "value2"}
    file_path = tmp_path / "map.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    result = load_mapping(file_path)

    assert result == {
        "hello world": "value1",
        "test": "value2",
    }


def test_load_mapping_file_not_exists(tmp_path: Path) -> None:
    file_path = tmp_path / "nonexistent.json"

    result = load_mapping(file_path)

    assert result == {}


def test_load_mapping_with_default(tmp_path: Path) -> None:
    default = {"a": "b"}
    file_path = tmp_path / "nonexistent.json"

    result = load_mapping(file_path, default=default)

    assert result == {"a": "b"}
    # убедимся, что не вернули сам объект default
    assert result is not default


# ---------- tests for save_mapping ----------

def test_save_mapping_creates_file_and_dirs(tmp_path: Path) -> None:
    mapping = {"Hello!": "value1", "Test": "value2"}
    file_path = tmp_path / "subdir" / "data" / "map.json"

    save_mapping(mapping, file_path)

    assert file_path.exists()
    data = json.loads(file_path.read_text(encoding="utf-8"))

    # После нормализации: "Hello!" -> "hello", "Test" -> "test"
    assert data == {
        "hello": "value1",
        "test": "value2",
    }


def test_save_mapping_normalizes_keys(tmp_path: Path) -> None:
    mapping = {"Hello!!!": "v1", "  Test  ": "v2"}
    file_path = tmp_path / "map.json"

    save_mapping(mapping, file_path)

    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert "hello" in data
    assert "test" in data
    assert data["hello"] == "v1"
    assert data["test"] == "v2"


# ---------- tests for get_value ----------

# def test_get_value_with_mapping() -> None:
#     mapping = {"hello world": "value1"}

#     # normalize_key("Hello World!") -> "hello world"
#     assert get_value("Hello World!", mapping=mapping) == "value1"
#     assert get_value("hello world", mapping=mapping) == "value1"
#     assert get_value("HELLO   WORLD !!!", mapping=mapping) == "value1"


def test_get_value_loads_from_file(tmp_path: Path) -> None:
    data = {"Test Key": "loaded_value"}
    file_path = tmp_path / "map.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    result = get_value("test key", path=file_path)

    assert result == "loaded_value"


def test_get_value_with_default(tmp_path: Path) -> None:
    mapping = {}
    assert get_value("key", mapping=mapping, default="default_val") == "default_val"


# ---------- tests for set_value ----------

def test_set_value_creates_and_saves(tmp_path: Path) -> None:
    file_path = tmp_path / "map.json"

    result = set_value("New Key", "new value", path=file_path, merge=False)

    assert result == {"new key": "new value"}
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert data == {"new key": "new value"}


def test_set_value_merges_with_existing(tmp_path: Path) -> None:
    data = {"existing": "value"}
    file_path = tmp_path / "map.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    result = set_value("New Key", "new value", path=file_path, merge=True)

    assert "existing" in result
    assert result["new key"] == "new value"


# ---------- tests for update_mapping ----------

def test_update_mapping_merges(tmp_path: Path) -> None:
    data = {"old": "value"}
    file_path = tmp_path / "map.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    result = update_mapping(
        {"new key": "new value"}, path=file_path, merge=True
    )

    assert result["old"] == "value"
    assert result["new key"] == "new value"


def test_update_mapping_replaces_when_merge_false(tmp_path: Path) -> None:
    data = {"old": "value"}
    file_path = tmp_path / "map.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    result = update_mapping(
        {"new key": "new value"}, path=file_path, merge=False
    )

    assert "old" not in result
    assert result == {"new key": "new value"}


# ---------- tests for remove_key ----------

def test_remove_key_removes(tmp_path: Path) -> None:
    data = {"key to remove": "value", "keep": "value2"}
    file_path = tmp_path / "map.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    result = remove_key("key to remove", path=file_path)

    assert "key to remove" not in result
    assert "keep" in result


def test_remove_key_nonexistent_no_error(tmp_path: Path) -> None:
    data = {"keep": "value"}
    file_path = tmp_path / "map.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    result = remove_key("nonexistent", path=file_path)

    assert result == {"keep": "value"}