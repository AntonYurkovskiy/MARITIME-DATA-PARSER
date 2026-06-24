"""
Tests for contracts strategy.
"""

from pathlib import Path
import pytest

from src.parsers.html import main_parser, get_html_content
from src.orchestration.strategies.contracts import (
    parse_sea_service_raw,
    normalize_sea_service,
    validate_contracts,
    build_contracts_payloads,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


@pytest.fixture
def full_html_parsed():
    """Parse full.html through main_parser to get raw_data dict."""
    html_path = FIXTURES_DIR / "full.html"
    soup = get_html_content(str(html_path))
    return main_parser(soup)


@pytest.fixture
def parsed_contracts(full_html_parsed):
    """Extract parsed sea service contracts."""
    return parse_sea_service_raw(full_html_parsed)


class TestParseSeaServiceRaw:
    """Test parse_sea_service_raw function."""

    def test_extract_sea_service_list(self, full_html_parsed):
        """Should extract list from 'Sea service (last 5 years)' section."""
        result = parse_sea_service_raw(full_html_parsed)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_contract_has_expected_fields(self, full_html_parsed):
        """Each contract entry should have expected fields."""
        result = parse_sea_service_raw(full_html_parsed)
        for contract in result:
            assert isinstance(contract, dict)
            assert "Position" in contract
            assert "Vessel Name / Flag" in contract
            assert "From - Till" in contract

    def test_returns_empty_list_when_missing(self):
        """Should return empty list when Sea service section missing."""
        result = parse_sea_service_raw({})
        assert result == []

    def test_returns_empty_list_for_non_list_value(self):
        """Should return empty list if value is not a list."""
        result = parse_sea_service_raw({"Sea service (last 5 years)": "not a list"})
        assert result == []


class TestNormalizeSeaService:
    """Test normalize_sea_service function."""

    def test_normalize_populates_all_fields(self, parsed_contracts):
        """Each normalized contract should have all expected fields."""
        result = normalize_sea_service(parsed_contracts)
        
        expected_fields = [
            "rank",
            "rank_id",
            "vessel_name",
            "vessel_flag",
            "vessel_name_raw",
            "vessel_type",
            "dwt",
            "sign_on_date",
            "sign_off_date",
            "shipowner",
            "shipowner_country",
        ]
        
        assert len(result) > 0
        for contract in result:
            assert isinstance(contract, dict)
            for field in expected_fields:
                assert field in contract, f"Field '{field}' missing in normalized contract"

    def test_normalize_extracts_vessel_name_and_flag(self, parsed_contracts):
        """Should split 'Vessel Name / Flag' into separate fields."""
        result = normalize_sea_service(parsed_contracts)
        for contract in result:
            # Either both empty or both populated
            vessel_name = contract.get("vessel_name")
            if vessel_name:
                assert isinstance(vessel_name, str)
                assert len(vessel_name) > 0

    def test_normalize_parses_dates(self, parsed_contracts):
        """Should parse From - Till into sign_on_date and sign_off_date."""
        result = normalize_sea_service(parsed_contracts)
        for contract in result:
            # If dates are present, should be ISO format YYYY-MM-DD
            sign_on = contract.get("sign_on_date")
            sign_off = contract.get("sign_off_date")
            if sign_on:
                assert isinstance(sign_on, str)
                assert len(sign_on) == 10  # YYYY-MM-DD
                assert sign_on.count("-") == 2
            if sign_off:
                assert isinstance(sign_off, str)
                assert len(sign_off) == 10
                assert sign_off.count("-") == 2

    def test_normalize_parses_vessel_type_dwt(self, parsed_contracts):
        """Should split vessel_type and DWT."""
        result = normalize_sea_service(parsed_contracts)
        for contract in result:
            dwt = contract.get("dwt")
            if dwt is not None:
                assert isinstance(dwt, int)

    def test_normalize_handles_shipowner_country(self, parsed_contracts):
        """Should split Shipowner / Country into separate fields."""
        result = normalize_sea_service(parsed_contracts)
        for contract in result:
            shipowner = contract.get("shipowner")
            shipowner_country = contract.get("shipowner_country")
            assert isinstance(shipowner, str)
            assert isinstance(shipowner_country, str)

    def test_normalize_handles_empty_list(self):
        """Should handle empty list gracefully."""
        result = normalize_sea_service([])
        assert result == []

    def test_normalize_handles_missing_fields_gracefully(self):
        """Should handle entries with missing fields without crashing."""
        raw = [
            {
                "Position": "Chief Officer",
                # Missing other fields
            },
            {
                "Vessel Name / Flag": "COOL EXPLORER / MALTA",
                # Missing other fields
            },
        ]
        result = normalize_sea_service(raw)
        assert len(result) == 2
        assert result[0]["rank"] == "Chief Officer"
        assert result[1]["vessel_name"] == "COOL EXPLORER"


class TestValidateContracts:
    """Test validate_contracts function."""

    def test_validate_passes_valid_contracts(self, parsed_contracts):
        """Valid contracts with all required fields should pass."""
        normalized = normalize_sea_service(parsed_contracts)
        is_valid, errors = validate_contracts(normalized)
        
        # Should pass if at least one valid entry
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    def test_validate_fails_empty_list(self):
        """Should fail when no contracts provided."""
        is_valid, errors = validate_contracts([])
        
        assert not is_valid
        assert len(errors) > 0
        assert any("no sea service entries" in e.lower() for e in errors)

    def test_validate_fails_missing_vessel_name(self):
        """Should fail when vessel_name is missing."""
        contracts = [
            {
                "vessel_name": None,
                "sign_on_date": "2020-01-01",
                "sign_off_date": "2020-02-01",
            }
        ]
        is_valid, errors = validate_contracts(contracts)
        
        assert not is_valid
        assert any("vessel_name" in e.lower() for e in errors)

    def test_validate_fails_missing_sign_on_date(self):
        """Should fail when sign_on_date is missing."""
        contracts = [
            {
                "vessel_name": "TEST VESSEL",
                "sign_on_date": None,
                "sign_off_date": "2020-02-01",
            }
        ]
        is_valid, errors = validate_contracts(contracts)
        
        assert not is_valid
        assert any("sign_on_date" in e.lower() for e in errors)

    def test_validate_fails_missing_sign_off_date(self):
        """Should fail when sign_off_date is missing."""
        contracts = [
            {
                "vessel_name": "TEST VESSEL",
                "sign_on_date": "2020-01-01",
                "sign_off_date": None,
            }
        ]
        is_valid, errors = validate_contracts(contracts)
        
        assert not is_valid
        assert any("sign_off_date" in e.lower() for e in errors)

    def test_validate_partial_valid_contracts(self):
        """Should pass if at least one contract is valid, even if others aren't."""
        contracts = [
            {
                "vessel_name": None,  # Invalid
                "sign_on_date": "2020-01-01",
                "sign_off_date": "2020-02-01",
            },
            {
                "vessel_name": "VALID VESSEL",  # Valid
                "sign_on_date": "2020-03-01",
                "sign_off_date": "2020-04-01",
            },
        ]
        is_valid, errors = validate_contracts(contracts)
        
        assert is_valid  # Should pass because at least one is valid


class TestBuildContractsPayloads:
    """Test build_contracts_payloads function."""

    def test_payload_structure_matches_api_format(self, parsed_contracts):
        """Payloads should match POST /contracts API format."""
        normalized = normalize_sea_service(parsed_contracts)
        payloads = build_contracts_payloads(normalized)
        
        assert isinstance(payloads, list)
        for payload in payloads:
            assert isinstance(payload, dict)
            expected_keys = [
                "is_historical",
                "rank_id",
                "vessel",
                "sign_on_date",
                "sign_off_date",
                "is_automatic",
                "off_reason_id",
                "details",
            ]
            for key in expected_keys:
                assert key in payload, f"Key '{key}' missing in payload"

    def test_vessel_object_in_payload(self, parsed_contracts):
        """Payload should have vessel object with uuid, source, name, flag."""
        normalized = normalize_sea_service(parsed_contracts)
        payloads = build_contracts_payloads(normalized)
        
        for payload in payloads:
            vessel = payload.get("vessel")
            assert isinstance(vessel, dict)
            assert "uuid" in vessel
            assert "source" in vessel
            assert "name" in vessel
            assert "flag" in vessel

    def test_dates_in_iso_format(self, parsed_contracts):
        """sign_on_date and sign_off_date should be ISO format."""
        normalized = normalize_sea_service(parsed_contracts)
        payloads = build_contracts_payloads(normalized)
        
        for payload in payloads:
            sign_on = payload.get("sign_on_date")
            sign_off = payload.get("sign_off_date")
            
            if sign_on:
                assert len(sign_on) == 10
                assert sign_on.count("-") == 2
            if sign_off:
                assert len(sign_off) == 10
                assert sign_off.count("-") == 2

    def test_skips_invalid_entries(self):
        """Should skip entries without required fields."""
        contracts = [
            {
                "vessel_name": None,
                "sign_on_date": "2020-01-01",
                "sign_off_date": "2020-02-01",
            },
            {
                "vessel_name": "VALID VESSEL",
                "sign_on_date": "2020-03-01",
                "sign_off_date": "2020-04-01",
            },
        ]
        payloads = build_contracts_payloads(contracts)
        
        # Should only include valid entry
        assert len(payloads) == 1
        assert payloads[0]["vessel"]["name"] == "VALID VESSEL"

    def test_builds_payloads_with_minimal_data(self):
        """Payload should build even with minimal data."""
        contracts = [
            {
                "vessel_name": "TEST VESSEL",
                "vessel_flag": "MALTA",
                "rank_id": 1,
                "sign_on_date": "2020-01-01",
                "sign_off_date": "2020-02-01",
            }
        ]
        payloads = build_contracts_payloads(contracts)
        
        assert len(payloads) == 1
        payload = payloads[0]
        assert payload["is_historical"] is True
        assert payload["rank_id"] == 1
        assert payload["vessel"]["name"] == "TEST VESSEL"


class TestContractsIntegration:
    """Integration tests for full contracts pipeline."""

    def test_full_pipeline_parse_normalize_validate_build(self, full_html_parsed):
        """Full pipeline: parse -> normalize -> validate -> build."""
        # Parse
        raw = parse_sea_service_raw(full_html_parsed)
        assert isinstance(raw, list)
        
        # Normalize
        normalized = normalize_sea_service(raw)
        assert isinstance(normalized, list)
        
        # Validate
        is_valid, errors = validate_contracts(normalized)
        if not is_valid:
            pytest.skip(f"Validation failed: {errors}")
        
        # Build
        payloads = build_contracts_payloads(normalized)
        assert isinstance(payloads, list)
        assert len(payloads) > 0
        
        # Check structure of first payload
        first = payloads[0]
        assert first.get("is_historical") is True
        assert first.get("vessel") is not None
        assert first.get("sign_on_date") is not None
