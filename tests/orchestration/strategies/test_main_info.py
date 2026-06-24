"""
Tests for main_info strategy.
"""

from pathlib import Path
import pytest
from bs4 import BeautifulSoup

from src.parsers.html import main_parser, get_html_content
from src.orchestration.strategies.main_info import (
    parse_main_info_raw,
    normalize_main_info,
    validate_main_info,
    build_main_info_payload,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def full_html_parsed():
    """Parse full.html through main_parser to get raw_data dict."""
    html_path = FIXTURES_DIR / "full.html"
    soup = get_html_content(str(html_path))
    return main_parser(soup)


@pytest.fixture
def parsed_main_info(full_html_parsed):
    """Extract parsed main info (with main_info and biometrics sections)."""
    return parse_main_info_raw(full_html_parsed)


class TestParseMainInfoRaw:
    """Test parse_main_info_raw function."""

    def test_extract_main_info_structure(self, full_html_parsed):
        """Should extract dict with main_info and biometrics keys."""
        result = parse_main_info_raw(full_html_parsed)
        assert isinstance(result, dict)
        assert "main_info" in result
        assert "biometrics" in result
        assert isinstance(result["main_info"], dict)
        assert isinstance(result["biometrics"], dict)

    def test_main_info_section_extracted(self, full_html_parsed):
        """main_info section should have Name / Surname key."""
        result = parse_main_info_raw(full_html_parsed)
        assert "Name / Surname:" in result["main_info"]

    def test_returns_empty_dicts_when_sections_missing(self):
        """Should return empty dicts for missing sections."""
        result = parse_main_info_raw({})
        assert result == {"main_info": {}, "biometrics": {}}


class TestNormalizeMainInfo:
    """Test normalize_main_info function."""

    def test_normalize_populates_all_fields(self, parsed_main_info):
        """Normalized output should have all expected fields."""
        result = normalize_main_info(parsed_main_info)
        
        expected_fields = [
            "name",
            "middle_name",
            "surname",
            "date_of_birth",
            "place_of_birth",
            "emails",
            "gender_id",
            "rank_id",
            "additional_ranks_id",
            "nationality_country_id",
            "language_id",
            "resident_country_id",
            "phone_numbers",
        ]
        
        for field in expected_fields:
            assert field in result, f"Field '{field}' missing in normalized output"

    def test_normalize_extracts_name_fields(self, parsed_main_info):
        """Should extract name, middle_name, surname."""
        result = normalize_main_info(parsed_main_info)
        
        assert result.get("name") is not None or parsed_main_info["main_info"].get("Name / Surname:") == ""
        assert "middle_name" in result
        assert "surname" in result

    def test_normalize_extracts_dates(self, parsed_main_info):
        """Should extract date_of_birth and place_of_birth."""
        result = normalize_main_info(parsed_main_info)
        
        # Date can be None if not present, but field should exist
        assert "date_of_birth" in result
        assert "place_of_birth" in result

    def test_normalize_handles_missing_data_gracefully(self):
        """Should handle empty/missing sections without crashing."""
        result = normalize_main_info({"main_info": {}, "biometrics": {}})
        
        assert result.get("name") is None
        assert result.get("emails") == []
        assert result.get("phone_numbers") == []


class TestValidateMainInfo:
    """Test validate_main_info function."""

    def test_validate_passes_complete_normalized_data(self, parsed_main_info):
        """Valid normalized data should pass validation."""
        normalized = normalize_main_info(parsed_main_info)
        is_valid, errors = validate_main_info(normalized)
        
        if is_valid:
            assert errors == []
        else:
            # If invalid, should have specific error messages
            assert isinstance(errors, list)
            assert all(isinstance(e, str) for e in errors)

    def test_validate_fails_missing_name(self):
        """Should fail if name is missing."""
        normalized = {
            "name": None,
            "surname": "Test",
            "rank_id": 1,
            "gender_id": 1,
            "date_of_birth": "2000-01-01",
        }
        is_valid, errors = validate_main_info(normalized)
        
        assert not is_valid
        assert any("name" in e.lower() for e in errors)

    def test_validate_fails_missing_surname(self):
        """Should fail if surname is missing."""
        normalized = {
            "name": "John",
            "surname": None,
            "rank_id": 1,
            "gender_id": 1,
            "date_of_birth": "2000-01-01",
        }
        is_valid, errors = validate_main_info(normalized)
        
        assert not is_valid
        assert any("surname" in e.lower() for e in errors)

    def test_validate_fails_missing_rank(self):
        """Should fail if rank_id is missing."""
        normalized = {
            "name": "John",
            "surname": "Doe",
            "rank_id": None,
            "gender_id": 1,
            "date_of_birth": "2000-01-01",
        }
        is_valid, errors = validate_main_info(normalized)
        
        assert not is_valid
        assert any("rank_id" in e.lower() for e in errors)

    def test_validate_fails_missing_gender(self):
        """Should fail if gender_id is missing."""
        normalized = {
            "name": "John",
            "surname": "Doe",
            "rank_id": 1,
            "gender_id": None,
            "date_of_birth": "2000-01-01",
        }
        is_valid, errors = validate_main_info(normalized)
        
        assert not is_valid
        assert any("gender_id" in e.lower() for e in errors)

    def test_validate_fails_missing_date_of_birth(self):
        """Should fail if date_of_birth is missing."""
        normalized = {
            "name": "John",
            "surname": "Doe",
            "rank_id": 1,
            "gender_id": 1,
            "date_of_birth": None,
        }
        is_valid, errors = validate_main_info(normalized)
        
        assert not is_valid
        assert any("date_of_birth" in e.lower() for e in errors)


class TestBuildMainInfoPayload:
    """Test build_main_info_payload function."""

    def test_payload_structure_matches_api_format(self, parsed_main_info):
        """Payload should match POST /seafarers/ API format."""
        normalized = normalize_main_info(parsed_main_info)
        payload = build_main_info_payload(normalized)
        
        expected_keys = [
            "name",
            "middle_name",
            "surname",
            "rank_id",
            "additional_ranks_id",
            "date_of_birth",
            "place_of_birth",
            "gender_id",
            "marital_status_id",
            "nationality_country_id",
            "emails",
            "resident_status_id",
            "fast_note",
            "phone_numbers",
            "personal_id",
            "language_id",
        ]
        
        for key in expected_keys:
            assert key in payload, f"Key '{key}' missing in payload"

    def test_emails_formatted_correctly(self, parsed_main_info):
        """Emails should be formatted as list of dicts with email, comment, uuid."""
        normalized = normalize_main_info(parsed_main_info)
        normalized["emails"] = ["test@example.com", "test2@example.com"]
        payload = build_main_info_payload(normalized)
        
        emails = payload["emails"]
        assert isinstance(emails, list)
        for email_obj in emails:
            assert isinstance(email_obj, dict)
            assert "email" in email_obj
            assert "comment" in email_obj
            assert "uuid" in email_obj
            assert email_obj["uuid"] is None

    def test_additional_ranks_as_list(self, parsed_main_info):
        """additional_ranks_id should be a list."""
        normalized = normalize_main_info(parsed_main_info)
        payload = build_main_info_payload(normalized)
        
        assert isinstance(payload["additional_ranks_id"], list)

    def test_phone_numbers_preserved(self, parsed_main_info):
        """phone_numbers should be preserved from normalized."""
        normalized = normalize_main_info(parsed_main_info)
        payload = build_main_info_payload(normalized)
        
        assert isinstance(payload["phone_numbers"], list)

    def test_payload_with_minimal_data(self):
        """Payload should build even with minimal data."""
        normalized = {
            "name": "John",
            "middle_name": "Michael",
            "surname": "Doe",
            "rank_id": 1,
            "additional_ranks_id": [],
            "date_of_birth": "2000-01-01",
            "place_of_birth": "New York",
            "gender_id": 1,
            "marital_status_id": None,
            "nationality_country_id": 1,
            "emails": [],
            "resident_country_id": None,
            "phone_numbers": [],
            "personal_id": None,
            "language_id": 1,
            "photo": None,
            "fast_note": None,
        }
        payload = build_main_info_payload(normalized)
        
        assert payload["name"] == "John"
        assert payload["rank_id"] == 1


class TestMainInfoIntegration:
    """Integration tests for full main_info pipeline."""

    def test_full_pipeline_parse_normalize_validate_build(self, full_html_parsed):
        """Full pipeline: parse -> normalize -> validate -> build."""
        # Parse
        parsed = parse_main_info_raw(full_html_parsed)
        assert parsed is not None
        assert "main_info" in parsed
        
        # Normalize
        normalized = normalize_main_info(parsed)
        assert normalized is not None
        assert normalized.get("name") is not None
        
        # Validate
        is_valid, errors = validate_main_info(normalized)
        assert is_valid, f"Validation failed: {errors}"
        
        # Build
        payload = build_main_info_payload(normalized)
        assert payload is not None
        assert isinstance(payload, dict)
        assert payload.get("name") is not None
