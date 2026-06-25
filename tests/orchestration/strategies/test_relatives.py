"""
Tests for relatives strategy.
"""

from src.orchestration.strategies import relatives


def test_parse_relatives_raw_extracts_kin_block():
    raw_data = {
        "Main info": {
            "Citizenship:": "Ukraine",
            "Country of residence / City:": "Ukraine / Odesa",
            "Phones:": "+380501112233",
        },
        "Additional info": {
            "Next of kin:": "Wife",
            "Kin phone:": "+380671234567",
            "Kin name, Surname:": "Ianishevska Olha",
            "Kin address:": "Ukraine, Odesa, Shevchenko ave 10",
        },
    }

    parsed = relatives.parse_relatives_raw(raw_data)

    assert len(parsed) == 1
    assert parsed[0]["relationship"] == "Wife"
    assert parsed[0]["name_raw"] == "Ianishevska Olha"
    assert parsed[0]["phone_raw"] == "+380671234567"
    assert parsed[0]["address_raw"] == "Ukraine, Odesa, Shevchenko ave 10"


def test_normalize_relatives_builds_nested_addresses(monkeypatch):
    monkeypatch.setattr(
        relatives,
        "_load_reference_dicts",
        lambda: {
            "gender": [
                {"id": 1, "value": "male"},
                {"id": 2, "value": "female"},
            ],
            "languages": [
                {"id": 10, "value": "Ukrainian"},
            ],
            "relatives_types": [
                {"id": 5, "value": "Wife"},
            ],
        },
    )
    monkeypatch.setattr(relatives, "get_resident_country", lambda residence, citizenship: "Ukraine")
    monkeypatch.setattr(relatives, "search_geo", lambda term, geo_type: [{"id": 99}] if geo_type == "countries" and term == "Ukraine" else [])
    monkeypatch.setattr(relatives, "get_phones", lambda *args, **kwargs: [{"uuid": None, "country_id": 380, "number": "671234567", "type_id": 1, "comment": "comment"}])
    monkeypatch.setattr(relatives, "country_to_language", lambda citizenship: "Ukrainian")
    monkeypatch.setattr(relatives, "get_dict", lambda key: [])

    normalized = relatives.normalize_relatives(
        [
            {
                "relationship": "Wife",
                "name_raw": "Ianishevska Olha",
                "phone_raw": "+380671234567",
                "address_raw": "Ukraine, Odesa, Shevchenko ave 10",
                "email_raw": "wife@example.com",
                "dob_raw": "12.03.1988",
                "gender_raw": "female",
                "citizenship": "Ukraine",
                "residence": "Ukraine / Odesa",
                "personal_id": "AB123456",
            }
        ]
    )

    assert len(normalized) == 1
    item = normalized[0]
    assert item["name"] == "Ianishevska"
    assert item["surname"] == "Olha"
    assert item["personal_id"] == "AB123456"
    assert item["date_of_birth"] == "1988-03-12"
    assert item["gender_id"] == 2
    assert item["relationship_type_id"] == 5
    assert item["language_id"] == 10
    assert item["phone_numbers"]
    assert item["emails"] == [{"email": "wife@example.com", "comment": "comment", "uuid": None}]
    assert item["addresses"]
    assert item["addresses"][0]["line1"] == "Ukraine, Odesa, Shevchenko ave 10"


def test_validate_relatives_requires_relationship_type():
    is_valid, errors = relatives.validate_relatives(
        [
            {
                "name": "Olha",
                "surname": "Ianishevska",
                "relationship_type_id": None,
            }
        ]
    )

    assert not is_valid
    assert any("relationship_type_id" in error for error in errors)


def test_build_relatives_payload_preserves_nested_lists():
    payload = relatives.build_relatives_payload(
        [
            {
                "name": "Olha",
                "surname": "Ianishevska",
                "personal_id": "AB123456",
                "date_of_birth": "1988-03-12",
                "gender_id": 2,
                "relationship_type_id": 5,
                "language_id": 10,
                "phone_numbers": [{"uuid": None, "country_id": 380, "number": "671234567", "type_id": 1, "comment": "comment"}],
                "emails": [{"email": "wife@example.com", "comment": "comment", "uuid": None}],
                "addresses": [{"type_id": 1, "line1": "Ukraine, Odesa, Shevchenko ave 10"}],
            }
        ]
    )

    assert len(payload) == 1
    assert payload[0]["name"] == "Olha"
    assert payload[0]["surname"] == "Ianishevska"
    assert payload[0]["relationship_type_id"] == 5
    assert payload[0]["addresses"][0]["line1"] == "Ukraine, Odesa, Shevchenko ave 10"
