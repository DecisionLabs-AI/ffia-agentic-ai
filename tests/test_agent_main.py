import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import agent.main as agent_main


class AgentMainTests(unittest.TestCase):
    def test_run_agent_passes_multi_turn_history_without_duplicating_current_user_message(self):
        history = [
            {"role": "user", "content": "What is diesel today?"},
            {"role": "assistant", "content": "It is 31 THB."},
            {"role": "user", "content": "How does that affect margins?"},
        ]

        fake_agent = Mock()
        fake_agent.invoke.return_value = {"messages": [AIMessage(content="Using prior context now.")]}

        with patch.object(agent_main, "_get_agent", return_value=fake_agent):
            agent_main.run_agent("How does that affect margins?", history)

        passed_messages = fake_agent.invoke.call_args.args[0]["messages"]
        self.assertEqual(
            [message.content for message in passed_messages],
            ["What is diesel today?", "It is 31 THB.", "How does that affect margins?"],
        )

    def test_run_agent_accepts_langchain_message_history(self):
        history = [
            HumanMessage(content="เมนูกะเพราขาย 100 บาท ต้นทุน 55 บาท"),
            AIMessage(content="รับทราบ"),
        ]
        fake_agent = Mock()
        fake_agent.invoke.return_value = {"messages": [AIMessage(content="Follow-up handled.")]}

        with patch.object(agent_main, "_get_agent", return_value=fake_agent):
            agent_main.run_agent("ถ้าลด 10% ยังไหวไหม", history)

        passed_messages = fake_agent.invoke.call_args.args[0]["messages"]
        self.assertEqual(
            [message.content for message in passed_messages],
            ["เมนูกะเพราขาย 100 บาท ต้นทุน 55 บาท", "รับทราบ", "ถ้าลด 10% ยังไหวไหม"],
        )

    def test_promo_follow_up_reuses_user_values_from_history(self):
        history = [
            {"role": "human", "content": "เมนูกะเพราขาย 100 บาท ต้นทุน 55 บาท"},
            {"role": "ai", "content": "บอกส่วนลดเพิ่มได้เลย"},
        ]

        self.assertIsNone(
            agent_main._build_promo_missing_inputs_reply("ถ้าลด 10% ยังไหวไหม", history)
        )

    def test_bundle_set_question_does_not_ask_for_discount_amount(self):
        message = (
            "ข้าวหน้าหมูหม่าล่ามีต้นทุน 38 บาท ถ้าจะจัดชุดขายราคา 99 บาท "
            "โดน GP 28% และต้องเหลือ margin หลัง GP อย่างน้อย 30% "
            "ต้นทุนรวมของทั้งชุดควรไม่เกินกี่บาท"
        )

        self.assertIsNone(agent_main._build_promo_missing_inputs_reply(message))
        result = agent_main.run_agent(message)

        self.assertNotIn("จำนวนส่วนลด", result["output"])
        self.assertIn("41.58", result["output"])
        self.assertIn("3.58", result["output"])

    def test_discount_promo_without_discount_value_still_asks_for_discount_amount(self):
        message = "อยากทำโปร กะเพราขาย 100 บาท ต้นทุน 55 บาท ยังคุ้มไหม"

        reply = agent_main._build_promo_missing_inputs_reply(message)

        self.assertIsNotNone(reply)
        self.assertIn("จำนวนส่วนลด", reply)

    def test_reasoning_trace_maps_tool_outputs_by_tool_call_id(self):
        messages = [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_search", "name": "search_tool", "args": {"query": "diesel"}},
                    {"id": "call_postgres", "name": "postgres_tool", "args": {"sql": "SELECT 1"}},
                ],
            ),
            ToolMessage(
                content="postgres rows",
                name="postgres_tool",
                tool_call_id="call_postgres",
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
                ("postgres_tool", "postgres rows"),
            ],
        )

    def test_invoice_questions_use_latest_invoice_for_current_user_only(self):
        with patch.object(agent_main, "get_latest_invoice", return_value={"invoice_no": "INV-001"}) as mock_latest:
            fake_agent = Mock()
            fake_agent.invoke.return_value = {"messages": [AIMessage(content="Scoped invoice answer.")]}
            with patch.object(agent_main, "_get_agent", return_value=fake_agent):
                agent_main.run_agent("analyze my invoice", current_user_id="alice")

        mock_latest.assert_called_once_with("alice")


if __name__ == "__main__":
    unittest.main()
