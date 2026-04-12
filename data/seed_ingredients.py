# =============================================================================
# FFIA — data/seed_ingredients.py
# One-time seed script: loads ingredient_market_price.csv into PostgreSQL.
# Run from project root: python3 data/seed_ingredients.py
# Safe to re-run — uses ON CONFLICT DO UPDATE (upsert).
# =============================================================================

# Step 1: Add project root to path so data/ package imports work
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 2: Import DB helpers
from data.db import create_tables, seed_ingredient_market_prices

# Step 3: Resolve CSV path relative to this script's directory
CSV_PATH = Path(__file__).parent / "raw" / "ingredient_market_price.csv"

if __name__ == "__main__":
    # Step 4: Ensure the ingredient_market_prices table exists before seeding
    print("Ensuring tables exist...")
    create_tables()
    print("Tables ready.")

    # Step 5: Seed — upsert all rows from the CSV
    print(f"Seeding from {CSV_PATH} ...")
    n = seed_ingredient_market_prices(str(CSV_PATH))
    print(f"Done — {n} rows upserted into ingredient_market_prices.")
