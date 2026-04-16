"""
oil_price_tool.py — Fetch latest fuel price from the Bangchak Oil Price API.

API:  https://oil-price.bangchak.co.th/ApiOilPrice2/en
Supports: Diesel, Gasohol 95/91, E20, E85, Hi Diesel S, Hi Premium Diesel Plus.
"""

# Step 1: Minimal imports — no CSV, no pandas, no Google Sheet logic
import json
import warnings
from datetime import datetime

import requests
import urllib3
from langchain_core.tools import tool

# Step 2: Bangchak API endpoint (English locale)
BANGCHAK_API_URL = "https://oil-price.bangchak.co.th/ApiOilPrice2/en"

# Actual response structure (verified from live API):
#   data       → list[dict], take data[0]
#   data[0]["OilList"]      → JSON string  (must json.loads())
#   each product["OilName"] → e.g. "DIESEL B20", "Gasohol 95 S EVO"
#   each product["PriceToday"] → float
#   data[0]["OilPriceDate"] → "10/04/2026"

# Step 3: Alias map — normalised user input → OilName substring keyword
_FUEL_ALIASES: dict[str, str] = {
    # Diesel B20
    "diesel":       "diesel",
    "ดีเซล":        "diesel",
    "b20":          "diesel",
    # Hi Diesel S (ไฮดีเซล S)
    "ไฮดีเซล":      "hi diesel s",
    "ไฮดีเซล s":    "hi diesel s",
    "hi diesel s":  "hi diesel s",
    # Gasohol 95
    "gasohol 95":   "gasohol 95",
    "95":           "gasohol 95",
    "เบนซิน 95":    "gasohol 95",
    "g95":          "gasohol 95",
    # Gasohol 91
    "gasohol 91":   "gasohol 91",
    "91":           "gasohol 91",
    "เบนซิน 91":    "gasohol 91",
    "g91":          "gasohol 91",
    # E20 / E85
    "e20":          "e20",
    "gasohol e20":  "e20",
    "e85":          "e85",
    "gasohol e85":  "e85",
    # Premium diesel grades
    "hi diesel s":          "hi diesel s",
    "hi diesel":            "hi diesel",
    "hi premium diesel":    "hi premium diesel",
}


def _parse_oil_list(wrapper: dict) -> list:
    """Step 4: Decode OilList from JSON string → Python list."""
    raw = wrapper.get("OilList")
    if not raw:
        return []
    return json.loads(raw) if isinstance(raw, str) else raw


def _resolve_keyword(fuel_type: str) -> str:
    """Step 5: Normalise user input to the OilName search keyword."""
    return _FUEL_ALIASES.get(fuel_type.strip().lower(), fuel_type.strip().lower())


def _find_fuel(items: list, keyword: str) -> dict | None:
    """Step 6: Return first product whose OilName contains keyword (case-insensitive)."""
    for item in items:
        if keyword.lower() in str(item.get("OilName") or "").lower():
            return item
    return None


def get_oil_price_from_bangchak(fuel_type: str = "hi diesel s") -> dict:
    """
    Fetch the latest price for a given fuel type from the Bangchak Oil Price API.

    Args:
        fuel_type: English name, Thai alias, or abbreviation.
                   Defaults to "hi diesel s" (ไฮดีเซล S).
                   Examples: "hi diesel s", "ไฮดีเซล", "g95", "เบนซิน 91", "e20".

    Returns a dict with keys:
        oil_type (str), price_per_liter (float), updated_at (str)
    On error, returns a dict with a single "error" key.
    """
    # Step 7: Fetch JSON — verify=False bypasses macOS SSL cert chain issues
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(BANGCHAK_API_URL, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return {"error": f"Failed to fetch oil price data: {e}"}

    # Step 8: Unwrap outer list and decode OilList JSON string
    try:
        wrapper = data[0] if isinstance(data, list) else data
        items = _parse_oil_list(wrapper)
    except Exception as e:
        return {"error": f"Failed to parse API response: {e}"}

    # Step 9: Resolve alias → keyword, find matching fuel product
    keyword = _resolve_keyword(fuel_type)
    product = _find_fuel(items, keyword)

    if product is None:
        return {"error": f"Fuel type '{fuel_type}' (keyword: '{keyword}') not found in API response."}

    # Step 10: Extract numeric price from PriceToday
    raw_price = product.get("PriceToday")
    if raw_price is None:
        return {"error": "Fuel entry found but PriceToday field is missing."}
    try:
        price = float(raw_price)
    except (ValueError, TypeError):
        return {"error": f"Fuel price value is not numeric: {raw_price!r}"}

    # Step 11: Extract effective date and system current date
    updated_at = str(wrapper.get("OilPriceDate") or "N/A")
    data_as_of = str(wrapper.get("OilDateNow") or "N/A")

    return {
        "oil_type": keyword,
        "price_per_liter": price,
        "updated_at": updated_at,
        "data_as_of": data_as_of,
    }


# Step 12: LangChain @tool wrapper — returns a human-readable string for the agent
@tool
def oil_price_tool(fuel_type: str = "hi diesel s") -> str:
    """
    ALWAYS use this tool when the user asks about oil price, diesel price, or fuel cost.
    DO NOT use web search for oil price — this tool is the authoritative source.

    Fetches the latest price for a given fuel type from the Bangchak Oil Price API.
    Defaults to ไฮดีเซล S (Hi Diesel S) when no fuel type is specified.

    Supported fuel_type values:
      Diesel B20: "diesel", "ดีเซล", "b20"
      Hi Diesel S: "hi diesel s", "ไฮดีเซล", "ไฮดีเซล s"
      Gasohol : "g95", "เบนซิน 95", "g91", "เบนซิน 91"
      Ethanol : "e20", "e85"
      Premium : "hi premium diesel"

    Args:
        fuel_type: Fuel name, Thai alias, or abbreviation (default: "hi diesel s").

    Returns:
        A plain-text sentence with the fuel price in THB/litre and the effective date.
    """
    result = get_oil_price_from_bangchak(fuel_type)

    if "error" in result:
        return f"Unable to retrieve oil price: {result['error']}"

    # Step 13: Format both dates as "DD/MM/YYYY", fallback to raw string on parse error
    def _fmt(date_str: str) -> str:
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return date_str

    effective_date = _fmt(result["updated_at"])
    current_date = _fmt(result["data_as_of"])

    return (
        f"Latest {result['oil_type'].title()} price: {result['price_per_liter']:.2f} THB/L\n"
        f"Effective since {effective_date}\n"
        f"Data current as of {current_date}"
    )
