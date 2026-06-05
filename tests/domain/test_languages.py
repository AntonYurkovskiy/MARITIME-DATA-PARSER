import pytest
from importlib import import_module
from unittest.mock import patch

MODULE = "src.domain.languages"


@pytest.fixture
def utils_module():
    return import_module(MODULE)


class TestCountryToLanguage:
    def test_exact_match(self, utils_module):
        with patch(f"{MODULE}.COUNTRY_TO_LANGUAGE", {"Sweden": "sv"}):
            assert utils_module.country_to_language("Sweden") == "sv"

    def test_case_insensitive_match(self, utils_module):
        with patch(f"{MODULE}.COUNTRY_TO_LANGUAGE", {"Sweden": "sv"}):
            assert utils_module.country_to_language("sweden") == "sv"
            assert utils_module.country_to_language("SWEden") == "sv"

    def test_strip_spaces(self, utils_module):
        with patch(f"{MODULE}.COUNTRY_TO_LANGUAGE", {"Sweden": "sv"}):
            assert utils_module.country_to_language("  Sweden  ") == "sv"

    def test_empty_string(self, utils_module):
        with patch(f"{MODULE}.COUNTRY_TO_LANGUAGE", {"Sweden": "sv"}):
            assert utils_module.country_to_language("") is None

    def test_unknown_country(self, utils_module):
        with patch(f"{MODULE}.COUNTRY_TO_LANGUAGE", {"Sweden": "sv"}):
            assert utils_module.country_to_language("Atlantis") is None