from pathlib import Path
import os
import pytest

# Set env BEFORE any modules are imported (must be done at module level)
os.environ["DISABLE_CACHE"] = "true"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_configure(config):
    """Disable persistent cache during tests to ensure mocks work correctly."""
    os.environ["DISABLE_CACHE"] = "true"
    # Patch already-imported modules
    try:
        import src.api.dicts as _dicts_mod
        _dicts_mod._CACHE_DISABLED = True
    except ImportError:
        pass
    try:
        import src.api.geo as _geo_mod
        _geo_mod._CACHE_DISABLED = True
    except ImportError:
        pass
    try:
        import src.api.seafarers as _sf_mod
        _sf_mod._CACHE_DISABLED = True
    except ImportError:
        pass
    try:
        import src.api.vessels as _vessels_mod
        _vessels_mod._CACHE_DISABLED = True
    except ImportError:
        pass


@pytest.fixture
def fixture_html():
    def _read(name: str) -> str:
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return _read
