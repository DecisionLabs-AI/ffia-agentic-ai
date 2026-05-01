import types
import unittest
from unittest.mock import patch

from api.services import agent_service


class AgentServiceRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_db_intent_questions_inject_postgres_first_instruction(self):
        prompts = [
            "Based on my profile, what is my biggest cost risk?",
            "จากโปรไฟล์ร้าน ฉันเสี่ยงต้นทุนตรงไหนที่สุด",
            "ช่องทางเดลิเวอรี่ยังทำกำไรไหม",
            "จากใบเสร็จล่าสุด วัตถุดิบไหนแพงที่สุด",
        ]
        captured_messages = []

        def fake_run_agent(user_message, **kwargs):
            captured_messages.append((user_message, kwargs))
            return {
                "output": "ok",
                "intermediate_steps": [("postgres_tool", "db checked")],
            }

        fake_agent_pkg = types.ModuleType("agent")
        fake_agent_main = types.ModuleType("agent.main")
        fake_agent_main.run_agent = fake_run_agent

        with patch.dict(
            "sys.modules",
            {"agent": fake_agent_pkg, "agent.main": fake_agent_main},
        ):
            for prompt in prompts:
                result = await agent_service.ask_agent(prompt, user_id="user-1")
                self.assertEqual(result["trace"][0]["tool"], "postgres_tool")

        self.assertEqual(len(captured_messages), len(prompts))
        for routed_message, kwargs in captured_messages:
            self.assertIn("MUST call postgres_tool first", routed_message)
            self.assertIn("current_user_id", routed_message)
            self.assertIn("user_id = 'current_user_placeholder'", routed_message)
            self.assertEqual(kwargs["current_user_id"], "user-1")

    def test_non_db_question_is_not_rewritten(self):
        message = "What is diesel today?"

        self.assertEqual(
            agent_service._with_db_first_instruction(message, "user-1"),
            message,
        )


if __name__ == "__main__":
    unittest.main()
