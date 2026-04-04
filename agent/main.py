# =============================================================================
# FFIA — agent/main.py
# W2: LangGraph ReAct agent with Gemini 1.5 (Vertex AI) + 2 tools:
#   - BigQuerySQL: query restaurant cost data
#   - WebSearch: look up Bangkok oil prices and Thai fuel news
# =============================================================================

# Step 1: Load environment variables from .env BEFORE all other imports
# Security: API keys and credential paths must come from .env, never hardcoded
from dotenv import load_dotenv
load_dotenv()

# Step 2: Standard library imports + project root on path
import os
import sys
from pathlib import Path

# Add project root to sys.path so 'agent.tools.*' imports work when running
# this file directly (python3 agent/main.py) or via Streamlit (app/main.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 3: LangChain + LangGraph imports
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

# Step 4: Import tools built in agent/tools/
from agent.tools.bigquery_tool import bigquery_tool
from agent.tools.search_tool import search_tool


# Step 5: Load system prompt from file (kept in file, not hardcoded)
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"

def _load_system_prompt() -> str:
    """Read system prompt from file. Returns fallback string if file missing."""
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "You are FFIA, a restaurant cost optimization AI assistant for Bangkok."


# Step 6: Validate required GCP environment variables at import time
def _validate_env():
    """Warn loudly if critical credentials are missing."""
    missing = []
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        missing.append("GOOGLE_APPLICATION_CREDENTIALS")
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        missing.append("GOOGLE_CLOUD_PROJECT")
    if missing:
        print(f"WARNING: Missing env vars: {', '.join(missing)}. "
              "Copy .env.example to .env and set these values.", file=sys.stderr)

_validate_env()


# Step 7: Initialize Gemini 1.5 via Vertex AI
# ChatVertexAI uses GOOGLE_APPLICATION_CREDENTIALS (ADC) automatically
llm = ChatVertexAI(
    model_name="gemini-2.5-flash",
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-madt-ai"),
    location="us-central1",   # Nearest Vertex AI region to Bangkok
    temperature=0,            # Deterministic output for data analysis
    max_output_tokens=2048,
)

# Step 8: Collect tools and load system prompt
tools = [bigquery_tool, search_tool]
system_prompt = _load_system_prompt()

# Step 9: Create LangGraph ReAct agent
# create_react_agent handles the Thought/Action/Observation loop internally
# prompt= injects the system message so the agent knows its FFIA role
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=system_prompt,
)


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


# Step 11: Public function called by app/main.py
def run_agent(user_message: str, chat_history: list = None, callbacks: list = None) -> dict:
    """
    Run the FFIA ReAct agent and return a normalized result dict.

    Args:
        user_message: The user's question or input.
        chat_history: List of previous turns (kept for API compat, unused in ReAct).
        callbacks: LangChain callbacks, e.g. [StreamlitCallbackHandler(...)].

    Returns:
        dict with keys:
          "output"             — final answer as a clean plain string
          "intermediate_steps" — list of (tool_name: str, observation: str) tuples
    """
    # Step 10a: Invoke the LangGraph agent
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config={"callbacks": callbacks or []}
    )

    # Step 10b: Extract final answer — normalize Gemini's content block list to plain string
    messages = result.get("messages", [])
    output = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
            output = _extract_text(msg.content)
            break

    # Step 10c: Extract intermediate steps (tool calls + observations) for the UI trace
    # Also normalize ToolMessage content to plain string
    intermediate_steps = []
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                intermediate_steps.append((tc.get("name", "tool"), ""))
        if hasattr(msg, "name") and msg.name:  # ToolMessage
            if intermediate_steps:
                name, _ = intermediate_steps[-1]
                intermediate_steps[-1] = (name, _extract_text(msg.content))

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
