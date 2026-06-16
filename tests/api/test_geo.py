from unittest.mock import Mock, patch
from src.api.geo import (
    search_geo,
    search_geo_exact,
    search_geo_dict,
    get_resident_country,
    resolve_country_by_code,
)


# ============================================================================
# Tests for search_geo
# ============================================================================

class TestSearchGeo:
    """Tests for search_geo function"""

    @patch("src.api.geo._get_session")
    def test_search_geo_success_countries(self, mock_get_session):
        """Should return list of countries"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "name": "Panama", "code": "PA"},
            {"id": 2, "name": "Panama City", "code": "PC"},
        ]
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_geo("Panama", "countries")

        assert len(result) == 2
        assert result[0]["name"] == "Panama"
        mock_session.get.assert_called_once()

    @patch("src.api.geo._get_session")
    def test_search_geo_success_cities(self, mock_get_session):
        """Should search cities with correct URL"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "Panama City"}]
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_geo("Panama", "cities")

        assert result[0]["name"] == "Panama City"
        call_args = mock_session.get.call_args[0][0]
        assert "/geo/cities/search/" in call_args

    @patch("src.api.geo._get_session")
    def test_search_geo_empty_input(self, mock_get_session):
        """Should return None for empty search term"""
        result = search_geo("", "countries")

        assert result is None
        mock_get_session.assert_not_called()

    @patch("src.api.geo._get_session")
    def test_search_geo_none_input(self, mock_get_session):
        """Should return None for None input"""
        result = search_geo(None, "countries")

        assert result is None
        mock_get_session.assert_not_called()

    @patch("src.api.geo._get_session")
    def test_search_geo_http_error(self, mock_get_session):
        """Should return empty list on HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_geo("NonExistent", "countries")

        assert result == []

    @patch("src.api.geo._get_session")
    def test_search_geo_custom_geo_type(self, mock_get_session):
        """Should handle custom geo_type"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1}]
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_geo("test", "vessels")

        assert result == [{"id": 1}]
        call_args = mock_session.get.call_args[0][0]
        assert "/vessels/search/" in call_args


# ============================================================================
# Tests for search_geo_exact
# ============================================================================

class TestSearchGeoExact:
    """Tests for search_geo_exact function"""

    @patch("src.api.geo.search_geo")
    def test_search_geo_exact_single_match(self, mock_search_geo):
        """Should return exact match"""
        mock_search_geo.return_value = [
            {"name": "Panama", "id": 1},
            {"name": "Panama City", "id": 2},
        ]

        result = search_geo_exact("Panama", "countries")

        assert len(result) == 1
        assert result[0]["name"] == "Panama"

    @patch("src.api.geo.search_geo")
    def test_search_geo_exact_case_insensitive(self, mock_search_geo):
        """Should match case-insensitively"""
        mock_search_geo.return_value = [
            {"name": "PANAMA", "id": 1},
            {"name": "Panama City", "id": 2},
        ]

        result = search_geo_exact("panama", "countries")

        assert len(result) == 1
        assert result[0]["name"] == "PANAMA"

    @patch("src.api.geo.search_geo")
    def test_search_geo_exact_no_match(self, mock_search_geo):
        """Should return empty list if no exact match"""
        mock_search_geo.return_value = [
            {"name": "Panama City", "id": 1},
            {"name": "New Panama", "id": 2},
        ]

        result = search_geo_exact("Panama", "countries")

        assert result == []

    @patch("src.api.geo.search_geo")
    def test_search_geo_exact_empty_results(self, mock_search_geo):
        """Should return empty list for empty search results"""
        mock_search_geo.return_value = []

        result = search_geo_exact("NonExistent", "countries")

        assert result == []

    @patch("src.api.geo.search_geo")
    def test_search_geo_exact_whitespace_handling(self, mock_search_geo):
        """Should handle whitespace in names"""
        mock_search_geo.return_value = [
            {"name": "  Panama  ", "id": 1},
            {"name": "Panama City", "id": 2},
        ]

        result = search_geo_exact("Panama", "countries")

        assert len(result) == 1
        assert result[0]["id"] == 1


# ============================================================================
# Tests for search_geo_dict
# ============================================================================

class TestSearchGeoDict:
    """Tests for search_geo_dict function"""

    @patch("src.api.geo._get_session")
    def test_search_geo_dict_success(self, mock_get_session):
        """Should return complete geo dictionary"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "name": "Panama"},
            {"id": 2, "name": "Poland"},
        ]
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_geo_dict("countries")

        assert len(result) == 2
        assert result[0]["name"] == "Panama"

    @patch("src.api.geo._get_session")
    def test_search_geo_dict_geo_types(self, mock_get_session):
        """Should construct correct URL for different geo_types"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        search_geo_dict("regions")

        call_args = mock_session.get.call_args[0][0]
        assert "/geo/regions/search/" in call_args

    @patch("src.api.geo._get_session")
    def test_search_geo_dict_http_error(self, mock_get_session):
        """Should handle HTTP errors"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = search_geo_dict("countries")

        assert result is None


# ============================================================================
# Tests for get_resident_country
# ============================================================================

class TestGetResidentCountry:
    """Tests for get_resident_country function"""

    def test_get_resident_country_with_slash_separator(self):
        """Should extract country from slash-separated string"""
        result = get_resident_country("Panama / Egypt", "Egypt")

        assert result.strip() == "Panama"

    @patch("src.api.geo.search_geo_exact")
    @patch("src.api.geo.only_letters_regex")
    def test_get_resident_country_exact_match_in_dictionary(
        self, mock_only_letters, mock_search_geo_exact
    ):
        """Should search exact matches if not in COUNTRY_TO_LANGUAGE"""
        mock_only_letters.return_value = True
        mock_search_geo_exact.return_value = [
            {"country": {"name": "Egypt"}, "name": "Cairo"}
        ]

        result = get_resident_country("UnknownCountry", None)

        assert result == "Egypt"
        mock_search_geo_exact.assert_called_once_with("UnknownCountry")

    @patch("src.api.geo.search_geo_exact")
    @patch("src.api.geo.only_letters_regex")
    def test_get_resident_country_single_exact_match(
        self, mock_only_letters, mock_search_geo_exact
    ):
        """Should return country from exact match"""
        mock_only_letters.return_value = True
        mock_search_geo_exact.return_value = [
            {"country": {"name": "Panama"}, "name": "Panama City"}
        ]

        result = get_resident_country("Panama", None)

        assert result == "Panama"

    @patch("src.api.geo.search_geo_exact")
    @patch("src.api.geo.only_letters_regex")
    def test_get_resident_country_multiple_matches_with_citizenship(
        self, mock_only_letters, mock_search_geo_exact
    ):
        """Should return citizenship if in multiple matches"""
        mock_only_letters.return_value = True
        mock_search_geo_exact.return_value = [
            {"country": {"name": "Panama"}, "name": "Panama City"},
            {"country": {"name": "Egypt"}, "name": "New Cairo"},
        ]

        result = get_resident_country("Panama", "Egypt")

        assert result == "Egypt"

    @patch("src.api.geo.only_letters_regex")
    def test_get_resident_country_not_letters(self, mock_only_letters):
        """Should return None if search_term contains non-letters"""
        mock_only_letters.return_value = False

        result = get_resident_country("123", "Egypt")

        assert result is None

    def test_get_resident_country_empty_input(self):
        """Should return None for empty search_term"""
        result = get_resident_country("", "Egypt")

        assert result is None

    def test_get_resident_country_none_input(self):
        """Should return None for None input"""
        result = get_resident_country(None, "Egypt")

        assert result is None


# ============================================================================
# Tests for resolve_country_by_code
# ============================================================================

class TestResolveCountryByCode:
    """Tests for resolve_country_by_code function"""

    def test_resolve_country_by_code_single_result(self):
        """Should return single result without ambiguity"""
        mock_search_geo = Mock(return_value=[
            {"id": "PA", "name": "Panama", "dial_code": "+507"}
        ])

        result = resolve_country_by_code("PA", None, None, mock_search_geo)

        assert result["country_id"] == "PA"
        assert result["dial_code"] == "+507"
        assert result["is_ambiguous"] is False
        assert len(result["matches"]) == 1

    def test_resolve_country_by_code_resident_country_match(self):
        """Should prefer resident_country_id in multiple results"""
        mock_search_geo = Mock(return_value=[
            {"id": "PA", "name": "Panama", "dial_code": "+507"},
            {"id": "EG", "name": "Egypt", "dial_code": "+20"},
        ])

        result = resolve_country_by_code("PA", "PA", "EG", mock_search_geo)

        assert result["country_id"] == "PA"
        assert result["is_ambiguous"] is True
        assert len(result["matches"]) == 2

    def test_resolve_country_by_code_nationality_country_match(self):
        """Should use nationality_country_id if resident not found"""
        mock_search_geo = Mock(return_value=[
            {"id": "PA", "name": "Panama", "dial_code": "+507"},
            {"id": "EG", "name": "Egypt", "dial_code": "+20"},
        ])

        result = resolve_country_by_code("PA", None, "EG", mock_search_geo)

        assert result["country_id"] == "EG"
        assert result["is_ambiguous"] is True

    def test_resolve_country_by_code_first_result_fallback(self):
        """Should use first result as fallback"""
        mock_search_geo = Mock(return_value=[
            {"id": "PA", "name": "Panama", "dial_code": "+507"},
            {"id": "EG", "name": "Egypt", "dial_code": "+20"},
        ])

        result = resolve_country_by_code("PA", "XX", "YY", mock_search_geo)

        assert result["country_id"] == "PA"
        assert result["is_ambiguous"] is True

    def test_resolve_country_by_code_no_results(self):
        """Should return None values when no results"""
        mock_search_geo = Mock(return_value=[])

        result = resolve_country_by_code("XX", None, None, mock_search_geo)

        assert result["country_id"] is None
        assert result["dial_code"] is None
        assert result["is_ambiguous"] is True
        assert result["matches"] == []

    def test_resolve_country_by_code_empty_results(self):
        """Should handle None from search_geo"""
        mock_search_geo = Mock(return_value=None)

        result = resolve_country_by_code("XX", None, None, mock_search_geo)

        assert result["country_id"] is None
        assert result["dial_code"] is None
        assert result["is_ambiguous"] is True
        assert result["matches"] == []

    def test_resolve_country_by_code_calls_search_func(self):
        """Should call search_geo_func with correct parameters"""
        mock_search_geo = Mock(return_value=[
            {"id": "PA", "name": "Panama", "dial_code": "+507"}
        ])

        resolve_country_by_code("PA", None, None, mock_search_geo)

        mock_search_geo.assert_called_once_with("PA", "countries")
