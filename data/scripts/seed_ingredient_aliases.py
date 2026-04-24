# =============================================================================
# FFIA — data/scripts/seed_ingredient_aliases.py
# One-time seed script: loads ingredient_matching_template.csv into PostgreSQL.
# Run from project root: python3 data/scripts/seed_ingredient_aliases.py
# Safe to re-run — uses ON CONFLICT DO NOTHING on (input_name, canonical_name).
# =============================================================================

# Step 1: Add project root to path so data/ package imports work
import sys
import csv
import psycopg2
import psycopg2.extras
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Step 2: Import DB connection helper
from data.db import get_connection

# Step 3: Resolve CSV path relative to this script's directory
CSV_PATH = Path(__file__).parent.parent / "raw" / "ingredient_matching_template.csv"


def create_ingredient_aliases_table() -> None:
    # Step 4: Create table and unique index if not exists
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ingredient_aliases (
                    id               SERIAL PRIMARY KEY,
                    group_name       TEXT,
                    canonical_name   TEXT NOT NULL,
                    category         TEXT,
                    input_name       TEXT NOT NULL,
                    match_type       TEXT,
                    confidence       TEXT,
                    parent_group     TEXT,
                    child_item       TEXT,
                    usage_context    TEXT,
                    cost_sensitivity TEXT,
                    risk_type        TEXT,
                    business_note    TEXT,
                    oil_sensitive    BOOLEAN DEFAULT FALSE,
                    created_at       TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_ingredient_aliases_input_canonical
                ON ingredient_aliases (input_name, canonical_name)
            """)
        conn.commit()


def seed_ingredient_aliases(csv_path: str) -> int:
    # Step 5: Read CSV — convert oil_sensitive to bool, empty strings to NULL
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            oil_val = row.get("oil_sensitive", "").strip().lower()
            rows.append((
                row.get("group_name", "").strip() or None,
                row["canonical_name"].strip(),
                row.get("category", "").strip() or None,
                row["input_name"].strip(),
                row.get("match_type", "").strip() or None,
                row.get("confidence", "").strip() or None,
                row.get("parent_group", "").strip() or None,
                row.get("child_item", "").strip() or None,
                row.get("usage_context", "").strip() or None,
                row.get("cost_sensitivity", "").strip() or None,
                row.get("risk_type", "").strip() or None,
                row.get("business_note", "").strip() or None,
                oil_val in {"yes", "true", "1"},
            ))

    if not rows:
        return 0

    # Step 6: Bulk insert with ON CONFLICT DO NOTHING
    with get_connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO ingredient_aliases (
                    group_name, canonical_name, category, input_name,
                    match_type, confidence, parent_group, child_item,
                    usage_context, cost_sensitivity, risk_type,
                    business_note, oil_sensitive
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (input_name, canonical_name) DO NOTHING
                """,
                rows,
            )
        conn.commit()
    return len(rows)


if __name__ == "__main__":
    # Step 7: Create table, then seed
    print("Creating ingredient_aliases table if not exists...")
    create_ingredient_aliases_table()
    print("Table ready.")

    print(f"Seeding from {CSV_PATH} ...")
    n = seed_ingredient_aliases(str(CSV_PATH))
    print(f"Done — {n} rows inserted into ingredient_aliases.")
