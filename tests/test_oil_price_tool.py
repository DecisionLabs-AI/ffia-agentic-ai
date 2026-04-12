"""
Tests for agent/tools/oil_price_tool.py (multi-fuel Bangchak API version).

Real API shape (verified from live endpoint):
  response = [{"OilPriceDate": "10/04/2026", "OilList": "<json-string>", ...}]
  OilList item fields: OilName (str), PriceToday (float)

All tests mock requests.get — no network calls made.
"""

import json
from unittest.mock import MagicMock, patch

from agent.tools.oil_price_tool import (
    _find_fuel,
    _parse_oil_list,
    _resolve_keyword,
    get_oil_price_from_bangchak,
)

_API_URL = "agent.tools.oil_price_tool.requests.get"

_SAMPLE_PRODUCTS = [
    {"OilName": "DIESEL B20",           "PriceToday": 37.40},
    {"OilName": "Hi Diesel S",          "PriceToday": 44.40},
    {"OilName": "Hi Premium Diesel Plus","PriceToday": 66.80},
    {"OilName": "Gasohol E85 S EVO",    "PriceToday": 31.89},
    {"OilName": "Gasohol E20 S EVO",    "PriceToday": 35.95},
    {"OilName": "Gasohol 91 S EVO",     "PriceToday": 42.58},
    {"OilName": "Gasohol 95 S EVO",     "PriceToday": 42.95},
]


def _make_wrapper(products: list, date: str = "10/04/2026") -> dict:
    return {"OilPriceDate": date, "OilList": json.dumps(products)}


def _mock_response(products: list = None, date: str = "10/04/2026") -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    # Use `is not None` so an explicit empty list [] is not replaced by _SAMPLE_PRODUCTS
    mock.json.return_value = [_make_wrapper(products if products is not None else _SAMPLE_PRODUCTS, date)]
    return mock


# ---------------------------------------------------------------------------
# _parse_oil_list
# ---------------------------------------------------------------------------

def test_parse_oil_list_decodes_json_string():
    products = [{"OilName": "DIESEL B20", "PriceToday": 37.40}]
    assert _parse_oil_list({"OilList": json.dumps(products)}) == products


def test_parse_oil_list_handles_missing_key():
    assert _parse_oil_list({}) == []


# ---------------------------------------------------------------------------
# _resolve_keyword — alias mapping
# ---------------------------------------------------------------------------

def test_resolve_keyword_diesel_default():
    assert _resolve_keyword("diesel") == "diesel"

def test_resolve_keyword_thai_diesel():
    assert _resolve_keyword("ดีเซล") == "diesel"

def test_resolve_keyword_g95():
    assert _resolve_keyword("g95") == "gasohol 95"

def test_resolve_keyword_thai_benzin_95():
    assert _resolve_keyword("เบนซิน 95") == "gasohol 95"

def test_resolve_keyword_g91():
    assert _resolve_keyword("g91") == "gasohol 91"

def test_resolve_keyword_thai_benzin_91():
    assert _resolve_keyword("เบนซิน 91") == "gasohol 91"

def test_resolve_keyword_e20():
    assert _resolve_keyword("e20") == "e20"

def test_resolve_keyword_e85():
    assert _resolve_keyword("e85") == "e85"

def test_resolve_keyword_strips_whitespace():
    assert _resolve_keyword("  g95  ") == "gasohol 95"

def test_resolve_keyword_unknown_passes_through():
    assert _resolve_keyword("jet fuel") == "jet fuel"


# ---------------------------------------------------------------------------
# _find_fuel
# ---------------------------------------------------------------------------

def test_find_fuel_matches_diesel_b20():
    result = _find_fuel(_SAMPLE_PRODUCTS, "diesel")
    assert result["OilName"] == "DIESEL B20"

def test_find_fuel_matches_gasohol_95():
    result = _find_fuel(_SAMPLE_PRODUCTS, "gasohol 95")
    assert "95" in result["OilName"]

def test_find_fuel_matches_gasohol_91():
    result = _find_fuel(_SAMPLE_PRODUCTS, "gasohol 91")
    assert "91" in result["OilName"]

def test_find_fuel_matches_e20():
    result = _find_fuel(_SAMPLE_PRODUCTS, "e20")
    assert result["OilName"] == "Gasohol E20 S EVO"

def test_find_fuel_returns_none_when_absent():
    assert _find_fuel(_SAMPLE_PRODUCTS, "jet fuel") is None

def test_find_fuel_is_case_insensitive():
    assert _find_fuel(_SAMPLE_PRODUCTS, "GASOHOL 91") is not None


# ---------------------------------------------------------------------------
# get_oil_price_from_bangchak — happy path
# ---------------------------------------------------------------------------

def test_returns_diesel_price():
    with patch(_API_URL, return_value=_mock_response()):
        result = get_oil_price_from_bangchak("diesel")

    assert result["oil_type"] == "diesel"
    assert result["price_per_liter"] == 37.40
    assert result["updated_at"] == "10/04/2026"


def test_returns_gasohol95_via_alias_g95():
    with patch(_API_URL, return_value=_mock_response()):
        result = get_oil_price_from_bangchak("g95")

    assert result["oil_type"] == "gasohol 95"
    assert result["price_per_liter"] == 42.95


def test_returns_gasohol91_via_thai_alias():
    with patch(_API_URL, return_value=_mock_response()):
        result = get_oil_price_from_bangchak("เบนซิน 91")

    assert result["price_per_liter"] == 42.58


def test_returns_e20():
    with patch(_API_URL, return_value=_mock_response()):
        result = get_oil_price_from_bangchak("e20")

    assert result["price_per_liter"] == 35.95


def test_defaults_to_diesel_when_no_fuel_type():
    with patch(_API_URL, return_value=_mock_response()):
        result = get_oil_price_from_bangchak()

    assert result["oil_type"] == "diesel"


def test_missing_date_returns_na():
    wrapper = {"OilList": json.dumps([{"OilName": "DIESEL B20", "PriceToday": 37.40}])}
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = [wrapper]
    with patch(_API_URL, return_value=mock):
        result = get_oil_price_from_bangchak()

    assert result["updated_at"] == "N/A"
    assert "error" not in result


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_network_error_returns_error_dict():
    with patch(_API_URL, side_effect=Exception("Connection refused")):
        result = get_oil_price_from_bangchak()

    assert "error" in result
    assert "Connection refused" in result["error"]


def test_http_error_returns_error_dict():
    mock = MagicMock()
    mock.raise_for_status.side_effect = Exception("404 Not Found")
    with patch(_API_URL, return_value=mock):
        result = get_oil_price_from_bangchak()

    assert "error" in result


def test_unknown_fuel_type_returns_error():
    with patch(_API_URL, return_value=_mock_response()):
        result = get_oil_price_from_bangchak("jet fuel")

    assert "error" in result
    assert "jet fuel" in result["error"]


def test_missing_price_today_returns_error():
    products = [{"OilName": "DIESEL B20"}]
    with patch(_API_URL, return_value=_mock_response(products)):
        result = get_oil_price_from_bangchak()

    assert "error" in result
    assert "PriceToday" in result["error"]


def test_non_numeric_price_returns_error():
    products = [{"OilName": "DIESEL B20", "PriceToday": "N/A"}]
    with patch(_API_URL, return_value=_mock_response(products)):
        result = get_oil_price_from_bangchak()

    assert "error" in result
    assert "numeric" in result["error"].lower()


def test_empty_oil_list_returns_error():
    with patch(_API_URL, return_value=_mock_response([])):
        result = get_oil_price_from_bangchak()

    assert "error" in result
