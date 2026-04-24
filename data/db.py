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
from app.utils.auth import get_legacy_owner_user_id

load_dotenv()

# Step 2: Runtime config getter — reads DATABASE_URL on demand, not at import time.
# This ensures .env changes are picked up without restarting Streamlit.
def _get_database_url() -> str | None:
    return os.getenv("DATABASE_URL")


# Step 3: Connection helper
def _require_user_id(user_id: str) -> str:
    """Return a validated tenant identifier."""
    normalized = str(user_id or "").strip()
    if not normalized:
        raise ValueError("Authenticated user_id is required for invoice access.")
    return normalized


def _apply_user_context(conn, user_id: str) -> None:
    """Bind the current PostgreSQL session to a tenant for RLS enforcement."""
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", (user_id,))


def get_connection(user_id: str | None = None):
    """Return a psycopg2 connection using DATABASE_URL from .env."""
    database_url = _get_database_url()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to your .env file.\n"
            "Format: postgresql://user:password@host:5432/dbname"
        )
    conn = psycopg2.connect(database_url)
    if user_id:
        _apply_user_context(conn, _require_user_id(user_id))
    return conn


# Step 4: Schema creation — idempotent, safe to call on every app startup
def create_tables():
    """Create invoices and invoice_items tables if they do not already exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Step 4a: Invoice header table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id           SERIAL PRIMARY KEY,
                    user_id      TEXT,
                    vendor       TEXT NOT NULL,
                    invoice_no   TEXT NOT NULL,
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
                    user_id     TEXT,
                    name        TEXT NOT NULL,
                    qty         NUMERIC(10, 3) NOT NULL,
                    unit_price  NUMERIC(12, 2) NOT NULL,
                    total       NUMERIC(12, 2) NOT NULL
                )
            """)

            # Step 4c: Temporarily disable RLS while running schema maintenance
            cur.execute("ALTER TABLE invoices NO FORCE ROW LEVEL SECURITY")
            cur.execute("ALTER TABLE invoices DISABLE ROW LEVEL SECURITY")
            cur.execute("ALTER TABLE invoice_items NO FORCE ROW LEVEL SECURITY")
            cur.execute("ALTER TABLE invoice_items DISABLE ROW LEVEL SECURITY")

            # Step 4d: Ensure tenant columns exist on older table versions
            cur.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS user_id TEXT")
            cur.execute("ALTER TABLE invoice_items ADD COLUMN IF NOT EXISTS user_id TEXT")

            # Step 4e: Replace global invoice uniqueness with per-user uniqueness
            cur.execute("ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_invoice_no_key")
            cur.execute("DROP INDEX IF EXISTS idx_invoices_invoice_no")

            # Step 4f: Backfill legacy rows before making user_id required
            legacy_owner_user_id = get_legacy_owner_user_id()
            cur.execute("SELECT COUNT(*) FROM invoices WHERE user_id IS NULL")
            _null_invoice_count = cur.fetchone()[0]
            if _null_invoice_count:
                if not legacy_owner_user_id:
                    raise RuntimeError(
                        "Existing invoices must be assigned to a tenant before enabling multi-tenant security. "
                        "Set FFIA_LEGACY_OWNER_USERNAME or configure exactly one auth user."
                    )
                cur.execute(
                    "UPDATE invoices SET user_id = %s WHERE user_id IS NULL",
                    (legacy_owner_user_id,),
                )

            cur.execute("""
                UPDATE invoice_items AS items
                SET user_id = invoices.user_id
                FROM invoices
                WHERE items.invoice_id = invoices.id
                  AND items.user_id IS NULL
            """)
            cur.execute("SELECT COUNT(*) FROM invoice_items WHERE user_id IS NULL")
            _null_item_count = cur.fetchone()[0]
            if _null_item_count:
                if not legacy_owner_user_id:
                    raise RuntimeError(
                        "Existing invoice_items rows must be assigned to a tenant before enabling multi-tenant security."
                    )
                cur.execute(
                    "UPDATE invoice_items SET user_id = %s WHERE user_id IS NULL",
                    (legacy_owner_user_id,),
                )

            cur.execute("ALTER TABLE invoices ALTER COLUMN user_id SET NOT NULL")
            cur.execute("ALTER TABLE invoice_items ALTER COLUMN user_id SET NOT NULL")

            # Step 4g: Ensure tenant-aware indexes exist
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_user_invoice_no
                ON invoices(user_id, invoice_no)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_invoices_user_created_at
                ON invoices(user_id, created_at DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_invoice_items_user_invoice_id
                ON invoice_items(user_id, invoice_id)
            """)

            # Step 4h: Backfill any columns that may be missing from older table versions
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

            # Step 4i: Enforce row-level tenant isolation for invoice tables
            cur.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY")
            cur.execute("ALTER TABLE invoices FORCE ROW LEVEL SECURITY")
            cur.execute("DROP POLICY IF EXISTS invoices_tenant_isolation ON invoices")
            cur.execute("""
                CREATE POLICY invoices_tenant_isolation ON invoices
                USING (
                    current_setting('app.current_user_id', true) IS NOT NULL
                    AND user_id = current_setting('app.current_user_id', true)
                )
                WITH CHECK (
                    current_setting('app.current_user_id', true) IS NOT NULL
                    AND user_id = current_setting('app.current_user_id', true)
                )
            """)

            cur.execute("ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY")
            cur.execute("ALTER TABLE invoice_items FORCE ROW LEVEL SECURITY")
            cur.execute("DROP POLICY IF EXISTS invoice_items_tenant_isolation ON invoice_items")
            cur.execute("""
                CREATE POLICY invoice_items_tenant_isolation ON invoice_items
                USING (
                    current_setting('app.current_user_id', true) IS NOT NULL
                    AND user_id = current_setting('app.current_user_id', true)
                )
                WITH CHECK (
                    current_setting('app.current_user_id', true) IS NOT NULL
                    AND user_id = current_setting('app.current_user_id', true)
                )
            """)

            # Step 4j: Ingredient market prices — global reference table (no RLS, no tenant scoping)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ingredient_market_prices (
                    id               TEXT PRIMARY KEY,
                    ingredient       TEXT NOT NULL,
                    avg_market_price NUMERIC(10, 2) NOT NULL,
                    unit             TEXT NOT NULL,
                    source           TEXT NOT NULL,
                    seeded_at        TIMESTAMP DEFAULT NOW()
                )
            """)

            # Step 4k: Platform fee reference table — global, no RLS, no tenant scoping
            # (docs/data_definition.md — Table 2: platform_fee)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS platform_fee (
                    platform    VARCHAR(50)   PRIMARY KEY,
                    fee_percent DECIMAL(5, 2) NOT NULL,
                    is_default  BOOLEAN       NOT NULL DEFAULT false,
                    updated_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Step 4l: Seed default platform fees (idempotent — skip if already seeded)
            cur.execute("SELECT COUNT(*) FROM platform_fee")
            if cur.fetchone()[0] == 0:
                cur.executemany(
                    "INSERT INTO platform_fee (platform, fee_percent, is_default) "
                    "VALUES (%s, %s, %s)",
                    [
                        ("Grab",         30.00, True),
                        ("Foodpanda",    30.00, False),
                        ("LINE MAN",     30.00, False),
                        ("Shopee Food",  25.00, False),
                        ("Robinhood",     0.00, False),
                    ],
                )

            # Step 4m: Per-user channel mix — tenant-scoped, persists Business Profile Step 3
            cur.execute("""
                CREATE TABLE IF NOT EXISTS restaurant_channel_mix (
                    id                SERIAL PRIMARY KEY,
                    user_id           TEXT          NOT NULL,
                    platform          TEXT          NOT NULL,
                    revenue_share_pct DECIMAL(5,2)  NOT NULL DEFAULT 0,
                    platform_fee_pct  DECIMAL(5,2)  NOT NULL DEFAULT 0,
                    is_active         BOOLEAN       NOT NULL DEFAULT true,
                    updated_at        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, platform)
                )
            """)
        conn.commit()


# Step 4 RAG: Ensure RAG schema — vector extension + invoice_embeddings table
def ensure_rag_schema() -> None:
    """Create pgvector extension and invoice_embeddings table if they do not exist.

    Standalone — not wired into create_tables() startup.
    Call once during RAG pipeline setup before the first embedding write.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Step 1: Enable pgvector extension (requires superuser or pg_extension_owner)
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Step 2: Create embedding store
            # vector(768) matches VertexAI text-embedding-004 — change dimension here
            # if switching to a different embedding model
            cur.execute("""
                CREATE TABLE IF NOT EXISTS invoice_embeddings (
                    id          SERIAL PRIMARY KEY,
                    user_id     TEXT        NOT NULL,
                    invoice_id  INTEGER     REFERENCES invoices(id) ON DELETE CASCADE,
                    item_id     INTEGER     REFERENCES invoice_items(id) ON DELETE CASCADE,
                    chunk_text  TEXT        NOT NULL,
                    embedding   vector(768),
                    metadata    JSONB,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Step 3: HNSW index for approximate nearest-neighbour search (cosine distance)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_invoice_embeddings_hnsw
                ON invoice_embeddings USING hnsw (embedding vector_cosine_ops)
            """)

            # Step 4: B-tree index for fast per-tenant filtering
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_invoice_embeddings_user_id
                ON invoice_embeddings (user_id)
            """)
        conn.commit()


# Step 4 RAG-2: Fetch invoice line items as text chunks ready for embedding
def fetch_invoice_chunks_for_embedding(user_id: str) -> list[dict]:
    """Return all invoice line items for the tenant formatted as embedding-ready text chunks.

    Returns:
        List of dicts with keys: chunk_text, item_id, invoice_id,
        vendor, invoice_date, user_id
    """
    # Step 1: Validate and normalise tenant identifier
    normalized_user_id = _require_user_id(user_id)

    # Step 2: JOIN invoices + invoice_items — filter by user_id for tenant isolation
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    ii.id           AS item_id,
                    ii.invoice_id,
                    ii.name,
                    ii.qty,
                    ii.unit_price,
                    ii.total,
                    inv.vendor,
                    inv.invoice_date,
                    inv.user_id     AS user_id
                FROM invoice_items ii
                JOIN invoices inv ON ii.invoice_id = inv.id
                WHERE inv.user_id = %s
                ORDER BY inv.invoice_date DESC, ii.id ASC
                """,
                (normalized_user_id,),
            )
            rows = cur.fetchall()

    # Step 3: Build chunk text per line item using the standard invoice chunk format
    chunks = []
    for row in rows:
        chunk_text = (
            f"Invoice from {row['vendor']} on {row['invoice_date']}: "
            f"{row['name']}, quantity {row['qty']}, "
            f"unit price {row['unit_price']} THB, total {row['total']} THB."
        )
        chunks.append({
            "chunk_text":   chunk_text,
            "item_id":      row["item_id"],
            "invoice_id":   row["invoice_id"],
            "vendor":       row["vendor"],
            "invoice_date": row["invoice_date"],
            "user_id":      row["user_id"],
        })
    return chunks


# Step 5: Duplicate check — used by the UI before saving
def invoice_exists(user_id: str, invoice_no: str) -> bool:
    """Return True if an invoice with this invoice_no already exists for the current user."""
    normalized_user_id = _require_user_id(user_id)
    with get_connection(normalized_user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM invoices WHERE user_id = %s AND invoice_no = %s LIMIT 1",
                (normalized_user_id, invoice_no),
            )
            return cur.fetchone() is not None


# Step 6: Save invoice — insert a new invoice and its items
def save_invoice(
    user_id: str,
    vendor: str,
    invoice_no: str,
    invoice_date,
    total_amount: float,
    items: list[dict],
) -> int:
    """
    Persist an invoice header and its line items to PostgreSQL.

    Args:
        user_id:      Authenticated tenant identifier
        vendor:       Supplier name
        invoice_no:   Unique invoice reference number
        invoice_date: Date object or ISO string (YYYY-MM-DD)
        total_amount: Total invoice amount in THB
        items:        List of dicts with keys: name, qty, unit_price, total

    Returns:
        int: The invoice id (primary key)
    """
    normalized_user_id = _require_user_id(user_id)
    with get_connection(normalized_user_id) as conn:
        with conn.cursor() as cur:
            # Step 6a: Insert invoice header
            cur.execute(
                """
                INSERT INTO invoices (user_id, vendor, invoice_no, invoice_date, total_amount)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (normalized_user_id, vendor, invoice_no, invoice_date, total_amount),
            )
            invoice_id = cur.fetchone()[0]

            # Step 6b: Bulk insert line items
            if items:
                psycopg2.extras.execute_batch(
                    cur,
                    """
                    INSERT INTO invoice_items (invoice_id, user_id, name, qty, unit_price, total)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            invoice_id,
                            normalized_user_id,
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
def get_latest_invoice(user_id: str) -> dict | None:
    """
    Return the most recently created invoice for the current user and its line items.

    Returns:
        dict with invoice header fields plus `items`, or None if no invoice exists.
    """
    normalized_user_id = _require_user_id(user_id)
    with get_connection(normalized_user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, vendor, invoice_no, invoice_date, total_amount, created_at
                FROM invoices
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (normalized_user_id,),
            )
            invoice = cur.fetchone()
            if not invoice:
                return None

            invoice_data = dict(invoice)
            cur.execute(
                """
                SELECT name, qty, unit_price, total
                FROM invoice_items
                WHERE user_id = %s AND invoice_id = %s
                ORDER BY id ASC
                """,
                (normalized_user_id, invoice_data["id"]),
            )
            invoice_data["items"] = [dict(row) for row in cur.fetchall()]
            return invoice_data


# Step 8: Fetch recent invoices for display in the UI
def get_recent_invoices(user_id: str, limit: int = 10) -> list[dict]:
    """
    Return the most recently created invoices for the current user.

    Returns:
        List of dicts with keys: id, vendor, invoice_no, invoice_date,
        total_amount, created_at
    """
    normalized_user_id = _require_user_id(user_id)
    with get_connection(normalized_user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, vendor, invoice_no, invoice_date, total_amount, created_at
                FROM invoices
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (normalized_user_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]


# Step 9: Fetch invoices for the current calendar month — used by the upload page
def fetch_invoices_current_month(user_id: str) -> list[dict]:
    """
    Return all invoices whose invoice_date falls in the current calendar month,
    sorted by invoice_date DESC (latest first).

    Returns:
        List of dicts with keys: id, invoice_date, vendor, invoice_no, total_amount
    """
    normalized_user_id = _require_user_id(user_id)
    with get_connection(normalized_user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, invoice_date, vendor, invoice_no, total_amount
                FROM invoices
                WHERE user_id = %s
                  AND DATE_TRUNC('month', invoice_date) = DATE_TRUNC('month', CURRENT_DATE)
                ORDER BY invoice_date DESC
                """,
                (normalized_user_id,),
            )
            return [dict(row) for row in cur.fetchall()]


# Step 10: Fetch line items for a selected invoice — used by the upload page detail view
def fetch_invoice_items(invoice_id: int, user_id: str) -> list[dict]:
    """
    Return line items for a given invoice, aliasing the 'name' column as 'item_name'
    to match the display requirement.

    Returns:
        List of dicts with keys: item_name, qty, unit_price, total
    """
    normalized_user_id = _require_user_id(user_id)
    with get_connection(normalized_user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT name AS item_name, qty, unit_price, total
                FROM invoice_items
                WHERE invoice_id = %s AND user_id = %s
                ORDER BY id ASC
                """,
                (invoice_id, normalized_user_id),
            )
            return [dict(row) for row in cur.fetchall()]


# Step 10b: Delete an invoice and its line items for a user — RLS-safe
def delete_invoice(invoice_id: int, user_id: str) -> bool:
    """Delete invoice and cascade to invoice_items.
    Returns True if deleted, False if not found."""
    normalized_user_id = _require_user_id(user_id)
    with get_connection(normalized_user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM invoices WHERE id = %s AND user_id = %s",
                (invoice_id, normalized_user_id),
            )
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted


# Step 10c: Count all line items for a user — used by dashboard decision card
def count_invoice_items(user_id: str) -> int:

    """Return total count of invoice line items stored for this user."""
    normalized_user_id = _require_user_id(user_id)
    with get_connection(normalized_user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM invoice_items WHERE user_id = %s",
                (normalized_user_id,),
            )
            return cur.fetchone()[0]


# Step 10c: Seed ingredient market prices from a CSV file — idempotent upsert
def seed_ingredient_market_prices(csv_path: str) -> int:
    """
    Upsert rows from a CSV into ingredient_market_prices.
    Safe to re-run: existing rows are updated, new rows are inserted.

    Args:
        csv_path: Path to CSV with columns: id, ingredient, avg_market_price, unit, source.

    Returns:
        Number of rows upserted.
    """
    import csv
    from pathlib import Path

    # Step 10c-i: Read CSV rows into a list of tuples
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Ingredient CSV not found: {csv_path}")

    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append((
                row["id"].strip(),
                row["ingredient"].strip(),
                float(row["avg_market_price"]),
                row["unit"].strip(),
                row["source"].strip(),
            ))

    if not rows:
        return 0

    # Step 10c-ii: Upsert — insert new rows, update existing ones on id conflict
    with get_connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO ingredient_market_prices (id, ingredient, avg_market_price, unit, source)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                    SET ingredient       = EXCLUDED.ingredient,
                        avg_market_price = EXCLUDED.avg_market_price,
                        unit             = EXCLUDED.unit,
                        source           = EXCLUDED.source,
                        seeded_at        = NOW()
                """,
                rows,
            )
        conn.commit()
    return len(rows)


# Step 11: Restaurant profile helpers

def fetch_latest_restaurant_profile(user_id: str) -> dict | None:
    """Return the most recent active restaurant profile for the user, or None."""
    # Step 11a: Normalize and validate user_id
    _uid = _require_user_id(user_id)
    # Step 11b: Query latest active profile ordered by updated_at DESC
    with get_connection(_uid) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, restaurant_name, business_type, food_types,
                       store_type, seat_range, currency,
                       target_margin_pct, warning_margin_pct, risk_margin_pct,
                       is_active, created_at, updated_at
                FROM public.restaurant_profiles
                WHERE user_id = %s AND is_active = true
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (_uid,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            # Step 11c: Normalize food_types — column may be text[] (list) or text (JSON string)
            profile = dict(row)
            raw_food = profile.get("food_types")
            if isinstance(raw_food, str):
                import json
                try:
                    profile["food_types"] = json.loads(raw_food)
                except (ValueError, TypeError):
                    profile["food_types"] = []
            elif raw_food is None:
                profile["food_types"] = []
            return profile


# Step 12: Upsert restaurant profile

def upsert_restaurant_profile(
    user_id: str,
    restaurant_name: str,
    business_type: str,
    food_types: list[str],
    store_type: str,
    seat_range: str,
    currency: str,
    target_margin_pct: float,
    warning_margin_pct: float,
    risk_margin_pct: float,
) -> None:
    """Update the active profile if one exists; insert a new one if not."""
    # Step 12a: Normalize user_id
    _uid = _require_user_id(user_id)
    # Step 12b: UPDATE existing active row; INSERT if no row was updated
    with get_connection(_uid) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.restaurant_profiles
                SET restaurant_name = %s,
                    business_type   = %s,
                    food_types      = %s::text[],
                    store_type      = %s,
                    seat_range      = %s,
                    currency        = %s,
                    target_margin_pct  = %s,
                    warning_margin_pct = %s,
                    risk_margin_pct    = %s,
                    updated_at      = NOW()
                WHERE user_id = %s AND is_active = true
                """,
                (
                    restaurant_name, business_type, food_types,
                    store_type, seat_range, currency,
                    target_margin_pct, warning_margin_pct, risk_margin_pct,
                    _uid,
                ),
            )
            # Step 12c: INSERT if no existing active profile was found
            if cur.rowcount == 0:
                cur.execute(
                    """
                    INSERT INTO public.restaurant_profiles
                        (user_id, restaurant_name, business_type, food_types,
                         store_type, seat_range, currency,
                         target_margin_pct, warning_margin_pct, risk_margin_pct,
                         is_active)
                    VALUES (%s, %s, %s, %s::text[], %s, %s, %s, %s, %s, %s, true)
                    """,
                    (
                        _uid, restaurant_name, business_type, food_types,
                        store_type, seat_range, currency,
                        target_margin_pct, warning_margin_pct, risk_margin_pct,
                    ),
                )
        conn.commit()


# Step 13: Persist user channel mix from Business Profile Step 3

def upsert_channel_mix(user_id: str, channels: dict) -> None:
    """
    Persist all platform/channel selections for a user into restaurant_channel_mix.

    Args:
        user_id:  Authenticated tenant identifier
        channels: Dict keyed by channel slug, each value is a dict with:
                  label (str), revenue_share_pct (float), gp_pct (float), enabled (bool)

    Behaviour:
        - Active channels are upserted with their current revenue_share_pct / platform_fee_pct.
        - Disabled channels are upserted with is_active = false so history is preserved.
    """
    # Step 13a: Normalize user_id
    _uid = _require_user_id(user_id)

    # Step 13b: Build rows list — one row per channel regardless of enabled state
    rows = []
    for _slug, _ch in channels.items():
        rows.append((
            _uid,
            str(_ch.get("label", _slug)),
            float(_ch.get("revenue_share_pct", 0)),
            float(_ch.get("gp_pct", 0)),
            bool(_ch.get("enabled", False)),
        ))

    if not rows:
        return

    # Step 13c: Upsert — insert or update on (user_id, platform) conflict
    with get_connection(_uid) as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO restaurant_channel_mix
                    (user_id, platform, revenue_share_pct, platform_fee_pct, is_active)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, platform)
                DO UPDATE SET
                    revenue_share_pct = EXCLUDED.revenue_share_pct,
                    platform_fee_pct  = EXCLUDED.platform_fee_pct,
                    is_active         = EXCLUDED.is_active,
                    updated_at        = CURRENT_TIMESTAMP
                """,
                rows,
            )
        conn.commit()


# Step 14: Standalone test block
if __name__ == "__main__":
    print("Creating tables...")
    create_tables()
    print("Tables ready.")

    print("Saving test invoice...")
    _test_user_id = "demo"
    if invoice_exists(_test_user_id, "TEST-001"):
        print("Invoice TEST-001 already exists.")
    else:
        inv_id = save_invoice(
            user_id=_test_user_id,
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
    for row in get_recent_invoices(_test_user_id):
        print(" ", row)

    print("Latest invoice:")
    print(get_latest_invoice(_test_user_id))
