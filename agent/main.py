# =============================================================================
# FFIA — agent/main.py
# LangGraph ReAct agent with Gemini 2.5 Flash (Vertex AI) + 2 tools:
#   - PostgreSQL: query restaurant cost data
#   - WebSearch: look up Bangkok oil prices and Thai fuel news
# =============================================================================

# Step 1: Load environment variables from .env BEFORE all other imports
# Security: API keys and credential paths must come from .env, never hardcoded
from dotenv import load_dotenv
load_dotenv()

# Step 2: Standard library imports + project root on path
import json
import os
import re
import sys
from pathlib import Path

# Add project root to sys.path so 'agent.tools.*' imports work when running
# this file directly (python3 agent/main.py) or via Streamlit (app/main.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 3: LangChain + LangGraph imports
from langchain_google_vertexai import ChatVertexAI
from google.oauth2 import service_account
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.errors import GraphRecursionError

# Step 4: Import tools built in agent/tools/
from agent.tools.postgres_tool import (
    postgres_tool,
    reset_postgres_tool_user_id,
    set_postgres_tool_user_id,
)
from agent.tools.search_tool import search_tool
from agent.tools.oil_price_tool import oil_price_tool
from agent.tools.ingredient_price_tool import ingredient_price_tool
from agent.tools.business_rules_tool import (
    platform_floor_guard_tool,
    promo_profitability_tool,
    cogs_alert_tool,
    scenario_classifier_tool,
)
from data.db import get_latest_invoice, fetch_latest_restaurant_profile


# Step 5: Load system prompt from file (kept in file, not hardcoded)
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"

def _load_system_prompt() -> str:
    """Read system prompt from file. Returns fallback string if file missing."""
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "You are FFIA, a restaurant cost optimization AI assistant for Bangkok."


# Step 6: Runtime-configurable model and region — read after load_dotenv() has run.
# Defaults keep behaviour identical to the previous hardcoded values.
_AGENT_MODEL     = os.getenv("FFIA_AGENT_MODEL", "gemini-2.5-flash")
_VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "asia-southeast1")


def _validate_env():
    """Warn loudly if critical credentials are missing."""
    missing = []
    if not os.getenv("GCP_PROJECT_ID"):
        missing.append("GCP_PROJECT_ID")
    if not os.getenv("DATABASE_URL"):
        missing.append("DATABASE_URL")
    if missing:
        print(f"WARNING: Missing env vars: {', '.join(missing)}. "
              "Copy .env.example to .env and set these values.", file=sys.stderr)

_validate_env()


# Step 7: Lazy agent singleton — created only on first run_agent() call, not at import time.
# This prevents Gemini LLM + LangGraph graph construction from running on every Streamlit rerun.
_agent_instance = None

def _get_agent():
    """Return the LangGraph ReAct agent, constructing it once on first call."""
    global _agent_instance
    if _agent_instance is None:
        # Step 7a: Build credentials — load from JSON string (Streamlit Cloud) or fall back to ADC
        _creds_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
        _credentials = None
        if _creds_json:
            _creds_dict = json.loads(_creds_json)
            _credentials = service_account.Credentials.from_service_account_info(
                _creds_dict,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        # Step 7b: Build LLM — model/location from env (FFIA_AGENT_MODEL, VERTEX_LOCATION)
        llm = ChatVertexAI(
            model=_AGENT_MODEL,
            project=os.getenv("GCP_PROJECT_ID"),
            location=_VERTEX_LOCATION,
            credentials=_credentials,
            temperature=0,
            max_output_tokens=4096,
        )
        # Step 7b: Build agent graph (Thought/Action/Observation loop)
        _agent_instance = create_react_agent(
            model=llm,
            tools=[
                postgres_tool,
                search_tool,
                oil_price_tool,
                ingredient_price_tool,
                platform_floor_guard_tool,
                promo_profitability_tool,
                cogs_alert_tool,
                scenario_classifier_tool,
            ],
            prompt=_load_system_prompt(),
        )
    return _agent_instance


# Step 10: Helper — normalize Gemini's content block list to a plain string
# Gemini 2.5 Flash returns AIMessage.content as a list of dicts:
# [{'type': 'text', 'text': '...', 'thought_signature': '...'}]
# This strips out everything except the 'text' values.
def _extract_text(content) -> str:
    """Convert Gemini content blocks or any content type to a clean plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


MAX_CHAT_HISTORY_MESSAGES = 12


def _should_inject_latest_invoice(user_message: str) -> bool:
    """Return True when the user is asking about an invoice."""
    return bool(re.search(
        r"\binvoices?\b|receipt|latest\s+bill|ใบเสร็จ|บิล|วัตถุดิบ",
        user_message,
        flags=re.IGNORECASE,
    ))


_PROFILE_QUESTION_PATTERN = re.compile(
    r"(profile|โปรไฟล์|โปรไฟล์ร้าน"
    r"|biggest.cost.risk|cost.risk"
    r"|what.should.i.optim|ควรปรับ|ควรทำอะไร"
    r"|based.on.my|จากโปรไฟล์|จากข้อมูลร้าน"
    r"|my.restaurant|my.business|ร้านของฉัน|ร้านฉัน|ธุรกิจของฉัน|ธุรกิจฉัน"
    r"|am.i.at.risk|เสี่ยงไหม|เสี่ยงต้นทุน|ความเสี่ยงต้นทุน"
    r"|how.is.my.restaurant"
    r"|biggest.risk|ความเสี่ยงหลัก|ต้นทุนตรงไหน"
    r"|should.i.optimize|optimize.my"
    r"|ช่องทางเดลิเวอรี่"
    r"|ปัญหาหลัก|ร้านเป็นยังไง)",
    re.IGNORECASE,
)


def _is_profile_question(user_message: str) -> bool:
    """Return True when the question requires restaurant profile context."""
    return bool(_PROFILE_QUESTION_PATTERN.search(user_message))


_PROMO_QUESTION_PATTERN = re.compile(
    r"(โปร(?!ไฟล์)|โปรโมชั่น|ส่วนลด|ลดราคา|discount|promo|promotion|flash sale|price cut)",
    re.IGNORECASE,
)
_PROMO_DISCOUNT_VALUE_PATTERN = re.compile(
    r"(?:(?:ลด|ส่วนลด|discount|promo(?:tion)?|flash\s*sale|price cut|โปร(?![ก-๙A-Za-z])|โปรโมชั่น)[^0-9]{0,15}\d+(?:\.\d+)?\s*(?:บาท|baht|฿|%|percent|pct|เปอร์เซ็นต์)?)"
    r"|(?:\d+(?:\.\d+)?\s*(?:บาท|baht|฿|%|percent|pct|เปอร์เซ็นต์)\s*(?:ส่วนลด|discount|promo(?:tion)?|off|ลด|flash\s*sale|โปร(?![ก-๙A-Za-z])|โปรโมชั่น))",
    re.IGNORECASE,
)
_PROMO_PRICE_VALUE_PATTERN = re.compile(
    r"(?:ราคา|ขาย|price|selling|menu price|gross_revenue)[^0-9]{0,15}\d+(?:\.\d+)?\s*(?:บาท|baht|฿)?",
    re.IGNORECASE,
)
_PROMO_COST_OR_MARGIN_PATTERN = re.compile(
    r"(?:ต้นทุน|cost|cogs|gp|margin|มาร์จิ้น|กำไรขั้นต้น|กำไรสุทธิ)[^0-9]{0,15}\d+(?:\.\d+)?\s*(?:บาท|baht|฿|%|percent|pct|เปอร์เซ็นต์)?",
    re.IGNORECASE,
)


def _is_thai_message(text: str) -> bool:
    """Return True when the message contains Thai characters."""
    return bool(re.search(r"[ก-๙]", text or ""))


def _build_promo_missing_inputs_reply(user_message: str) -> str | None:
    """Return a minimal follow-up question when promo viability inputs are insufficient."""
    # Profile, invoice, and tenant data questions must not be downgraded into
    # promo clarification just because Thai profile text contains "โปร".
    if _is_profile_question(user_message) or _should_inject_latest_invoice(user_message):
        return None

    if not _PROMO_QUESTION_PATTERN.search(user_message or ""):
        return None

    # Safety: evaluate promo inputs from the current user message only.
    context_text = str(user_message or "")
    has_discount = bool(_PROMO_DISCOUNT_VALUE_PATTERN.search(context_text))
    has_price = bool(_PROMO_PRICE_VALUE_PATTERN.search(context_text))
    has_cost_or_margin = bool(_PROMO_COST_OR_MARGIN_PATTERN.search(context_text))

    missing: list[str] = []
    if not has_discount:
        missing.append("discount")
    if not has_price:
        missing.append("price")
    if not has_cost_or_margin:
        missing.append("cost_or_margin")

    if not missing:
        return None

    ask_keys = missing[:2]
    is_thai = _is_thai_message(user_message)
    if is_thai:
        label_map = {
            "discount": "จำนวนส่วนลด (บาทหรือ %)",
            "price": "ราคาขายก่อนลด",
            "cost_or_margin": "ต้นทุนต่อจานหรือ GP% ปัจจุบัน",
        }
        labels = [label_map[k] for k in ask_keys]
        joined = f"{labels[0]} และ {labels[1]}" if len(labels) == 2 else labels[0]
        return (
            f"เพื่อเช็กว่าโปรนี้ยังคุ้มไหม รบกวนระบุ {joined} "
            "แล้วฉันจะสรุปให้ทันที"
        )

    label_map = {
        "discount": "discount amount (THB or %)",
        "price": "pre-discount selling price",
        "cost_or_margin": "cost per dish or current GP%",
    }
    labels = [label_map[k] for k in ask_keys]
    joined = f"{labels[0]} and {labels[1]}" if len(labels) == 2 else labels[0]
    return (
        f"To check promo viability, please share {joined}. "
        "I will conclude right away."
    )


def _build_profile_context_message(profile: dict) -> str:
    """Format the restaurant profile as structured context for the agent."""
    return (
        "Restaurant profile loaded from PostgreSQL. Use these margin thresholds and "
        "restaurant attributes as the anchor for all profile-based analysis. "
        "Do NOT ask the user for this information — it is already here.\n\n"
        f"{json.dumps(profile, ensure_ascii=False, indent=2, default=str)}"
    )


def _build_invoice_context_message(invoice: dict) -> str:
    """Format the latest saved invoice as structured context for the agent."""
    return (
        "Latest saved invoice from PostgreSQL. Use this data when answering the user's "
        "invoice question, and treat it as the primary invoice source unless the user "
        "asks about a different invoice.\n\n"
        f"{json.dumps(invoice, ensure_ascii=False, indent=2, default=str)}"
    )


def _build_agent_messages(
    user_message: str,
    chat_history: list | None = None,
    latest_invoice: dict | None = None,
    invoice_context_requested: bool = False,
    invoice_context_error: str = "",
    restaurant_profile: dict | None = None,
    profile_context_requested: bool = False,
    profile_context_error: str = "",
) -> list:
    """Convert UI chat history into LangChain message objects without duplicating the current turn."""
    history = list(chat_history or [])

    if history:
        last_message = history[-1]
        if (
            last_message.get("role") in {"user", "human"}
            and str(last_message.get("content", "")).strip() == user_message.strip()
        ):
            history = history[:-1]

    relevant_history = history[-MAX_CHAT_HISTORY_MESSAGES:]
    messages = []

    for item in relevant_history:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if role in {"user", "human"}:
            messages.append(HumanMessage(content=content))
        elif role in {"assistant", "ai"}:
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(SystemMessage(content=content))

    if latest_invoice:
        messages.append(SystemMessage(content=_build_invoice_context_message(latest_invoice)))
    elif invoice_context_error:
        messages.append(SystemMessage(
            content=(
                "The user asked about an invoice, but the latest invoice could not be loaded "
                f"from PostgreSQL: {invoice_context_error}. Do not claim to have invoice data "
                "unless it is provided elsewhere in the conversation."
            )
        ))
    elif invoice_context_requested:
        messages.append(SystemMessage(
            content=(
                "The user asked about an invoice, but no saved invoice was found in PostgreSQL. "
                "Do not claim to have invoice data unless it is provided elsewhere in the conversation."
            )
        ))

    # Step 8b: Inject restaurant profile context for profile-based questions
    if restaurant_profile:
        messages.append(SystemMessage(content=_build_profile_context_message(restaurant_profile)))
    elif profile_context_error:
        messages.append(SystemMessage(
            content=(
                "The user asked a profile-based question, but the restaurant profile could not "
                f"be loaded from PostgreSQL: {profile_context_error}. Inform the user that their "
                "profile could not be retrieved and ask them to check the Business Profile Settings."
            )
        ))
    elif profile_context_requested:
        messages.append(SystemMessage(
            content=(
                "The user asked a profile-based question, but no saved restaurant profile was "
                "found in PostgreSQL. Ask the user to complete their Business Profile Settings first."
            )
        ))

    messages.append(HumanMessage(content=user_message))
    return messages


def _extract_intermediate_steps(messages: list) -> list[tuple[str, str]]:
    """Map tool outputs to their matching tool calls, even when calls complete out of order."""
    intermediate_steps = []
    tool_call_index: dict[str, int] = {}

    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None) or []
        for tool_call in tool_calls:
            step_index = len(intermediate_steps)
            tool_name = tool_call.get("name", "tool")
            tool_call_id = tool_call.get("id")
            intermediate_steps.append((tool_name, ""))
            if tool_call_id:
                tool_call_index[tool_call_id] = step_index

        tool_name = getattr(msg, "name", None)
        tool_call_id = getattr(msg, "tool_call_id", None)
        if not tool_name:
            continue

        target_index = None
        if tool_call_id and tool_call_id in tool_call_index:
            target_index = tool_call_index[tool_call_id]
        else:
            for index, (existing_name, observation) in enumerate(intermediate_steps):
                if existing_name == tool_name and not observation:
                    target_index = index
                    break

        if target_index is not None:
            intermediate_steps[target_index] = (intermediate_steps[target_index][0], _extract_text(msg.content))

    return intermediate_steps


# Step 11: Public function called by app/main.py
def run_agent(
    user_message: str,
    chat_history: list = None,
    callbacks: list = None,
    current_user_id: str | None = None,
) -> dict:
    """
    Run the FFIA ReAct agent and return a normalized result dict.

    Args:
        user_message: The user's question or input.
        chat_history: List of previous turns (kept for API compat, unused in ReAct).
        callbacks: LangChain callbacks, e.g. [StreamlitCallbackHandler(...)].
        current_user_id: Authenticated tenant identifier for invoice scoping.

    Returns:
        dict with keys:
          "output"             — final answer as a clean plain string
          "intermediate_steps" — list of (tool_name: str, observation: str) tuples
    """
    # Step 10a: Strict promo stop rule — ask only minimum missing inputs and stop early.
    promo_missing_reply = _build_promo_missing_inputs_reply(user_message)
    if promo_missing_reply:
        return {"output": promo_missing_reply, "intermediate_steps": []}

    latest_invoice = None
    invoice_context_error = ""
    invoice_context_requested = _should_inject_latest_invoice(user_message)
    if invoice_context_requested:
        try:
            if current_user_id:
                latest_invoice = get_latest_invoice(current_user_id)
            else:
                invoice_context_error = "No authenticated user context was provided."
        except Exception as exc:
            invoice_context_error = str(exc)

    # Step 10b: Pre-fetch restaurant profile for profile-based questions
    restaurant_profile = None
    profile_context_error = ""
    profile_context_requested = _is_profile_question(user_message)
    if profile_context_requested:
        try:
            if current_user_id:
                restaurant_profile = fetch_latest_restaurant_profile(current_user_id)
            else:
                profile_context_error = "No authenticated user context was provided."
        except Exception as exc:
            profile_context_error = str(exc)

    # Step 10c: Invoke the LangGraph agent
    agent_messages = _build_agent_messages(
        user_message,
        chat_history,
        latest_invoice,
        invoice_context_requested,
        invoice_context_error,
        restaurant_profile,
        profile_context_requested,
        profile_context_error,
    )
    user_token = set_postgres_tool_user_id(current_user_id)
    try:
        try:
            result = _get_agent().invoke(
                {"messages": agent_messages},
                config={"callbacks": callbacks or [], "recursion_limit": 9}
            )
        except GraphRecursionError:
            fallback_output = (
                "ฉันยังสรุปคำตอบไม่จบในรอบนี้ ลองระบุข้อมูลเพิ่มอีกนิด หรือถามให้แคบลงได้เลย"
                if _is_thai_message(user_message)
                else (
                    "I couldn't finish the reasoning in this run. "
                    "Please narrow the question or provide a bit more detail."
                )
            )
            return {"output": fallback_output, "intermediate_steps": []}
    finally:
        reset_postgres_tool_user_id(user_token)

    # Step 10d: Extract final answer — normalize Gemini's content block list to plain string
    messages = result.get("messages", [])
    output = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
            output = _extract_text(msg.content)
            break

    # Step 10e: Extract intermediate steps (tool calls + observations) for the UI trace
    # Also normalize ToolMessage content to plain string
    intermediate_steps = _extract_intermediate_steps(messages)

    return {"output": output, "intermediate_steps": intermediate_steps}


# Step 11: CLI test block — run without Streamlit for quick verification
if __name__ == "__main__":
    print("FFIA ReAct Agent — W4 CLI Test")
    print("Type your message (Ctrl+C to quit)\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            result = run_agent(user_input)
            print(f"\nFFIA: {result['output']}\n")

            steps = result.get("intermediate_steps", [])
            if steps:
                print(f"  [{len(steps)} tool call(s) made]")
                for tool_name, observation in steps:
                    print(f"  -> {tool_name}: {str(observation)[:120]}")
            print()

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
