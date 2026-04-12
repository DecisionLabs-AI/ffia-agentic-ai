"""
ingredient_price_tool.py — Look up Thai ingredient market reference prices.

Data: ingredient_market_prices table (seeded from data/raw/ingredient_market_price.csv).
Sources:
  - Ministry of Commerce (MOC-*): meats, eggs, seafood, vegetables, oils, fruits, rice
  - Makro (MAK-*): packaging and disposables
"""

# Step 1: Imports
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()


# Step 2: DB connection helper — reads DATABASE_URL on demand
def _get_database_url() -> str | None:
    return os.getenv("DATABASE_URL")


# Step 3: Core query — returns up to `limit` rows matching the keyword (ILIKE)
def search_ingredient_prices(keyword: str, limit: int = 5) -> list[dict]:
    """
    Search ingredient_market_prices by partial name match.

    Args:
        keyword: Thai or English ingredient name fragment.
        limit:   Max rows to return.

    Returns:
        List of dicts with keys: id, ingredient, avg_market_price, unit, source.
        Returns an empty list on no match or DB error.
    """
    database_url = _get_database_url()
    if not database_url:
        return []

    try:
        # Step 3a: Open connection and run ILIKE search — no tenant scoping needed
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, ingredient, avg_market_price, unit, source
                    FROM ingredient_market_prices
                    WHERE ingredient ILIKE %s
                    ORDER BY source, ingredient
                    LIMIT %s
                    """,
                    (f"%{keyword.strip()}%", limit),
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception:
        return []


# Step 4: LangChain @tool wrapper — returns a human-readable string for the agent
@tool
def ingredient_price_tool(keyword: str) -> str:
    """
    Look up Thai ingredient or packaging market reference prices by name or keyword.
    Use this tool when the user asks about ingredient costs, food raw material prices,
    or packaging material costs.

    Data sources (updated from official government and wholesale data):
      - Ministry of Commerce: meats, eggs, seafood, vegetables, oils, fruits, rice
      - Makro: packaging materials and disposables

    Args:
        keyword: Ingredient name (Thai or English) or any partial keyword.
                 Examples: "ไก่", "กุ้งขาว", "ข้าว", "น้ำมันปาล์ม", "หมู", "ผักคะน้า"

    Returns:
        Formatted list of matching ingredients with price per unit and data source.
    """
    # Step 4a: Query the DB for up to 5 matching rows
    results = search_ingredient_prices(keyword, limit=5)

    if not results:
        return (
            f"No ingredient price found for '{keyword}'. "
            "Try a shorter keyword or search in Thai (e.g. 'ไก่' for chicken)."
        )

    # Step 4b: Format as a readable bullet list
    lines = [f"Ingredient prices matching '{keyword}' (THB):"]
    for row in results:
        lines.append(
            f"  - {row['ingredient']}: {float(row['avg_market_price']):.2f} ฿/{row['unit']}"
            f"  [{row['source']}]"
        )
    return "\n".join(lines)
