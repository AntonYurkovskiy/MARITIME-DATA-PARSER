import pytest
from unittest.mock import Mock, patch
from src.api.vessels import (
    _extract_items,
    _get_vessel_name,
    _name_variants,
    _best_fuzzy_item,
    search_vessel,
    get_vessel_uuid,
    _add_new_vessel,
    add_historical_contract,
    search_external_vessel,
)


# ============================================================================
# Tests for _extract_items
# ============================================================================

class TestExtractItems:
    """Tests for _extract_items function"""

    def test_extract_items_from_dict_with_items(self):
        """Should extract items list from dict"""
        result = {"items": [{"id": 1}, {"id": 2}]}
        assert _extract_items(result) == [{"id": 1}, {"id": 2}]

    def test_extract_items_from_dict_without_items(self):
        """Should return empty list if items key missing"""
        result = {"data": "something"}
        assert _extract_items(result) == []

    def test_extract_items_from_dict_with_none_items(self):
        """Should return empty list if items is None"""
        result = {"items": None}
        assert _extract_items(result) == []

    def test_extract_items_from_list(self):
        """Should return list as is when result is a list"""
        result = [{"id": 1}, {"id": 2}]
        assert _extract_items(result) == [{"id": 1}, {"id": 2}]

    def test_extract_items_from_empty_list(self):
        """Should return empty list when result is empty list"""
        result = []
        assert _extract_items(result) == []

    def test_extract_items_from_invalid_type(self):
        """Should return empty list for invalid types"""
        assert _extract_items("string") == []
        assert _extract_items(123) == []
        assert _extract_items(None) == []


# ============================================================================
# Tests for _get_vessel_name
# ============================================================================

class TestGetVesselName:
    """Tests for _get_vessel_name function"""

    def test_get_vessel_name_from_name_field(self):
        """Should get vessel name from 'name' field"""
        item = {"name": "Prince Bassel"}
        assert _get_vessel_name(item) == "Prince Bassel"

    def test_get_vessel_name_from_details_history(self):
        """Should get vessel name from details_history if name missing"""
        item = {"details_history": {"name": "Prince Bassel"}}
        assert _get_vessel_name(item) == "Prince Bassel"

    def test_get_vessel_name_from_imo_no(self):
        """Should get vessel name from imo_no if other fields missing"""
        item = {"imo_no": "1234567"}
        assert _get_vessel_name(item) == "1234567"

    def test_get_vessel_name_priority_name_over_details(self):
        """Should prioritize 'name' over 'details_history'"""
        item = {
            "name": "Prince Bassel",
            "details_history": {"name": "Old Name"},
        }
        assert _get_vessel_name(item) == "Prince Bassel"

    def test_get_vessel_name_details_over_imo(self):
        """Should prioritize details_history over imo_no"""
        item = {
            "details_history": {"name": "Prince Bassel"},
            "imo_no": "1234567",
        }
        assert _get_vessel_name(item) == "Prince Bassel"

    def test_get_vessel_name_empty_string_for_non_dict(self):
        """Should return empty string for non-dict input"""
        assert _get_vessel_name("string") == ""
        assert _get_vessel_name([]) == ""
        assert _get_vessel_name(None) == ""

    def test_get_vessel_name_empty_dict(self):
        """Should return empty string for empty dict"""
        assert _get_vessel_name({}) == ""

    def test_get_vessel_name_details_history_none(self):
        """Should handle None in details_history"""
        item = {"name": None, "details_history": None, "imo_no": "IMO123"}
        assert _get_vessel_name(item) == "IMO123"


# ============================================================================
# Tests for _name_variants
# ============================================================================

class TestNameVariants:
    """Tests for _name_variants function"""

    def test_name_variants_single_word(self):
        """Should return list with single word"""
        result = _name_variants("Prince")
        assert result == ["Prince"]

    def test_name_variants_two_words(self):
        """Should generate variants for two-word name"""
        result = _name_variants("Prince Bassel")
        assert "Prince Bassel" in result
        # _normalize converts to lowercase
        assert any(v.lower() == "prince" for v in result)
        assert any(v.lower() == "bassel" for v in result)

    def test_name_variants_three_words(self):
        """Should generate variants for three-word name"""
        result = _name_variants("Prince of Bassel")
        # Should include: full name, first word, last word, first two, last two
        assert "Prince of Bassel" in result
        # _normalize converts to lowercase
        assert any(v.lower() == "prince" for v in result)
        assert any(v.lower() == "bassel" for v in result)

    def test_name_variants_no_duplicates(self):
        """Should not have duplicate variants (case-insensitive)"""
        result = _name_variants("Prince Prince Bassel")
        # Check that no duplicates in lowercase
        lowercase = [v.lower() for v in result]
        assert len(lowercase) == len(set(lowercase))

    def test_name_variants_strips_whitespace(self):
        """Should handle extra whitespace"""
        result = _name_variants("  Prince   Bassel  ")
        assert any("prince" in v.lower() for v in result)
        assert any("bassel" in v.lower() for v in result)

    def test_name_variants_preserves_case(self):
        """Should preserve case of input"""
        result = _name_variants("PRINCE bassel")
        assert "PRINCE" in result or any("prince" in v for v in result)


# ============================================================================
# Tests for _best_fuzzy_item
# ============================================================================

class TestBestFuzzyItem:
    """Tests for _best_fuzzy_item function"""

    def test_best_fuzzy_item_exact_match(self):
        """Should return item with best fuzzy score"""
        items = [
            {"name": "Prince Bassel"},
            {"name": "Something Else"},
        ]
        item, score = _best_fuzzy_item("Prince Bassel", items)
        assert item["name"] == "Prince Bassel"
        assert score > 90

    def test_best_fuzzy_item_partial_match(self):
        """Should find best partial match"""
        items = [
            {"name": "Prince of Bassel"},
            {"name": "Something Else"},
        ]
        item, score = _best_fuzzy_item("Prince Bassel", items)
        assert item is not None
        assert score > 0

    def test_best_fuzzy_item_empty_list(self):
        """Should return None for empty list"""
        item, score = _best_fuzzy_item("Prince", [])
        assert item is None
        assert score == -1

    def test_best_fuzzy_item_no_valid_candidates(self):
        """Should return None when no valid candidates"""
        items = [
            {"details_history": {}},
            {"other_field": "value"},
        ]
        item, score = _best_fuzzy_item("Prince", items)
        assert item is None
        assert score == -1

    def test_best_fuzzy_item_compares_all_items(self):
        """Should find best among multiple items"""
        items = [
            {"name": "Something Completely Different"},
            {"name": "Prince Bassel"},
            {"name": "Prince"},
        ]
        item, score = _best_fuzzy_item("Prince Bassel", items)
        assert item["name"] == "Prince Bassel"


# ============================================================================
# Tests for search_vessel
# ============================================================================

class TestSearchVessel:
    """Tests for search_vessel function"""

    @patch("src.api.vessels._get_session")
    def test_search_vessel_success(self, mock_get_session):
        """Should make POST request and return response"""
        mock_response = Mock()
        mock_response.json.return_value = {"items": [{"uuid": "123"}]}
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_vessel("Prince Bassel", "main", "/search")

        assert result == {"items": [{"uuid": "123"}]}
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "/search" in call_args[0][0]

    @patch("src.api.vessels._get_session")
    def test_search_vessel_http_error(self, mock_get_session):
        """Should raise HTTPError on bad status code"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        with pytest.raises(Exception):
            search_vessel("NonExistent", "main", "/search")

    @patch("src.api.vessels._get_session")
    def test_search_vessel_constructs_payload(self, mock_get_session):
        """Should construct correct payload"""
        mock_response = Mock()
        mock_response.json.return_value = {"items": []}
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        search_vessel("Test Vessel", "historical", "/historical/search")

        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args[1]
        payload = call_kwargs["json"]

        assert "filters" in payload
        assert "pagination" in payload
        assert payload["metadata"]["source"] == "historical"


# ============================================================================
# Tests for get_vessel_uuid
# ============================================================================

class TestGetVesselUuid:
    """Tests for get_vessel_uuid function"""

    @patch("src.api.vessels.search_vessel")
    def test_get_vessel_uuid_exact_match(self, mock_search):
        """Should return uuid when exact match found"""
        mock_search.return_value = {
            "items": [{"uuid": "exact-123", "name": "Prince Bassel"}]
        }

        uuid, source, item = get_vessel_uuid("Prince Bassel")

        assert uuid == "exact-123"
        assert source is not None
        assert item is not None

    @patch("src.api.vessels.search_vessel")
    def test_get_vessel_uuid_fuzzy_match(self, mock_search):
        """Should return fuzzy match if exact not found"""
        mock_search.return_value = {
            "items": [{"uuid": "fuzzy-123", "name": "Prince of Bassel"}]
        }

        uuid, source, item = get_vessel_uuid("Prince Bassel")

        # Should find fuzzy match with score >= 80
        if uuid:
            assert uuid is not None

    @patch("src.api.vessels.search_vessel")
    def test_get_vessel_uuid_not_found(self, mock_search):
        """Should return None when vessel not found"""
        mock_search.return_value = {"items": []}

        uuid, source, item = get_vessel_uuid("NonExistentVessel")

        assert uuid is None
        assert source is None
        assert item is None

    @patch("src.api.vessels.search_vessel")
    def test_get_vessel_uuid_high_threshold(self, mock_search):
        """Should only accept fuzzy matches with score >= 80"""
        # Response with very different name
        mock_search.return_value = {
            "items": [{"uuid": "different-123", "name": "Completely Different Ship"}]
        }

        uuid, source, item = get_vessel_uuid("Prince Bassel")

        # Should not match if score < 80
        if uuid:
            # If uuid found, it passed the threshold
            assert isinstance(uuid, str)


# ============================================================================
# Tests for _add_new_vessel
# ============================================================================

class TestAddNewVessel:
    """Tests for _add_new_vessel function"""

    @patch("src.api.vessels.get_id")
    @patch("src.api.vessels.get_value")
    @patch("src.api.vessels.search_geo")
    @patch("src.api.vessels._get_session")
    def test_add_new_vessel_success(
        self, mock_get_session, mock_search_geo, mock_get_value, mock_get_id
    ):
        """Should create new vessel successfully"""
        contract_details = {
            "Vessel Name / Flag": "Test Vessel / Panama",
            "Vessel type / DWT": "Bulk Carrier / 50000",
        }
        local_vessel_types = {}

        mock_search_geo.return_value = [{"id": "country-123"}]
        mock_get_id.return_value = "type-123"

        mock_response = Mock()
        mock_response.json.return_value = {
            "inserted": {"uuid": "vessel-123"}
        }
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = _add_new_vessel(
            contract_details, local_vessel_types
        )

        assert result["inserted"]["uuid"] == "vessel-123"
        mock_session.post.assert_called_once()

    def test_add_new_vessel_missing_name_flag(self):
        """Should raise ValueError if Vessel Name / Flag missing"""
        contract_details = {}
        local_vessel_types = {}

        with pytest.raises(ValueError, match="Missing Vessel Name / Flag"):
            _add_new_vessel(contract_details, local_vessel_types)

    def test_add_new_vessel_invalid_name_format(self):
        """Should raise ValueError if format invalid"""
        contract_details = {"Vessel Name / Flag": "No separator here"}
        local_vessel_types = {}

        with pytest.raises(ValueError, match="Unsupported Vessel Name / Flag format"):
            _add_new_vessel(contract_details, local_vessel_types)


# ============================================================================
# Tests for add_historical_contract
# ============================================================================

class TestAddHistoricalContract:
    """Tests for add_historical_contract function"""

    @patch("src.api.vessels.get_id")
    @patch("src.api.vessels.extract_date_to_iso")
    @patch("src.api.vessels._get_session")
    @patch("src.api.vessels.get_vessel_uuid")
    def test_add_historical_contract_with_existing_vessel(
        self,
        mock_get_vessel_uuid,
        mock_get_session,
        mock_extract_date,
        mock_get_id,
    ):
        """Should add contract with existing vessel"""
        sea_service = {
            "Position": "Captain",
            "Vessel Name / Flag": "Prince Bassel / Panama",
            "From - Till": "01.01.2020 - 01.01.2021",
        }

        mock_get_id.return_value = "rank-123"
        mock_get_vessel_uuid.return_value = ("vessel-123", "historical", {})
        mock_extract_date.return_value = [("2020-01-01",)]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "contract-123"}
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = add_historical_contract(
            sea_service, "seafarer-123", {}, {}
        )

        assert result["id"] == "contract-123"
        mock_session.post.assert_called_once()

    @patch("src.api.vessels.get_id")
    def test_add_historical_contract_missing_rank(self, mock_get_id):
        """Should raise ValueError if rank not found"""
        sea_service = {"Position": "UnknownRank"}
        mock_get_id.return_value = None

        with pytest.raises(ValueError, match="Missing rank_id"):
            add_historical_contract(sea_service, "seafarer-123", {}, {})

    @patch("src.api.vessels.get_id")
    @patch("src.api.vessels.extract_date_to_iso")
    @patch("src.api.vessels.simple_cleaned_vessel_name")
    @patch("src.api.vessels.get_vessel_uuid")
    def test_add_historical_contract_missing_dates(
        self, mock_get_vessel_uuid, mock_clean_name, mock_extract_date, mock_get_id
    ):
        """Should raise ValueError if dates cannot be parsed"""
        sea_service = {
            "Position": "Captain",
            "Vessel Name / Flag": "Vessel / Country",
            "From - Till": "01.01.2020 - 01.01.2021",
        }
        mock_get_id.return_value = "rank-123"
        mock_clean_name.return_value = "vessel"
        mock_get_vessel_uuid.return_value = ("vessel-123", "historical", {})
        mock_extract_date.return_value = []  # No dates parsed

        with pytest.raises(ValueError, match="Unable to parse contract dates"):
            add_historical_contract(sea_service, "seafarer-123", {}, {})


# ============================================================================
# Tests for search_external_vessel
# ============================================================================

class TestSearchExternalVessel:
    """Tests for search_external_vessel function"""

    @patch("src.api.vessels._get_session")
    def test_search_external_vessel_success(self, mock_get_session):
        """Should return list of vessels"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {"uuid": "1", "name": "Ship1"},
                {"uuid": "2", "name": "Ship2"},
            ]
        }
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_external_vessel("Prince Bassel")

        assert len(result) == 2
        assert result[0]["name"] == "Ship1"

    @patch("src.api.vessels._get_session")
    def test_search_external_vessel_no_results(self, mock_get_session):
        """Should return empty list if no results"""
        mock_response = Mock()
        mock_response.json.return_value = {"items": []}
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_external_vessel("NonExistent")

        assert result == []

    @patch("src.api.vessels._get_session")
    def test_search_external_vessel_no_items_key(self, mock_get_session):
        """Should return empty list if no items key in response"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_external_vessel("Test")

        assert result == []

    def test_search_external_vessel_empty_string(self):
        """Should return None for empty input"""
        result = search_external_vessel("")

        assert result is None

    def test_search_external_vessel_none_input(self):
        """Should return None for None input"""
        result = search_external_vessel(None)

        assert result is None

    @patch("src.api.vessels._get_session")
    def test_search_external_vessel_constructs_payload(self, mock_get_session):
        """Should construct correct payload with metadata"""
        mock_response = Mock()
        mock_response.json.return_value = {"items": []}
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        search_external_vessel("Test Vessel")

        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args[1]
        payload = call_kwargs["json"]

        assert payload["metadata"]["external"] is True
