# =============================================================================
# FFIA — data/db.py
# PostgreSQL connection helpers and invoice CRUD for the Streamlit UI.
# Agent read-only queries live separately in agent/tools/postgres_tool.py.
# =============================================================================

# Step 1: Imports
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# Step 2: Read DATABASE_URL from environment (never hardcoded)
_DATABASE_URL = os.getenv("DATABASE_URL")


# Step 3: Connection helper
def get_connection():
    """Return a psycopg2 connection using DATABASE_URL from .env."""
    if not _DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to your .env file.\n"
            "Format: postgresql://user:password@host:5432/dbname"
        )
    return psycopg2.connect(_DATABASE_URL)


# Step 4: Schema creation — idempotent, safe to call on every app startup
def create_tables():
    """Create invoices and invoice_items tables if they do not already exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Step 4a: Invoice header table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id           SERIAL PRIMARY KEY,
                    vendor       TEXT NOT NULL,
                    invoice_no   TEXT UNIQUE NOT NULL,
                    invoice_date DATE NOT NULL,
                    total_amount NUMERIC(12, 2) NOT NULL,
                    created_at   TIMESTAMP DEFAULT NOW()
                )
            """)

            # Step 4b: Invoice line items table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS invoice_items (
                    id          SERIAL PRIMARY KEY,
                    invoice_id  INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
                    name        TEXT NOT NULL,
                    qty         NUMERIC(10, 3) NOT NULL,
                    unit_price  NUMERIC(12, 2) NOT NULL,
                    total       NUMERIC(12, 2) NOT NULL
                )
            """)

            # Step 4c: Ensure unique index on invoice_no (idempotent — handles tables
            # created before the UNIQUE constraint was added to the schema)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_invoice_no
                ON invoices(invoice_no)
            """)

            # Step 4d: Backfill any columns that may be missing from older table versions
            for _col, _def in [
                ("name",       "TEXT NOT NULL DEFAULT ''"),
                ("qty",        "NUMERIC(10, 3) NOT NULL DEFAULT 0"),
                ("unit_price", "NUMERIC(12, 2) NOT NULL DEFAULT 0"),
                ("total",      "NUMERIC(12, 2) NOT NULL DEFAULT 0"),
            ]:
                cur.execute(f"""
                    ALTER TABLE invoice_items
                    ADD COLUMN IF NOT EXISTS {_col} {_def}
                """)
        conn.commit()


# Step 5: Duplicate check — used by the UI before saving
def invoice_exists(invoice_no: str) -> bool:
    """Return True if an invoice with this invoice_no already exists."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM invoices WHERE invoice_no = %s LIMIT 1",
                (invoice_no,),
            )
            return cur.fetchone() is not None


# Step 6: Save invoice — insert a new invoice and its items
def save_invoice(
    vendor: str,
    invoice_no: str,
    invoice_date,
    total_amount: float,
    items: list[dict],
) -> int:
    """
    Persist an invoice header and its line items to PostgreSQL.

    Args:
        vendor:       Supplier name
        invoice_no:   Unique invoice reference number
        invoice_date: Date object or ISO string (YYYY-MM-DD)
        total_amount: Total invoice amount in THB
        items:        List of dicts with keys: name, qty, unit_price, total

    Returns:
        int: The invoice id (primary key)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Step 6a: Insert invoice header
            cur.execute(
                """
                INSERT INTO invoices (vendor, invoice_no, invoice_date, total_amount)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (vendor, invoice_no, invoice_date, total_amount),
            )
            invoice_id = cur.fetchone()[0]

            # Step 6b: Bulk insert line items
            if items:
                psycopg2.extras.execute_batch(
                    cur,
                    """
                    INSERT INTO invoice_items (invoice_id, name, qty, unit_price, total)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            invoice_id,
                            row.get("name", ""),
                            float(row.get("qty", 0)),
                            float(row.get("unit_price", 0)),
                            float(row.get("total", 0)),
                        )
                        for row in items
                    ],
                )

        conn.commit()
    return invoice_id


# Step 7: Fetch the latest invoice with its line items for agent context
def get_latest_invoice() -> dict | None:
    """
    Return the most recently created invoice and its line items.

    Returns:
        dict with invoice header fields plus `items`, or None if no invoice exists.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, vendor, invoice_no, invoice_date, total_amount, created_at
                FROM invoices
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            invoice = cur.fetchone()
            if not invoice:
                return None

            invoice_data = dict(invoice)
            cur.execute(
                """
                SELECT name, qty, unit_price, total
                FROM invoice_items
                WHERE invoice_id = %s
                ORDER BY id ASC
                """,
                (invoice_data["id"],),
            )
            invoice_data["items"] = [dict(row) for row in cur.fetchall()]
            return invoice_data


# Step 8: Fetch recent invoices for display in the UI
def get_recent_invoices(limit: int = 10) -> list[dict]:
    """
    Return the most recently created invoices.

    Returns:
        List of dicts with keys: id, vendor, invoice_no, invoice_date,
        total_amount, created_at
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, vendor, invoice_no, invoice_date, total_amount, created_at
                FROM invoices
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


# Step 9: Standalone test block
if __name__ == "__main__":
    print("Creating tables...")
    create_tables()
    print("Tables ready.")

    print("Saving test invoice...")
    if invoice_exists("TEST-001"):
        print("Invoice TEST-001 already exists.")
    else:
        inv_id = save_invoice(
            vendor="Bangchak",
            invoice_no="TEST-001",
            invoice_date="2026-04-06",
            total_amount=2450.00,
            items=[
                {"name": "Diesel 50L", "qty": 50, "unit_price": 29.94, "total": 1497.00},
                {"name": "Gasohol 91 20L", "qty": 20, "unit_price": 31.28, "total": 625.60},
            ],
        )
        print(f"Saved — invoice id: {inv_id}")

    print("Recent invoices:")
    for row in get_recent_invoices():
        print(" ", row)

    print("Latest invoice:")
    print(get_latest_invoice())
