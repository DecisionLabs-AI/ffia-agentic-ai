import json
import unittest
from unittest.mock import patch

from agent.tools.platform_gp_lookup_tool import platform_gp_lookup_tool, resolve_platform_gp_pct


class _DummyCursor:
    def execute(self, *_args, **_kwargs):
        return None

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False


class _DummyConnection:
    def cursor(self):
        return _DummyCursor()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False


class PlatformGpLookupToolTests(unittest.TestCase):
    def test_resolve_returns_error_without_user_context(self):
        with patch("agent.tools.platform_gp_lookup_tool.get_postgres_tool_user_id", return_value=None):
            result = resolve_platform_gp_pct("Grab")
        self.assertEqual(result["status"], "error")
        self.assertIn("authenticated user context", result["message"])

    def test_resolve_uses_restaurant_channel_mix_first(self):
        with patch("agent.tools.platform_gp_lookup_tool.get_postgres_tool_user_id", return_value="user-1"):
            with patch("agent.tools.platform_gp_lookup_tool._get_database_url", return_value="postgres://db"):
                with patch("agent.tools.platform_gp_lookup_tool.psycopg2.connect", return_value=_DummyConnection()):
                    with patch(
                        "agent.tools.platform_gp_lookup_tool._lookup_user_channel_gp",
                        return_value=("Grab Food", 30.0, 40.0),
                    ):
                        with patch("agent.tools.platform_gp_lookup_tool._lookup_global_platform_fee") as fallback_lookup:
                            result = resolve_platform_gp_pct("Grab")

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["source"], "restaurant_channel_mix")
        self.assertEqual(result["platform"], "Grab Food")
        self.assertEqual(result["gp_pct"], 0.3)
        fallback_lookup.assert_not_called()

    def test_resolve_falls_back_to_platform_fee_when_channel_mix_missing(self):
        with patch("agent.tools.platform_gp_lookup_tool.get_postgres_tool_user_id", return_value="user-1"):
            with patch("agent.tools.platform_gp_lookup_tool._get_database_url", return_value="postgres://db"):
                with patch("agent.tools.platform_gp_lookup_tool.psycopg2.connect", return_value=_DummyConnection()):
                    with patch("agent.tools.platform_gp_lookup_tool._lookup_user_channel_gp", return_value=None):
                        with patch(
                            "agent.tools.platform_gp_lookup_tool._lookup_global_platform_fee",
                            return_value=("Grab", 30.0),
                        ):
                            result = resolve_platform_gp_pct("Grab")

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["source"], "platform_fee")
        self.assertEqual(result["gp_pct"], 0.3)

    def test_tool_returns_json_when_lookup_is_missing(self):
        with patch("agent.tools.platform_gp_lookup_tool.resolve_platform_gp_pct", return_value={
            "status": "missing",
            "needs_user_input": True,
            "missing_input": "gp_pct",
        }):
            output = platform_gp_lookup_tool.invoke({"platform_name": "Unknown"})

        parsed = json.loads(output)
        self.assertEqual(parsed["status"], "missing")
        self.assertTrue(parsed["needs_user_input"])


if __name__ == "__main__":
    unittest.main()
