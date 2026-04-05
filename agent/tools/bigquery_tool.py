# =============================================================================
# FFIA — BigQuery SQL Execution Tool (W2)
# Allows the ReAct agent to query restaurant cost data from BigQuery.
# =============================================================================

# Step 1: Imports
import os
import re
from dotenv import load_dotenv
from google.cloud import bigquery
from langchain_core.tools import tool

load_dotenv()

# Step 2: Read project and dataset from environment (never hardcoded)
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-madt-ai")
BQ_DATASET = os.getenv("BIGQUERY_DATASET", "data_source")
BQ_LOCATION = os.getenv("BIGQUERY_LOCATION", "asia-southeast3")

# Step 3: Interim FFIA schema contract — gives the LLM a concrete target for SQL generation.
# If the live dataset differs, the agent should inspect INFORMATION_SCHEMA first.
TABLE_SCHEMA_DESCRIPTION = f"""
FFIA BigQuery schema guidance for dataset `{GCP_PROJECT}.{BQ_DATASET}`:

Primary analysis tables:
1. `{GCP_PROJECT}.{BQ_DATASET}.restaurant_costs`
   Columns:
   - restaurant_id (STRING)
   - restaurant_name (STRING)
   - menu_item (STRING)
   - ingredient_cost_thb (FLOAT)
   - packaging_cost_thb (FLOAT)
   - delivery_fee_thb (FLOAT)
   - fuel_surcharge_thb (FLOAT)
   - selling_price_thb (FLOAT)
   - recorded_date (DATE)

2. `{GCP_PROJECT}.{BQ_DATASET}.oil_prices`
   Columns:
   - price_date (DATE)
   - diesel_price_thb (FLOAT)
   - gasohol_91_price_thb (FLOAT)
   - gasohol_95_price_thb (FLOAT)
   - source (STRING)
   - region (STRING)

Querying rules:
- Always use fully-qualified table names.
- For menu margin questions, start with `restaurant_costs`.
- For oil and fuel trend questions, start with `oil_prices`.
- If a requested column or table may differ in the live dataset, inspect
  `{GCP_PROJECT}.{BQ_DATASET}.INFORMATION_SCHEMA.COLUMNS` first with a SELECT query.
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
    (re.compile(r"\bEXECUTE\s+IMMEDIATE\b", re.IGNORECASE), "EXECUTE IMMEDIATE"),
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
def bigquery_tool(sql: str) -> str:
    """Use this tool to query restaurant cost and oil price data from BigQuery.

    Input MUST be exactly one SQL SELECT statement using fully-qualified table names.
    SELECT statements may begin with SELECT or WITH, but scripting, DDL, mutations,
    CALL statements, and semicolon-delimited multi-statement execution are blocked.

    Example:
    SELECT menu_item, selling_price_thb
    FROM `gcp-madt-ai.data_source.restaurant_costs`
    LIMIT 5
    """
    # Step 4a: Security guardrail — enforce a single safe SELECT statement.
    is_valid, validated_sql_or_error = _validate_select_sql(sql)
    if not is_valid:
        return validated_sql_or_error

    try:
        # Step 4b: Initialize BigQuery client (picks up GOOGLE_APPLICATION_CREDENTIALS from env)
        client = bigquery.Client(project=GCP_PROJECT)
        safe_sql = validated_sql_or_error

        # Step 4c: Inject LIMIT 50 if not already present to cap cost/output
        if "LIMIT" not in safe_sql.upper():
            safe_sql = safe_sql + " LIMIT 50"

        # Step 4d: Execute query
        query_job = client.query(safe_sql, location=BQ_LOCATION)
        df = query_job.to_dataframe()

        # Step 4e: Return empty message or markdown table
        if df.empty:
            return "Query returned no results."
        return df.to_markdown(index=False)

    except Exception as e:
        # Step 4f: Return error string — never raise, so agent can handle gracefully
        return f"BigQuery error: {str(e)}"


# Step 5: Standalone test block
if __name__ == "__main__":
    print("Testing BigQuery tool...")
    test_sql = f"SELECT * FROM `{GCP_PROJECT}.{BQ_DATASET}.INFORMATION_SCHEMA.TABLES`"
    result = bigquery_tool.invoke(test_sql)
    print(result)


bigquery_tool.description = f"{bigquery_tool.description}\n\n{TABLE_SCHEMA_DESCRIPTION.strip()}"
