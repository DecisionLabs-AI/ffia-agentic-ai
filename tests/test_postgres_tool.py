import unittest

from agent.tools.postgres_tool import _validate_select_sql, postgres_tool


class PostgresToolSafetyTests(unittest.TestCase):
    def test_rejects_multi_statement_sql(self):
        result = postgres_tool.invoke("SELECT 1; DELETE FROM invoice_items WHERE TRUE")
        self.assertIn("Multiple SQL statements", result)

    def test_rejects_mutation_keyword(self):
        is_valid, message = _validate_select_sql(
            "WITH danger AS (SELECT 1) SELECT * FROM danger MERGE target USING source ON TRUE"
        )
        self.assertFalse(is_valid)
        self.assertIn("Forbidden SQL keyword detected: MERGE", message)

    def test_blocks_invoice_queries_without_authenticated_user_context(self):
        result = postgres_tool.invoke("SELECT * FROM invoices")
        self.assertIn("authenticated user context", result)


if __name__ == "__main__":
    unittest.main()
