# =============================================================================
# FFIA — agent/main.py
# LangGraph ReAct agent with Gemini 2.5 Flash (Google AI API) + 2 tools:
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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

# Step 4: Import tools built in agent/tools/
from agent.tools.postgres_tool import (
    postgres_tool,
    reset_postgres_tool_user_id,
    set_postgres_tool_user_id,
)
from agent.tools.search_tool import search_tool
from data.db import get_latest_invoice


# Step 5: Load system prompt from file (kept in file, not hardcoded)
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"

def _load_system_prompt() -> str:
    """Read system prompt from file. Returns fallback string if file missing."""
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "You are FFIA, a restaurant cost optimization AI assistant for Bangkok."


# Step 6: Validate required environment variables at import time
def _validate_env():
    """Warn loudly if critical credentials are missing."""
    missing = []
    if not os.getenv("GOOGLE_API_KEY"):
        missing.append("GOOGLE_API_KEY")
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
        # Step 7a: Build LLM
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,            # Deterministic output for data analysis
            max_output_tokens=2048,
        )
        # Step 7b: Build agent graph (Thought/Action/Observation loop)
        _agent_instance = create_react_agent(
            model=llm,
            tools=[postgres_tool, search_tool],
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
    return bool(re.search(r"\binvoices?\b", user_message, flags=re.IGNORECASE))


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

    # Step 10a: Invoke the LangGraph agent
    agent_messages = _build_agent_messages(
        user_message,
        chat_history,
        latest_invoice,
        invoice_context_requested,
        invoice_context_error,
    )
    user_token = set_postgres_tool_user_id(current_user_id)
    try:
        result = _get_agent().invoke(
            {"messages": agent_messages},
            config={"callbacks": callbacks or []}
        )
    finally:
        reset_postgres_tool_user_id(user_token)

    # Step 10b: Extract final answer — normalize Gemini's content block list to plain string
    messages = result.get("messages", [])
    output = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
            output = _extract_text(msg.content)
            break

    # Step 10c: Extract intermediate steps (tool calls + observations) for the UI trace
    # Also normalize ToolMessage content to plain string
    intermediate_steps = _extract_intermediate_steps(messages)

    return {"output": output, "intermediate_steps": intermediate_steps}


# Step 11: CLI test block — run without Streamlit for quick verification
if __name__ == "__main__":
    print("FFIA ReAct Agent — W2 CLI Test")
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
