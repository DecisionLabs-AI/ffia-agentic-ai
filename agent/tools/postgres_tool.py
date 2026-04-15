# =============================================================================
# FFIA — PostgreSQL SQL Execution Tool
# Allows the ReAct agent to query restaurant cost data from PostgreSQL.
# =============================================================================

# Step 1: Imports
import os
import re
from contextvars import ContextVar
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# Step 2: Runtime config getter — reads DATABASE_URL on demand, not at import time.
# This ensures .env changes are picked up without restarting Streamlit.
def _get_database_url() -> str | None:
    return os.getenv("DATABASE_URL")
_CURRENT_USER_ID: ContextVar[str | None] = ContextVar("ffia_postgres_tool_user_id", default=None)

# Step 3: Interim FFIA schema contract — gives the LLM a concrete target for SQL generation.
# If the live schema differs, the agent should inspect information_schema first.
TABLE_SCHEMA_DESCRIPTION = """
FFIA PostgreSQL schema guidance:

Tenant-scoped invoice tables (always filter by user_id):

1. invoices
   Columns:
   - id (SERIAL PRIMARY KEY)
   - user_id (TEXT)          -- tenant identifier — ALWAYS include in WHERE clause
   - vendor (TEXT)
   - invoice_no (TEXT)
   - invoice_date (DATE)
   - total_amount (NUMERIC)
   - created_at (TIMESTAMPTZ)

2. invoice_items
   Columns:
   - id (SERIAL PRIMARY KEY)
   - user_id (TEXT)          -- tenant identifier — ALWAYS include in WHERE clause
   - invoice_id (INTEGER)    -- FK → invoices.id
   - name (TEXT)             -- ingredient or product name
   - qty (NUMERIC)
   - unit_price (NUMERIC)
   - total (NUMERIC)

3. ingredient_market_prices (global reference — no user_id filter needed)
   Columns:
   - id (TEXT PRIMARY KEY)        -- e.g. "MOC-001", "MAK-272716"
   - ingredient (TEXT)            -- Thai ingredient or packaging name
   - avg_market_price (NUMERIC)   -- price in THB
   - unit (TEXT)                  -- e.g. "kg", "piece", "pack", "bunch"
   - source (TEXT)                -- "Ministry of Commerce" or "Makro"
   - seeded_at (TIMESTAMP)

   Note: No user_id column — this table is shared across all tenants.
   Prefer the ingredient_price_tool for ingredient lookups; use SQL only for
   aggregations or joins with invoice_items.

4. platform_fee (global reference — no user_id filter needed)
   Columns:
   - platform    VARCHAR(50) PRIMARY KEY  -- e.g. "Grab", "Foodpanda", "LINE MAN"
   - fee_percent DECIMAL(5,2)             -- commission percentage, e.g. 30.00
   - is_default  BOOLEAN                  -- true for the default fallback platform
   - updated_at  TIMESTAMP               -- last updated timestamp

   Use: SELECT fee_percent / 100.0 AS gp_pct FROM platform_fee WHERE LOWER(platform) = LOWER('grab');
   Note: No user_id column — this table is shared across all tenants.
   Convert fee_percent to a fraction (divide by 100) before passing to business rule tools.
   FALLBACK ONLY — query restaurant_channel_mix first; use platform_fee only if that returns 0 rows.

5. restaurant_channel_mix (tenant-scoped — PRIMARY source for platform data)
   Columns:
   - id                SERIAL PRIMARY KEY
   - user_id           TEXT          -- tenant identifier — ALWAYS filter with 'current_user_placeholder'
   - platform          TEXT          -- e.g. "Grab Food", "LINE MAN", "Shopee Food", "Walk-in / Self-pickup"
   - revenue_share_pct DECIMAL(5,2)  -- % of total revenue through this channel, e.g. 40.00
   - platform_fee_pct  DECIMAL(5,2)  -- platform's commission fee %, e.g. 28.00
   - is_active         BOOLEAN       -- only query WHERE is_active = true
   - updated_at        TIMESTAMP

   Use: SELECT platform, revenue_share_pct, platform_fee_pct
        FROM restaurant_channel_mix
        WHERE user_id = 'current_user_placeholder' AND is_active = true
        ORDER BY revenue_share_pct DESC;
   Note: This is the PRIMARY source for platform data. Query this before platform_fee.
         If this returns 0 rows, fall back to platform_fee (global defaults).
   For gp_pct lookup: SELECT platform_fee_pct / 100.0 AS gp_pct
                      FROM restaurant_channel_mix
                      WHERE user_id = 'current_user_placeholder'
                        AND LOWER(platform) ILIKE '%<platform>%'
                        AND is_active = true LIMIT 1;

6. restaurant_profiles (tenant-scoped — filter by user_id)
   Columns:
   - id                  SERIAL PRIMARY KEY
   - user_id             TEXT             -- tenant identifier — filter with 'current_user_placeholder'
   - restaurant_name     TEXT
   - business_type       TEXT             -- e.g. "ร้านอาหาร", "Cloud Kitchen"
   - food_types          TEXT[]           -- cuisine types array, e.g. ["ไทย", "ข้าว"]
   - store_type          TEXT             -- e.g. "ร้านนั่งกิน", "Delivery Only"
   - seat_range          TEXT             -- e.g. "1-20", "21-50"
   - currency            TEXT             -- e.g. "THB"
   - target_margin_pct   NUMERIC          -- target gross margin as a whole number, e.g. 30.0 = 30%
   - warning_margin_pct  NUMERIC          -- warning threshold, e.g. 20.0 = 20%
   - risk_margin_pct     NUMERIC          -- critical/risk threshold, e.g. 15.0 = 15%
   - is_active           BOOLEAN          -- only query WHERE is_active = true
   - created_at          TIMESTAMP
   - updated_at          TIMESTAMP

   Use: SELECT * FROM restaurant_profiles
        WHERE user_id = 'current_user_placeholder' AND is_active = true
        ORDER BY updated_at DESC LIMIT 1;

Query rules:
- ALWAYS filter by user_id using the placeholder literal 'current_user_placeholder'
  for invoices and invoice_items. The tool replaces this with the real session user_id.
  Example: WHERE user_id = 'current_user_placeholder'
- ingredient_market_prices does NOT require a user_id filter.
- Use ILIKE for partial name matching: WHERE name ILIKE '%egg%'
- Use standard PostgreSQL syntax. No backticks, no BigQuery qualifiers.
- If a column may not exist, inspect information_schema.columns first.
"""

_BLOCK_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_PATTERN = re.compile(r"--[^\n\r]*")
_STRING_LITERAL_PATTERN = re.compile(r"'(?:''|\\'|[^'])*'|\"(?:\"\"|\\\"|[^\"])*\"")
_SELECT_START_PATTERN = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_FORBIDDEN_SQL_PATTERNS = [
    (re.compile(r"\bINSERT\b", re.IGNORECASE), "INSERT"),
    (re.compile(r"\bUPDATE\b", re.IGNORECASE), "UPDATE"),
    (re.compile(r"\bDELETE\b", re.IGNORECASE), "DELETE"),
    (re.compile(r"\bMERGE\b", re.IGNORECASE), "MERGE"),
    (re.compile(r"\bCREATE\b", re.IGNORECASE), "CREATE"),
    (re.compile(r"\bDROP\b", re.IGNORECASE), "DROP"),
    (re.compile(r"\bALTER\b", re.IGNORECASE), "ALTER"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE"),
    (re.compile(r"\bEXECUTE\b", re.IGNORECASE), "EXECUTE"),
    (re.compile(r"(?m)^\s*BEGIN\b", re.IGNORECASE), "BEGIN"),
    (re.compile(r"(?m)^\s*END\b", re.IGNORECASE), "END"),
    (re.compile(r"\bCALL\b", re.IGNORECASE), "CALL"),
]
_INVOICE_TABLE_PATTERN = re.compile(r"\b(invoices|invoice_items|restaurant_profiles)\b", re.IGNORECASE)


def _strip_sql_comments_and_literals(sql: str) -> str:
    """Remove comments and string literals before applying conservative safety checks."""
    without_block_comments = _BLOCK_COMMENT_PATTERN.sub(" ", sql)
    without_comments = _LINE_COMMENT_PATTERN.sub(" ", without_block_comments)
    return _STRING_LITERAL_PATTERN.sub("''", without_comments)


def _references_invoice_tables(sql: str) -> bool:
    """Return True when the SQL references tenant-scoped invoice tables."""
    normalized = _strip_sql_comments_and_literals(sql)
    return bool(_INVOICE_TABLE_PATTERN.search(normalized))


def set_postgres_tool_user_id(user_id: str | None):
    """Bind the current agent run to a tenant for invoice-table isolation."""
    normalized = str(user_id or "").strip() or None
    return _CURRENT_USER_ID.set(normalized)


def reset_postgres_tool_user_id(token) -> None:
    """Restore the previous tenant context after an agent run."""
    _CURRENT_USER_ID.reset(token)


def _validate_select_sql(sql: str) -> tuple[bool, str]:
    """
    Allow exactly one SELECT/CTE statement and block scripting, DDL, and mutations.

    Returns:
        (is_valid, normalized_sql_or_error_message)
    """
    normalized = _strip_sql_comments_and_literals(sql).strip()
    if not normalized:
        return False, "Error: Query blocked. SQL is empty."

    if not _SELECT_START_PATTERN.match(normalized):
        return (
            False,
            "Error: Query blocked. Only a single SELECT statement is allowed.",
        )

    trailing_semicolon = normalized.endswith(";")
    statement_body = normalized[:-1].strip() if trailing_semicolon else normalized

    if ";" in statement_body:
        return (
            False,
            "Error: Query blocked. Multiple SQL statements are not allowed.",
        )

    for pattern, keyword in _FORBIDDEN_SQL_PATTERNS:
        if pattern.search(statement_body):
            return (
                False,
                f"Error: Query blocked. Forbidden SQL keyword detected: {keyword}. "
                "Only a single SELECT statement is allowed.",
            )

    return True, sql.strip().rstrip(";").strip()


# Step 4: Define tool using @tool decorator (LangChain 1.x compatible)
@tool
def postgres_tool(sql: str) -> str:
    """Use this tool to query restaurant cost and oil price data from the PostgreSQL database.

    Input MUST be exactly one SQL SELECT statement.
    SELECT statements may begin with SELECT or WITH, but scripting, DDL, mutations,
    CALL statements, and semicolon-delimited multi-statement execution are blocked.

    IMPORTANT: Always use the literal string 'current_user_placeholder' in the WHERE
    clause for user_id. The tool replaces it with the real session user_id automatically.
    Never ask the user for their user_id — it is injected by the session context.

    Example:
    SELECT vendor, invoice_no, total_amount
    FROM invoices
    WHERE user_id = 'current_user_placeholder'
    LIMIT 5
    """
    # Step 4a: Security guardrail — enforce a single safe SELECT statement.
    is_valid, validated_sql_or_error = _validate_select_sql(sql)
    if not is_valid:
        return validated_sql_or_error

    database_url = _get_database_url()
    if not database_url:
        return "Error: DATABASE_URL is not set. Add it to your .env file."

    try:
        safe_sql = validated_sql_or_error
        current_user_id = _CURRENT_USER_ID.get()

        if _references_invoice_tables(safe_sql) and not current_user_id:
            return "Error: Invoice queries require an authenticated user context."

        # Step 4b: Replace the user_id placeholder with the real session user_id.
        # This allows the agent to write portable SQL without knowing the actual value.
        if current_user_id:
            safe_sql = safe_sql.replace("'current_user_placeholder'", f"'{current_user_id}'")

        # Step 4c: Inject LIMIT 50 if not already present to cap output
        if "LIMIT" not in safe_sql.upper():
            safe_sql = safe_sql + " LIMIT 50"

        # Step 4d: Execute query via psycopg2
        with psycopg2.connect(database_url) as conn:
            if current_user_id:
                with conn.cursor() as cur:
                    cur.execute("SELECT set_config('app.current_user_id', %s, false)", (current_user_id,))
            df = pd.read_sql_query(safe_sql, conn)

        # Step 4e: Return empty message or markdown table
        if df.empty:
            return "Query returned no results."
        return df.to_markdown(index=False)

    except Exception as e:
        # Step 4f: Return error string — never raise, so agent can handle gracefully
        return f"PostgreSQL error: {str(e)}"


# Step 5: Standalone test block
if __name__ == "__main__":
    print("Testing PostgreSQL tool...")
    result = postgres_tool.invoke("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    print(result)


postgres_tool.description = f"{postgres_tool.description}\n\n{TABLE_SCHEMA_DESCRIPTION.strip()}"
