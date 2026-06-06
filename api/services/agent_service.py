"""Thin service adapter around the existing LangGraph agent."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from api.services.runtime_errors import (
    GCP_BILLING_DISABLED_ANSWER,
    GCP_BILLING_DISABLED_ERROR,
    is_gcp_billing_disabled_error,
)

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

# Step 0: Prompt injection & instruction-leak patterns
_PROMPT_INJECTION_PATTERN = re.compile(
    r"ignore\s+(previous|above|all|prior|your)\s+instructions?"
    r"|reveal\s+(your\s+)?(system\s+)?prompt"
    r"|show\s+(me\s+)?(your\s+)?(system\s+)?prompt"
    r"|what\s+(is|are)\s+(your\s+)?(system\s+)?(prompt|instructions|rules|configuration)"
    r"|repeat\s+(your\s+)?(system\s+)?instructions?"
    r"|print\s+(your\s+)?(system\s+)?prompt"
    r"|forget\s+(everything|all|your|what\s+you)"
    r"|disregard\s+(previous|all|your|above)"
    r"|you\s+are\s+now\s+(a|an)\s"
    r"|pretend\s+(you\s+(are|were)|to\s+be)"
    r"|act\s+as\s+(if\s+you|a|an)"
    r"|jailbreak|\bDAN\b|do\s+anything\s+now"
    r"|\[INST\]|\[SYS\]|<\|system\|>"
    r"|ลืม.*คำสั่ง|แสดง.*(system\s*prompt|คำสั่งระบบ)"
    r"|บอก.*(system\s*prompt|คำสั่งระบบ|prompt\s*ของ)"
    r"|ทำตัวเป็น.*AI|ข้ามคำสั่งเดิม|เปลี่ยนตัวเอง",
    re.IGNORECASE,
)

# Phrases that should never appear verbatim in a response (instruction leakage)
_INSTRUCTION_LEAK_PATTERN = re.compile(
    r"LANGUAGE LOCK\s*—\s*HIGHEST PRIORITY"
    r"|DB ROUTING INSTRUCTION"
    r"|current_user_placeholder"
    r"|MUST call postgres_tool first before"
    r"|PRICING DATA SOURCE PRIORITY\s*—\s*MANDATORY"
    r"|CONFIDENTIALITY\s*&\s*SECURITY GUARDRAIL",
    re.IGNORECASE,
)

_INJECTION_REFUSAL = (
    "ฉันไม่สามารถเปิดเผยหรือแก้ไขการตั้งค่าระบบได้ "
    "ถ้าอยากรู้เรื่องราคา ต้นทุน หรือการจัดการร้านอาหาร ถามได้เลยครับ"
)
_LEAK_REFUSAL = (
    "ขออภัย ไม่สามารถตอบคำถามนี้ได้ "
    "ถ้าอยากรู้เรื่องราคา ต้นทุน หรือการจัดการร้านอาหาร ถามได้เลยครับ"
)


def _is_prompt_injection(message: str) -> bool:
    """Return True when the message looks like a prompt injection attempt."""
    return bool(_PROMPT_INJECTION_PATTERN.search(message or ""))


def _has_instruction_leak(text: str) -> bool:
    """Return True when the response contains verbatim internal instruction text."""
    return bool(_INSTRUCTION_LEAK_PATTERN.search(text or ""))


_DB_INTENT_PATTERN = re.compile(
    r"(profile|business\s*risk|cost\s*risk|biggest\s+risk|my\s+business|my\s+restaurant"
    r"|channel|delivery|platform|invoice|receipt"
    r"|โปรไฟล์|ความเสี่ยง|เสี่ยง|ธุรกิจของฉัน|ร้านของฉัน|ร้านเรา|ร้านผม|ร้านฉัน|โปรไฟล์ร้าน"
    r"|ธุรกิจฉัน|เสี่ยงต้นทุน|ความเสี่ยงต้นทุน|ต้นทุนตรงไหน|จากข้อมูลร้าน"
    r"|ช่องทางเดลิเวอรี่|ช่องทาง|เดลิเวอรี่|เดลิเวอรี|แพลตฟอร์ม|ใบเสร็จ|บิล)",
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

    # Step 1: Input guard — block prompt injection attempts before reaching the agent
    if _is_prompt_injection(clean_message):
        logger.warning("Prompt injection attempt blocked: %.120s", clean_message)
        return {"answer": _INJECTION_REFUSAL, "trace": [], "error": "prompt_injection_blocked"}

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
        answer = str(result.get("output", "")).strip()
        # Step 2: Output guard — scrub responses that contain verbatim internal instructions
        if _has_instruction_leak(answer):
            logger.warning("Instruction leak detected in agent output; replacing with safe refusal")
            answer = _LEAK_REFUSAL
        return {
            "answer": answer,
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
    except Exception as exc:
        if is_gcp_billing_disabled_error(exc):
            logger.warning("FFIA agent unavailable because GCP billing is disabled: %s", exc)
            return {
                "answer": GCP_BILLING_DISABLED_ANSWER,
                "trace": [],
                "error": GCP_BILLING_DISABLED_ERROR,
            }

        logger.exception("FFIA agent call failed")
        return {
            "answer": "ขออภัย ตอนนี้ FFIA วิเคราะห์คำถามนี้ไม่สำเร็จ ลองถามใหม่ให้สั้นลงหรือเช็กการตั้งค่าระบบอีกครั้ง",
            "trace": [],
            "error": "agent_unavailable",
        }
