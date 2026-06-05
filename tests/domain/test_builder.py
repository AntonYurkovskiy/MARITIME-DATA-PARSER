# tests/parsers/test_seafarer.py

SEAFARER_MODULE = "src.domain.builder"

import pytest
from unittest.mock import MagicMock, patch
from importlib import import_module


@pytest.fixture
def seafarer():
    return import_module(SEAFARER_MODULE)


class TestBuildSeafarerDict:
    def test_build_seafarer_dict_basic(self, seafarer):
        mock_soup = MagicMock()
        with patch(SEAFARER_MODULE + ".get_photo", return_value="photo-bytes") as mock_get_photo:
            result = seafarer.build_seafarer_dict(
                soup=mock_soup,
                name="Ivan",
                middle_name="Petrovich",
                surname="Ivanov",
                rank_id=1,
                additional_ranks=[2, 3],
                date_of_birth="1990-01-01",
                place_of_birth="Moscow",
                gender_id=1,
                marital_status_id=2,
                nationality_country_id=643,
                emails=["test@example.com"],
                resident_country_id=752,
                notes="note",
                phones_list_of_dicts=[{"country_id": 752, "number": "123456"}],
                personal_id="ABC123",
                language_id_by_citizenship=10,
            )

        mock_get_photo.assert_called_once_with(mock_soup)

        assert result["photo"] == "photo-bytes"
        assert result["name"] == "Ivan"
        assert result["middle_name"] == "Petrovich"
        assert result["surname"] == "Ivanov"
        assert result["rank_id"] == 1
        assert result["additional_ranks_id"] == [2, 3]
        assert result["date_of_birth"] == "1990-01-01"
        assert result["place_of_birth"] == "Moscow"
        assert result["gender_id"] == 1
        assert result["marital_status_id"] == 2
        assert result["nationality_country_id"] == 643
        assert result["emails"] == ["test@example.com"]
        assert result["fast_note"] == "note"
        assert result["phone_numbers"] == [{"country_id": 752, "number": "123456"}]
        assert result["personal_id"] == "ABC123"
        assert result["language_id"] == 10

    def test_build_seafarer_dict_none_values(self, seafarer):
        with patch(SEAFARER_MODULE + ".get_photo", return_value=None):
            result = seafarer.build_seafarer_dict(
                soup=None,
                name=None,
                middle_name=None,
                surname=None,
                rank_id=None,
                additional_ranks=None,
                date_of_birth=None,
                place_of_birth=None,
                gender_id=None,
                marital_status_id=None,
                nationality_country_id=None,
                emails=[],
                resident_country_id=None,
                notes=None,
                phones_list_of_dicts=[],
                personal_id=None,
                language_id_by_citizenship=None,
            )

        assert result["photo"] is None
        assert result["name"] is None
        assert result["middle_name"] is None
        assert result["surname"] is None
        assert result["rank_id"] is None
        assert result["additional_ranks_id"] is None
        assert result["date_of_birth"] is None
        assert result["place_of_birth"] is None
        assert result["gender_id"] is None
        assert result["marital_status_id"] is None
        assert result["nationality_country_id"] is None
        assert result["emails"] == []
        assert result["fast_note"] is None
        assert result["phone_numbers"] == []
        assert result["personal_id"] is None
        assert result["language_id"] is None


class TestStringifyIdFields:
    def test_simple_ids_to_string(self, seafarer):
        data = {
            "rank_id": 1,
            "gender_id": 2,
            "name": "Ivan",
            "emails": ["a@test.com"],
            "nationality_country_id": None,
        }

        result = seafarer.stringify_id_fields(data)

        assert result["rank_id"] == "1"
        assert result["gender_id"] == "2"
        assert result["nationality_country_id"] is None
        assert result["name"] == "Ivan"
        assert result["emails"] == ["a@test.com"]

    def test_nested_dict_ids(self, seafarer):
        data = {
            "person": {
                "gender_id": 1,
                "details": {
                    "nationality_country_id": 643,
                    "document": {"type_id": 5, "number": "123"},
                },
            },
            "other": "value",
        }

        result = seafarer.stringify_id_fields(data)

        assert result["person"]["gender_id"] == "1"
        assert result["person"]["details"]["nationality_country_id"] == "643"
        assert result["person"]["details"]["document"]["type_id"] == "5"
        assert result["person"]["details"]["document"]["number"] == "123"
        assert result["other"] == "value"

    def test_list_of_dicts(self, seafarer):
        data = {
            "phone_numbers": [
                {"country_id": 752, "type_id": 1},
                {"country_id": None, "type_id": 2},
            ],
            "notes": "test",
        }

        result = seafarer.stringify_id_fields(data)

        assert result["phone_numbers"][0]["country_id"] == "752"
        assert result["phone_numbers"][0]["type_id"] == "1"
        assert result["phone_numbers"][1]["country_id"] is None
        assert result["phone_numbers"][1]["type_id"] == "2"
        assert result["notes"] == "test"

    def test_mixed_types(self, seafarer):
        data = {
            "id": 10,  # не заканчивается на _id => не трогаем
            "user_id": 20,
            "items": [
                1,
                {"item_id": 30, "value": 100},
                "text",
                {"nested": {"inner_id": 40}},
            ],
        }

        result = seafarer.stringify_id_fields(data)

        assert result["id"] == 10  # не изменён
        assert result["user_id"] == "20"
        assert result["items"][0] == 1
        assert result["items"][1]["item_id"] == "30"
        assert result["items"][1]["value"] == 100
        assert result["items"][2] == "text"
        assert result["items"][3]["nested"]["inner_id"] == "40"

    def test_empty_dict(self, seafarer):
        assert seafarer.stringify_id_fields({}) == {}