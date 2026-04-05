import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

import agent.main as agent_main


class AgentMainTests(unittest.TestCase):
    def test_run_agent_passes_multi_turn_history_without_duplicating_current_user_message(self):
        history = [
            {"role": "user", "content": "What is diesel today?"},
            {"role": "assistant", "content": "It is 31 THB."},
            {"role": "user", "content": "How does that affect margins?"},
        ]

        with patch.object(
            agent_main.agent,
            "invoke",
            return_value={"messages": [AIMessage(content="Using prior context now.")]},
        ) as mock_invoke:
            agent_main.run_agent("How does that affect margins?", history)

        passed_messages = mock_invoke.call_args.args[0]["messages"]
        self.assertEqual(
            [message.content for message in passed_messages],
            ["What is diesel today?", "It is 31 THB.", "How does that affect margins?"],
        )

    def test_reasoning_trace_maps_tool_outputs_by_tool_call_id(self):
        messages = [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_search", "name": "search_tool", "args": {"query": "diesel"}},
                    {"id": "call_bigquery", "name": "bigquery_tool", "args": {"sql": "SELECT 1"}},
                ],
            ),
            ToolMessage(
                content="bigquery rows",
                name="bigquery_tool",
                tool_call_id="call_bigquery",
            ),
            ToolMessage(
                content="search results",
                name="search_tool",
                tool_call_id="call_search",
            ),
        ]

        trace = agent_main._extract_intermediate_steps(messages)

        self.assertEqual(
            trace,
            [
                ("search_tool", "search results"),
                ("bigquery_tool", "bigquery rows"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
