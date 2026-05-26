from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def fixture_html():
    def _read(name: str) -> str:
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return _read
