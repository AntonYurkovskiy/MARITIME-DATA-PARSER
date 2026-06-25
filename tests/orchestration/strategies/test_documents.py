"""
Tests for documents strategy.
"""

from src.orchestration.strategies import documents


def test_parse_documents_raw_extracts_certificates_list():
    raw_data = {
        "Certificates": [
            {
                "Title of document": "Basic Safety Training",
                "No.": " 1351678 ",
                "Date of issue": "29.06.2021",
                "Country of issue": "Ukraine",
                "Valid up": "29.06.2026",
            }
        ]
    }

    parsed = documents.parse_documents_raw(raw_data)

    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["Title of document"] == "Basic Safety Training"


def test_parse_documents_raw_aggregates_all_document_sections():
    raw_data = {
        "Passports / Smbk": [{"Title of document": "International passport", "No.": "P-1"}],
        "Diplomas": [{"Title of document": "Professional license", "No.": "D-1"}],
        "Medical certificates": [{"Title of document": "Medical cert", "No.": "M-1"}],
        "Certificates": [{"Title of document": "Basic Safety Training", "No.": "C-1"}],
    }

    parsed = documents.parse_documents_raw(raw_data)

    assert len(parsed) == 4
    sections = {item.get("_source_section") for item in parsed}
    assert sections == {
        "Passports / Smbk",
        "Diplomas",
        "Medical certificates",
        "Certificates",
    }


def test_normalize_documents_maps_required_fields(monkeypatch):
    monkeypatch.setattr(
        documents,
        "_load_reference_dicts",
        lambda: {
            "certificate_groups": [{"id": 501, "value": "Certificate"}],
            "certificate_types": [{"id": 601, "value": "Basic Safety Training"}],
        },
    )
    monkeypatch.setattr(documents, "search_geo", lambda term, geo_type: [{"id": 804}] if term == "Ukraine" and geo_type == "countries" else [])
    monkeypatch.setattr(
        documents,
        "get_id",
        lambda dictionary, value, dict_name: next((item["id"] for item in dictionary if item.get("value") == value), 9999),
    )

    normalized = documents.normalize_documents(
        [
            {
                "Title of document": "Basic Safety Training",
                "No.": " 1351678 ",
                "Date of issue": "29.06.2021",
                "Country of issue": "Ukraine",
                "Valid up": "29.06.2026",
                "Issuer": "  Odessa center  ",
                "Notes": "  STCW cert  ",
            }
        ]
    )

    assert len(normalized) == 1
    item = normalized[0]
    assert item["group_id"] == 501
    assert item["type_id"] == 601
    assert item["number"] == "1351678"
    assert item["issued_date"] == "2021-06-29"
    assert item["expires_date"] == "2026-06-29"
    assert item["issued_country_id"] == 804
    assert item["issuer"] == "Odessa center"
    assert item["notes"] == "STCW cert"
    assert item["files"] == []


def test_validate_documents_requires_group_and_type_ids():
    is_valid, errors = documents.validate_documents(
        [
            {
                "group_id": None,
                "type_id": None,
            }
        ]
    )

    assert not is_valid
    assert any("group_id" in error for error in errors)
    assert any("type_id" in error for error in errors)


def test_build_documents_payload_skips_invalid_entries():
    payload = documents.build_documents_payload(
        [
            {
                "group_id": 501,
                "type_id": 601,
                "number": "1351678",
                "issued_date": "2021-06-29",
                "expires_date": "2026-06-29",
                "issued_country_id": 804,
                "issuer": "Odessa center",
                "notes": "STCW cert",
                "files": [],
            },
            {
                "group_id": None,
                "type_id": None,
                "number": "broken",
            },
        ]
    )

    assert len(payload) == 1
    assert payload[0]["group_id"] == 501
    assert payload[0]["type_id"] == 601
    assert payload[0]["number"] == "1351678"


def test_normalize_documents_resolves_type_by_normalized_and_partial_match(monkeypatch):
    monkeypatch.setattr(
        documents,
        "_load_reference_dicts",
        lambda: {
            "certificate_groups": [{"id": 501, "value": "Certificate"}],
            "certificate_types": [
                {"id": 7001, "value": "Ship Carrying Dangerous Hazard Cargo"},
                {"id": 7002, "value": "Security Related Training and Instruction for All Seafarers"},
            ],
        },
    )
    monkeypatch.setattr(documents, "search_geo", lambda term, geo_type: [{"id": 804}] if term == "Ukraine" and geo_type == "countries" else [])
    monkeypatch.setattr(
        documents,
        "get_id",
        lambda dictionary, value, dict_name: next((item["id"] for item in dictionary if item.get("value") == value), None),
    )

    normalized = documents.normalize_documents(
        [
            {
                "Title of document": "Ship Carrying Dangr/hazard Cargo",
                "No.": "A-1",
                "Date of issue": "01.01.2020",
                "Country of issue": "Ukraine",
                "Valid up": "01.01.2025",
            },
            {
                "Title of document": "Security-Related Training and Instruction for all Seafarers",
                "No.": "B-2",
                "Date of issue": "01.02.2020",
                "Country of issue": "Ukraine",
                "Valid up": "01.02.2025",
            },
        ]
    )

    assert len(normalized) == 2
    assert normalized[0]["type_id"] == 7001
    assert normalized[1]["type_id"] == 7002


def test_normalize_documents_resolves_type_by_explicit_alias(monkeypatch):
    monkeypatch.setattr(
        documents,
        "_load_reference_dicts",
        lambda: {
            "certificate_groups": [{"id": 501, "value": "Certificate"}],
            "certificate_types": [
                {"id": 7101, "value": "GMDSS restricted operator"},
            ],
        },
    )
    monkeypatch.setattr(documents, "search_geo", lambda term, geo_type: [{"id": 804}] if term == "Ukraine" and geo_type == "countries" else [])
    monkeypatch.setattr(
        documents,
        "get_id",
        lambda dictionary, value, dict_name: next((item["id"] for item in dictionary if item.get("value") == value), None),
    )

    normalized = documents.normalize_documents(
        [
            {
                "Title of document": "general operator certificate",
                "No.": "A-77",
                "Date of issue": "01.01.2020",
                "Country of issue": "Ukraine",
                "Valid up": "01.01.2025",
            }
        ]
    )

    assert len(normalized) == 1
    assert normalized[0]["type_id"] == 7101


def test_normalize_documents_section_aware_resolution_for_diplomas_and_medical(monkeypatch):
    monkeypatch.setattr(
        documents,
        "_load_reference_dicts",
        lambda: {
            "certificate_groups": [
                {"id": 9001, "value": "Certificate"},
                {"id": 9002, "value": "Certificate of Competency"},
                {"id": 9003, "value": "Medical"},
            ],
            "certificate_types": [
                {"id": 9101, "value": "OOW of navig. watch on ships of 500GT or more"},
                {"id": 9102, "value": "Medical Test"},
            ],
        },
    )
    monkeypatch.setattr(documents, "search_geo", lambda term, geo_type: [])
    monkeypatch.setattr(
        documents,
        "get_id",
        lambda dictionary, value, dict_name: next((item["id"] for item in dictionary if item.get("value") == value), None),
    )

    normalized = documents.normalize_documents(
        [
            {
                "_source_section": "Diplomas",
                "Title of document": "Professional license",
                "No.": "D-100",
                "Rank": "Officer in charge of navigational watch (OOW)",
            },
            {
                "_source_section": "Medical certificates",
                "Title of document": "Seafarer Medical Certificate",
                "No.": "M-200",
            },
        ]
    )

    assert len(normalized) == 2
    assert normalized[0]["group_id"] == 9002
    assert normalized[0]["type_id"] == 9101
    assert normalized[1]["group_id"] == 9003
    assert normalized[1]["type_id"] == 9102


def test_normalize_documents_section_aware_resolution_for_passports(monkeypatch):
    monkeypatch.setattr(
        documents,
        "_load_reference_dicts",
        lambda: {
            "certificate_groups": [
                {"id": 9201, "value": "Travel Documents"},
            ],
            "certificate_types": [
                {"id": 9301, "value": "Passport"},
                {"id": 9302, "value": "Seamans Book"},
            ],
        },
    )
    monkeypatch.setattr(documents, "search_geo", lambda term, geo_type: [])
    monkeypatch.setattr(
        documents,
        "get_id",
        lambda dictionary, value, dict_name: next((item["id"] for item in dictionary if item.get("value") == value), None),
    )

    normalized = documents.normalize_documents(
        [
            {
                "_source_section": "Passports / Smbk",
                "Title of document": "International passport",
                "No.": "P-1",
            },
            {
                "_source_section": "Passports / Smbk",
                "Title of document": "Seaman's book",
                "No.": "S-1",
            },
        ]
    )

    assert len(normalized) == 2
    assert normalized[0]["group_id"] == 9201
    assert normalized[0]["type_id"] == 9301
    assert normalized[1]["group_id"] == 9201
    assert normalized[1]["type_id"] == 9302
