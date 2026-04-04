# =============================================================================
# FFIA — BigQuery SQL Execution Tool (W2)
# Allows the ReAct agent to query restaurant cost data from BigQuery.
# =============================================================================

# Step 1: Imports
import os
from dotenv import load_dotenv
from google.cloud import bigquery
from langchain.tools import Tool

load_dotenv()

# Step 2: Read project and dataset from environment (never hardcoded)
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-madt-ai")
BQ_DATASET = os.getenv("BIGQUERY_DATASET", "data_source")
BQ_LOCATION = os.getenv("BIGQUERY_LOCATION", "asia-southeast3")

# Step 3: Table schema description — tells the LLM what tables and columns exist
# so it can write correct SQL without hallucinating schema.
# TODO: Replace the placeholder below with the actual schema from gcp-madt-ai.data_source
# Format: "Table: <dataset>.<table> — columns: col1 (TYPE), col2 (TYPE), ..."
TABLE_SCHEMA_DESCRIPTION = """
Available tables in BigQuery dataset `gcp-madt-ai.data_source`:

*** REPLACE THIS BLOCK WITH YOUR ACTUAL SCHEMA ***
Example format:
  Table: data_source.restaurant_costs — columns: restaurant_id (STRING), menu_item (STRING),
    ingredient_cost_thb (FLOAT), delivery_fee_thb (FLOAT), selling_price_thb (FLOAT),
    recorded_date (DATE)
  Table: data_source.oil_prices — columns: price_date (DATE), diesel_price_thb (FLOAT),
    gasohol_price_thb (FLOAT), source (STRING)
*** END REPLACE ***

Always use fully-qualified table names: `gcp-madt-ai.data_source.<table_name>`
"""


# Step 4: Core query function with security guardrails
def run_bigquery_query(sql: str) -> str:
    """Execute a SELECT SQL query against BigQuery and return results as a string."""

    # Step 4a: Security guardrail — only SELECT statements allowed
    if not sql.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are permitted. Mutations are not allowed."

    try:
        # Step 4b: Initialize BigQuery client (picks up GOOGLE_APPLICATION_CREDENTIALS from env)
        client = bigquery.Client(project=GCP_PROJECT)

        # Step 4c: Inject LIMIT 50 if not already present to cap cost/output
        sql_upper = sql.upper()
        if "LIMIT" not in sql_upper:
            sql = sql.rstrip(";").strip() + " LIMIT 50"

        # Step 4d: Execute query
        query_job = client.query(sql, location=BQ_LOCATION)
        df = query_job.to_dataframe()

        # Step 4e: Return empty message or markdown table
        if df.empty:
            return "Query returned no results."
        return df.to_markdown(index=False)

    except Exception as e:
        # Step 4f: Return error string — never raise, so agent can handle gracefully
        return f"BigQuery error: {str(e)}"


# Step 5: Wrap in LangChain Tool for the ReAct agent
bigquery_tool = Tool(
    name="BigQuerySQL",
    func=run_bigquery_query,
    description=(
        "Use this tool to query restaurant cost and oil price data from BigQuery. "
        f"{TABLE_SCHEMA_DESCRIPTION}"
        "Input MUST be a valid SQL SELECT statement using fully-qualified table names. "
        "Example: SELECT * FROM `gcp-madt-ai.data_source.restaurant_costs` LIMIT 5"
    ),
)


# Step 6: Standalone test block
if __name__ == "__main__":
    print("Testing BigQuery tool...")
    test_sql = f"SELECT * FROM `{GCP_PROJECT}.{BQ_DATASET}.INFORMATION_SCHEMA.TABLES`"
    result = run_bigquery_query(test_sql)
    print(result)
