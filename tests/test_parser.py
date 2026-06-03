from bs4 import BeautifulSoup
from pathlib import Path
import json

from src.parsers.html import main_parser


TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"

FULL_HTML = "full.html"
ALMOST_EMPTY_HTML = "almost_empty.html"
EDGE_HTML = "edge_case.html" 
GOLDEN_JSON = "golden_cv.json"

REQUIRED_SECTIONS = [
    "Main info",
    "Passports / Smbk",
    "Diplomas",
    "Certificates",
    "Sea service (last 5 years)",
    "Biometrics",
    "Additional info",
]

BIOMETRICS_KEYS = ["Sex", "Height", "Overall size", "Eyes color", "Weight", "Shoe size"]

SEA_SERVICE_KEYS = [
    "Position",
    "Vessel Name / Flag",
    "Vessel type / DWT",
    "ME Type / kW",
    "From - Till",
    "Shipowner / Country",
]


def _parse_fixture(html_name: str):
    """Вспомогательная функция: читает HTML из fixtures и прогоняет через main_parser."""
    html = (FIXTURES_DIR / html_name).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    return main_parser(soup)


def _load_golden(name: str):
    """Чтение golden JSON из fixtures."""
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _assert_sections_present(result: dict, sections: list[str]):
    for section in sections:
        assert section in result


def _assert_keys_present(mapping: dict, keys: list[str]):
    for key in keys:
        assert key in mapping


def test_full_main_parser():
    result = _parse_fixture(FULL_HTML)
    expected = _load_golden(GOLDEN_JSON)

    assert result == expected


def test_main_parser_almost_empty_minimal_fields():
    result = _parse_fixture(ALMOST_EMPTY_HTML)

    main_info = result["Main info"]
    biom = result["Biometrics"]

    assert "Name / Surname:" in main_info
    assert "Sex" in biom


def test_main_parser_edge_masked_and_single_service():
    """Специфический тест для edge-case резюме с маскировкой и одной записью стажа."""
    result = _parse_fixture(EDGE_HTML)

    # 1. Базовая структура
    assert isinstance(result, dict)
    _assert_sections_present(result, REQUIRED_SECTIONS)

    main_info = result["Main info"]
    sea = result["Sea service (last 5 years)"]
    biom = result["Biometrics"]
    add = result["Additional info"]

    # 2. Маскированные поля не потерялись и не обрезаны
    assert main_info["Name / Surname:"].startswith("Florid")
    assert main_info["Birthday / Place of birth:"].startswith("*")
    assert main_info["Phones:"].startswith("*")
    assert add["Maritime education:"].startswith("* * *")

    # 3. Одна запись sea service и корректные ключи
    assert isinstance(sea, list)
    assert len(sea) == 1
    row = sea[0]
    _assert_keys_present(row, SEA_SERVICE_KEYS)

    # 4. Biometrics полностью заполнен
    _assert_keys_present(biom, BIOMETRICS_KEYS)
    for key in BIOMETRICS_KEYS:
        assert biom[key] != ""

    # 5. В Additional info не потерялся навык
    assert add["Additional skills:"] == "Electric welding"