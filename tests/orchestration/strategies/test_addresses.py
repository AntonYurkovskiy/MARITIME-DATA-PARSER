"""
Tests for addresses strategy.
"""

from src.orchestration.strategies.addresses import (
    parse_addresses_raw,
    normalize_addresses,
    validate_addresses,
    build_addresses_payload,
)
import src.orchestration.strategies.addresses as addresses_module


def test_parse_addresses_raw_extracts_home_address_section():
    raw_data = {
        "Main info": {
            "Home address:": "4, Raduzhnyi",
            "Country of residence / City:": "Ukraine / Odessa",
            "Citizenship:": "Ukraine",
            "Closest airport:": "Odessa",
        },
        "Additional info": {"Kin address:": ""},
    }

    result = parse_addresses_raw(raw_data)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["home_address"] == "4, Raduzhnyi"
    assert result[0]["type_id"] == 1


def test_parse_addresses_raw_returns_empty_list_when_no_address():
    assert parse_addresses_raw({"Main info": {}, "Additional info": {}}) == []


def test_normalize_addresses_resolves_geo_ids(monkeypatch):
    raw_addresses = [
        {
            "type_id": 1,
            "home_address": "4, Raduzhnyi",
            "residence": "Ukraine / Odessa",
            "citizenship": "Ukraine",
            "closest_airport": "Odessa",
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.get_resident_country",
        lambda search_term, citizenship: "Ukraine",
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses._load_reference_dicts",
        lambda: {
            "geo_regions": [{"id": 44, "value": "Odessa region"}],
            "airports": [{"id": 77, "value": "Odessa"}],
        },
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.search_geo",
        lambda term, geo_type: [
            {
                "id": {"countries": 11, "cities": 22}.get(geo_type, 33),
                "region": {"id": 44},
            }
        ],
    )

    result = normalize_addresses(raw_addresses)

    assert len(result) == 1
    assert result[0]["country_id"] == 11
    assert result[0]["city_id"] == 22
    assert result[0]["nearest_airport_id"] == 77
    assert result[0]["region_id"] == 44
    assert result[0]["line1"] == "4, Raduzhnyi"


def test_normalize_addresses_extracts_apartment_to_line2(monkeypatch):
    raw_addresses = [
        {
            "type_id": 1,
            "home_address": "Lenina 10/5",
            "residence": "Ukraine / Odessa",
            "citizenship": "Ukraine",
            "closest_airport": "Odessa",
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.get_resident_country",
        lambda search_term, citizenship: "Ukraine",
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses._load_reference_dicts",
        lambda: {
            "geo_regions": [],
            "airports": [{"id": 77, "value": "Odessa"}],
        },
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.search_geo",
        lambda term, geo_type: [
            {
                "id": {"countries": 11, "cities": 22}.get(geo_type, 33),
                "region_id": 44,
            }
        ],
    )

    result = normalize_addresses(raw_addresses)

    assert len(result) == 1
    assert result[0]["line1"] == "Lenina 10"
    assert result[0]["line2"] == "5"


def test_normalize_addresses_extracts_apartment_with_multiple_spaces(monkeypatch):
    raw_addresses = [
        {
            "type_id": 1,
            "home_address": "  Lenina    10 /   5  ",
            "residence": "Ukraine / Odessa",
            "citizenship": "Ukraine",
            "closest_airport": "Odessa",
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.get_resident_country",
        lambda search_term, citizenship: "Ukraine",
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses._load_reference_dicts",
        lambda: {
            "geo_regions": [],
            "airports": [{"id": 77, "value": "Odessa"}],
        },
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.search_geo",
        lambda term, geo_type: [
            {
                "id": {"countries": 11, "cities": 22}.get(geo_type, 33),
                "region_id": 44,
            }
        ],
    )

    result = normalize_addresses(raw_addresses)

    assert len(result) == 1
    assert result[0]["line1"] == "Lenina 10"
    assert result[0]["line2"] == "5"


def test_validate_addresses_accepts_minimal_valid_payload():
    addresses = [
        {
            "type_id": 1,
            "city_id": 22,
            "region_id": None,
            "country_id": 11,
            "line1": "4, Raduzhnyi",
            "line2": None,
            "zip": None,
            "nearest_airport_id": 22,
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    is_valid, errors = validate_addresses(addresses)

    assert is_valid
    assert errors == []


def test_validate_addresses_rejects_missing_line1():
    addresses = [
        {
            "type_id": 1,
            "city_id": None,
            "region_id": None,
            "country_id": None,
            "line1": None,
            "line2": None,
            "zip": None,
            "nearest_airport_id": None,
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    is_valid, errors = validate_addresses(addresses)

    assert not is_valid
    assert any("line1" in error.lower() for error in errors)


def test_build_addresses_payload_keeps_api_shape():
    addresses = [
        {
            "type_id": 1,
            "city_id": 22,
            "region_id": None,
            "country_id": 11,
            "line1": "4, Raduzhnyi",
            "line2": None,
            "zip": None,
            "nearest_airport_id": 22,
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    payload = build_addresses_payload(addresses)

    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["type_id"] == 1
    assert payload[0]["line1"] == "4, Raduzhnyi"
    assert "country_id" in payload[0]


def test_normalize_addresses_city_is_filtered_by_country(monkeypatch):
    raw_addresses = [
        {
            "type_id": 1,
            "home_address": "Rua monte tadue",
            "residence": "Portugal/porto",
            "citizenship": "Egypt",
            "closest_airport": "Opo",
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.get_resident_country",
        lambda search_term, citizenship: "Portugal",
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses._load_reference_dicts",
        lambda: {"geo_regions": [], "airports": []},
    )

    def fake_search_geo(term, geo_type):
        if geo_type == "countries":
            return [{"id": 620, "name": "Portugal"}]
        if geo_type == "cities":
            return [
                {"id": 13992, "name": "Porto", "country": {"name": "Brazil"}},
                {"id": 89425, "name": "Porto", "country": {"name": "Portugal"}},
            ]
        if geo_type == "airports":
            return [
                {"id": 1, "name": "Some Airfield", "country": {"name": "Portugal"}},
                {"id": 43858, "name": "Francisco de Sa Carneiro Airport", "country": {"name": "Portugal"}},
            ]
        return []

    monkeypatch.setattr("src.orchestration.strategies.addresses.search_geo", fake_search_geo)

    result = normalize_addresses(raw_addresses)

    assert len(result) == 1
    assert result[0]["city_id"] == 89425
    assert result[0]["nearest_airport_id"] == 43858


def test_normalize_addresses_city_fallback_from_line1(monkeypatch):
    raw_addresses = [
        {
            "type_id": 1,
            "home_address": "Latvia, Jurmala, Skolas str35 -33",
            "residence": "Latvia",
            "citizenship": "Latvia",
            "closest_airport": "Riga",
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.get_resident_country",
        lambda search_term, citizenship: "Latvia",
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses._load_reference_dicts",
        lambda: {"geo_regions": [], "airports": []},
    )

    def fake_search_geo(term, geo_type):
        if geo_type == "countries":
            return [{"id": 428, "name": "Latvia"}]
        if geo_type == "cities":
            return [{"id": 66909, "name": "Jurmala", "country": {"name": "Latvia"}}]
        if geo_type == "airports":
            return [
                {"id": 858, "name": "Kendrigan Airport", "country": {"name": "United States"}},
                {"id": 24992, "name": "Riga International Airport", "country": {"name": "Latvia"}},
            ]
        return []

    monkeypatch.setattr("src.orchestration.strategies.addresses.search_geo", fake_search_geo)

    result = normalize_addresses(raw_addresses)

    assert len(result) == 1
    assert result[0]["city_id"] == 66909
    assert result[0]["nearest_airport_id"] == 24992


def test_normalize_addresses_removes_leading_slash_in_line1(monkeypatch):
    raw_addresses = [
        {
            "type_id": 1,
            "home_address": "/30 Voroshilova",
            "residence": "Uman",
            "citizenship": "Ukraine",
            "closest_airport": "",
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.get_resident_country",
        lambda search_term, citizenship: "Ukraine",
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses._load_reference_dicts",
        lambda: {"geo_regions": [], "airports": []},
    )

    def fake_search_geo(term, geo_type):
        if geo_type == "countries":
            return [{"id": 804, "name": "Ukraine"}]
        if geo_type == "cities":
            return [{"id": 110656, "name": "Uman", "country": {"name": "Ukraine"}}]
        return []

    monkeypatch.setattr("src.orchestration.strategies.addresses.search_geo", fake_search_geo)

    result = normalize_addresses(raw_addresses)

    assert len(result) == 1
    assert result[0]["line1"] == "30 Voroshilova"
    assert result[0]["city_id"] == 110656


def test_normalize_addresses_adds_comment_for_unresolved_fields(monkeypatch):
    raw_addresses = [
        {
            "type_id": 1,
            "home_address": "Some street 1",
            "residence": "Ukraine/Uman",
            "citizenship": "Ukraine",
            "closest_airport": "Riga",
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.get_resident_country",
        lambda search_term, citizenship: "Ukraine",
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses._load_reference_dicts",
        lambda: {"geo_regions": [], "airports": []},
    )

    def fake_search_geo(term, geo_type):
        if geo_type == "countries":
            return [{"id": 804, "name": "Ukraine"}]
        # Simulate unresolved city and airport.
        return []

    monkeypatch.setattr("src.orchestration.strategies.addresses.search_geo", fake_search_geo)

    result = normalize_addresses(raw_addresses)

    assert len(result) == 1
    assert result[0]["city_id"] is None
    assert result[0]["nearest_airport_id"] is None
    assert result[0]["comment"] is not None
    assert "Нераспознанные поля" in result[0]["comment"]
    assert '"city_id" - "Uman"' in result[0]["comment"]


def test_load_reference_dicts_fallback_when_geo_regions_endpoint_fails(monkeypatch):
    monkeypatch.setattr(addresses_module, "_REFERENCE_CACHE", {})

    def fake_get_dict(key):
        if key == "geo/regions":
            raise RuntimeError("404")
        if key == "geo_regions":
            return [{"id": 44, "value": "Odessa region"}]
        if key == "airports":
            return [{"id": 77, "value": "Odessa"}]
        return []

    monkeypatch.setattr(addresses_module, "get_dict", fake_get_dict)

    refs = addresses_module._load_reference_dicts()

    assert refs["geo_regions"] == [{"id": 44, "value": "Odessa region"}]
    assert refs["airports"] == [{"id": 77, "value": "Odessa"}]


def test_normalize_addresses_matches_khrabrovo_alias(monkeypatch):
    raw_addresses = [
        {
            "type_id": 1,
            "home_address": "Leninsky ave 1",
            "residence": "Russia / Kaliningrad",
            "citizenship": "Russia",
            "closest_airport": "Kaliningrad Khrabrovo Airport",
            "nearest_train_station": None,
            "comment": None,
        }
    ]

    monkeypatch.setattr(
        "src.orchestration.strategies.addresses.get_resident_country",
        lambda search_term, citizenship: "Russia",
    )
    monkeypatch.setattr(
        "src.orchestration.strategies.addresses._load_reference_dicts",
        lambda: {"geo_regions": [], "airports": []},
    )

    def fake_search_geo(term, geo_type):
        if geo_type == "countries":
            return [{"id": 643, "name": "Russia"}]
        if geo_type == "cities":
            return [{"id": 12345, "name": "Kaliningrad", "country": {"name": "Russia"}}]
        if geo_type == "airports":
            return [
                {"id": 111, "name": "Kaliningrad Airport Terminal", "country": {"name": "Russia"}},
                {"id": 24993, "name": "Khrabrovo Airport (KGD)", "country": {"name": "Russia"}},
            ]
        return []

    monkeypatch.setattr("src.orchestration.strategies.addresses.search_geo", fake_search_geo)

    result = normalize_addresses(raw_addresses)

    assert len(result) == 1
    assert result[0]["nearest_airport_id"] == 24993
