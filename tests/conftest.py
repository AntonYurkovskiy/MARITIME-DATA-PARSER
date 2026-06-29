from pathlib import Path
import os
import pytest

# Set env BEFORE any modules are imported (must be done at module level)
os.environ["DISABLE_CACHE"] = "true"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_configure(config):
    """Disable persistent cache during tests to ensure mocks work correctly."""
    os.environ["DISABLE_CACHE"] = "true"
    # Patch the centralised flag so already-imported modules also see the change
    try:
        import src.cache.persistent_cache as _cache_mod
        _cache_mod.CACHE_ENABLED = False
    except ImportError:
        pass


@pytest.fixture
def fixture_html():
    def _read(name: str) -> str:
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return _read
