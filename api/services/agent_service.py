"""Thin service adapter around the existing LangGraph agent."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

_DB_INTENT_PATTERN = re.compile(
    r"(profile|business\s*risk|cost\s*risk|biggest\s+risk|my\s+business|my\s+restaurant"
    r"|channel|delivery|platform|invoice|receipt"
    r"|โปรไฟล์|ความเสี่ยง|เสี่ยง|ธุรกิจของฉัน|ร้านของฉัน|ร้านเรา|ร้านผม|ร้านฉัน|โปรไฟล์ร้าน"
    r"|ช่องทาง|เดลิเวอรี่|เดลิเวอรี|แพลตฟอร์ม|ใบเสร็จ|บิล)",
    re.IGNORECASE,
)


def _requires_db_first(message: str) -> bool:
    """Return True when the question needs tenant DB context before answering."""
    return bool(_DB_INTENT_PATTERN.search(message or ""))


def _with_db_first_instruction(message: str, user_id: str | None) -> str:
    """Inject a minimal routing instruction for tenant-business questions."""
    if not user_id or not _requires_db_first(message):
        return message

    return (
        "DB ROUTING INSTRUCTION: This is a tenant-specific profile/risk/channel/"
        "invoice/my-business question. You MUST call postgres_tool first before "
        "answering. The authenticated current_user_id is already bound in the "
        "postgres_tool session context; filter tenant-scoped SQL with "
        "user_id = 'current_user_placeholder'. Do not answer from generic knowledge.\n\n"
        f"User question: {message}"
    )


def _agent_timeout_seconds() -> float:
    raw = os.getenv("FFIA_AGENT_TIMEOUT_SECONDS", "60").strip()
    try:
        parsed = float(raw)
    except ValueError:
        return 60.0
    return parsed if parsed > 0 else 60.0


def _normalize_trace(raw_steps: list[Any]) -> list[dict[str, str]]:
    trace: list[dict[str, str]] = []
    for item in raw_steps or []:
        if isinstance(item, dict):
            trace.append({
                "tool": str(item.get("tool", "")),
                "observation": str(item.get("observation", "")),
            })
            continue
        try:
            tool, observation = item
        except (TypeError, ValueError):
            continue
        trace.append({"tool": str(tool), "observation": str(observation)})
    return trace


def _graph_recursion_error_types() -> tuple[type[BaseException], ...]:
    try:
        from langgraph.errors import GraphRecursionError
    except Exception:
        return ()
    return (GraphRecursionError,)


async def ask_agent(
    message: str,
    user_id: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Call agent.main.run_agent() without changing the agent implementation."""
    clean_message = str(message or "").strip()
    if not clean_message:
        return {
            "answer": "",
            "trace": [],
            "error": "กรุณาพิมพ์คำถามก่อนส่งให้ FFIA",
        }

    def _run() -> dict[str, Any]:
        from agent.main import run_agent

        return run_agent(
            user_message=_with_db_first_instruction(clean_message, user_id),
            chat_history=history or [],
            callbacks=[],
            current_user_id=user_id,
        )

    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(_executor, _run),
            timeout=_agent_timeout_seconds(),
        )
        return {
            "answer": str(result.get("output", "")).strip(),
            "trace": _normalize_trace(result.get("intermediate_steps", [])),
            "error": None,
        }
    except asyncio.TimeoutError:
        logger.exception("FFIA agent call timed out")
        return {
            "answer": "ขออภัย ตอนนี้ FFIA ใช้เวลาวิเคราะห์นานเกินไป ลองถามใหม่ให้สั้นลงหรือรอสักครู่แล้วลองอีกครั้ง",
            "trace": [],
            "error": "agent_timeout",
        }
    except _graph_recursion_error_types():
        logger.exception("FFIA agent hit graph recursion limit")
        return {
            "answer": "ฉันยังสรุปคำตอบไม่จบในรอบนี้ ลองถามให้แคบลงหรือเพิ่มข้อมูลสำคัญอีกนิดได้เลย",
            "trace": [],
            "error": "agent_recursion_limit",
        }
    except Exception:
        logger.exception("FFIA agent call failed")
        return {
            "answer": "ขออภัย ตอนนี้ FFIA วิเคราะห์คำถามนี้ไม่สำเร็จ ลองถามใหม่ให้สั้นลงหรือเช็กการตั้งค่าระบบอีกครั้ง",
            "trace": [],
            "error": "agent_unavailable",
        }
