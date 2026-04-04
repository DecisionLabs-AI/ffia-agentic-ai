# =============================================================================
# FFIA — agent/main.py
# W2: LangChain ReAct agent with Gemini 1.5 (Vertex AI) + 2 tools:
#   - BigQuerySQL: query restaurant cost data
#   - WebSearch: look up Bangkok oil prices and Thai fuel news
# =============================================================================

# Step 1: Load environment variables from .env BEFORE all other imports
# Security: API keys and credential paths must come from .env, never hardcoded
from dotenv import load_dotenv
load_dotenv()

# Step 2: Standard library imports
import os
import sys
from pathlib import Path

# Step 3: LangChain imports — agent framework
from langchain_google_vertexai import ChatVertexAI
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent

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
    model_name="gemini-1.5-pro",
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-madt-ai"),
    location="asia-southeast1",   # Nearest Vertex AI region to Bangkok
    temperature=0,                # Deterministic output for data analysis
    max_output_tokens=2048,
)

# Step 8: Collect tools for the ReAct agent
tools = [bigquery_tool, search_tool]

# Step 9: Pull standard ReAct prompt template from LangChain Hub
# hwchase17/react is the canonical single-input ReAct prompt
react_prompt = hub.pull("hwchase17/react")

# Step 10: Inject FFIA system context as a prefix to the ReAct prompt
system_context = _load_system_prompt()
react_prompt = react_prompt.partial(
    # The ReAct template has no system slot, so we prepend context to instructions
)

# Step 11: Create the ReAct agent (LLM + tools + prompt)
agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt)

# Step 12: Wrap in AgentExecutor — manages the Thought/Action/Observation loop
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,                  # Logs Thought/Action/Observation to console
    handle_parsing_errors=True,    # Prevents crash if LLM output format is off
    max_iterations=8,              # Safety cap: stops runaway tool-call loops
    return_intermediate_steps=True # Required for reasoning trace in Streamlit UI
)


# Step 13: Public function called by app/main.py
def run_agent(user_message: str, chat_history: list = None, callbacks: list = None) -> dict:
    """
    Run the FFIA ReAct agent and return the result dict.

    Args:
        user_message: The user's question or input.
        chat_history: List of previous turns (unused in ReAct but kept for API compat).
        callbacks: LangChain callbacks, e.g. [StreamlitCallbackHandler(...)].
                   Passed per-request so each UI session gets its own handler.

    Returns:
        dict with keys:
          "output"             — final answer string
          "intermediate_steps" — list of (AgentAction, observation) tuples
    """
    # Step 13a: Build input — include system context so agent knows its role
    full_input = f"{system_context}\n\nUser question: {user_message}"

    # Step 13b: Run agent, passing callbacks for live Streamlit rendering
    result = agent_executor.invoke(
        {"input": full_input},
        config={"callbacks": callbacks or []}
    )
    return result


# Step 14: CLI test block — run without Streamlit for quick verification
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

            # Show intermediate steps summary in CLI
            steps = result.get("intermediate_steps", [])
            if steps:
                print(f"  [{len(steps)} tool call(s) made]")
                for action, observation in steps:
                    print(f"  -> {action.tool}: {str(observation)[:120]}...")
            print()

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
