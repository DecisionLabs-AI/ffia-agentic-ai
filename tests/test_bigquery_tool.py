import unittest

from agent.tools.bigquery_tool import _validate_select_sql, bigquery_tool


class BigQueryToolSafetyTests(unittest.TestCase):
    def test_rejects_multi_statement_sql(self):
        result = bigquery_tool.invoke("SELECT 1; DELETE FROM `project.dataset.table` WHERE TRUE")
        self.assertIn("Multiple SQL statements", result)

    def test_rejects_mutation_keyword(self):
        is_valid, message = _validate_select_sql(
            "WITH danger AS (SELECT 1) SELECT * FROM danger MERGE target USING source ON TRUE"
        )
        self.assertFalse(is_valid)
        self.assertIn("Forbidden SQL keyword detected: MERGE", message)


if __name__ == "__main__":
    unittest.main()
