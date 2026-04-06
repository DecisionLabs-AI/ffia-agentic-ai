# =============================================================================
# FFIA — PostgreSQL SQL Execution Tool
# Allows the ReAct agent to query restaurant cost data from PostgreSQL.
# =============================================================================

# Step 1: Imports
import os
import re
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# Step 2: Read database connection URL from environment (never hardcoded)
DATABASE_URL = os.getenv("DATABASE_URL")

# Step 3: Interim FFIA schema contract — gives the LLM a concrete target for SQL generation.
# If the live schema differs, the agent should inspect information_schema first.
TABLE_SCHEMA_DESCRIPTION = """
FFIA PostgreSQL schema guidance:

Primary analysis tables:
1. restaurant_costs
   Columns:
   - restaurant_id (TEXT)
   - restaurant_name (TEXT)
   - menu_item (TEXT)
   - ingredient_cost_thb (NUMERIC)
   - packaging_cost_thb (NUMERIC)
   - delivery_fee_thb (NUMERIC)
   - fuel_surcharge_thb (NUMERIC)
   - selling_price_thb (NUMERIC)
   - recorded_date (DATE)

2. oil_prices
   Columns:
   - price_date (DATE)
   - diesel_price_thb (NUMERIC)
   - gasohol_91_price_thb (NUMERIC)
   - gasohol_95_price_thb (NUMERIC)
   - source (TEXT)
   - region (TEXT)

Querying rules:
- Use standard table names (no project/dataset prefix).
- For menu margin questions, start with restaurant_costs.
- For oil and fuel trend questions, start with oil_prices.
- If a requested column or table may not exist, inspect
  information_schema.columns first with a SELECT query.
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


def _strip_sql_comments_and_literals(sql: str) -> str:
    """Remove comments and string literals before applying conservative safety checks."""
    without_block_comments = _BLOCK_COMMENT_PATTERN.sub(" ", sql)
    without_comments = _LINE_COMMENT_PATTERN.sub(" ", without_block_comments)
    return _STRING_LITERAL_PATTERN.sub("''", without_comments)


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

    Example:
    SELECT menu_item, selling_price_thb
    FROM restaurant_costs
    LIMIT 5
    """
    # Step 4a: Security guardrail — enforce a single safe SELECT statement.
    is_valid, validated_sql_or_error = _validate_select_sql(sql)
    if not is_valid:
        return validated_sql_or_error

    if not DATABASE_URL:
        return "Error: DATABASE_URL is not set. Add it to your .env file."

    try:
        safe_sql = validated_sql_or_error

        # Step 4b: Inject LIMIT 50 if not already present to cap output
        if "LIMIT" not in safe_sql.upper():
            safe_sql = safe_sql + " LIMIT 50"

        # Step 4c: Execute query via psycopg2
        with psycopg2.connect(DATABASE_URL) as conn:
            df = pd.read_sql_query(safe_sql, conn)

        # Step 4d: Return empty message or markdown table
        if df.empty:
            return "Query returned no results."
        return df.to_markdown(index=False)

    except Exception as e:
        # Step 4e: Return error string — never raise, so agent can handle gracefully
        return f"PostgreSQL error: {str(e)}"


# Step 5: Standalone test block
if __name__ == "__main__":
    print("Testing PostgreSQL tool...")
    result = postgres_tool.invoke("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    print(result)


postgres_tool.description = f"{postgres_tool.description}\n\n{TABLE_SCHEMA_DESCRIPTION.strip()}"
