# =============================================================================
# FFIA — app/main.py
# Streamlit Chat UI — W2: wired to LangChain ReAct agent (Gemini 1.5).
# Displays agent reasoning trace (Thought/Action/Observation) in st.expander.
# =============================================================================

# Step 1: Add project root to path so agent/ package can be imported
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 2: Streamlit and agent imports
import streamlit as st
from agent.main import run_agent

# Step 3: Configure the page
st.set_page_config(
    page_title="FFIA — Restaurant Cost Optimizer",
    page_icon="🍜",
    layout="wide",
)

# Step 4: Header
st.title("🍜 FFIA — Fuel & Food Impact Analyzer")
st.caption("MADT 7204 Vibe Coding Project | Team 2 | Bangkok Oil Price Crisis")
st.divider()

# Step 5: Build stage banner — W2
st.info(
    "**W2 — ReAct Agent Live.** Gemini 1.5 + BigQuery + Web Search connected. "
    "Expand the 'Agent Reasoning Trace' to see Thought → Action → Observation steps.",
    icon="🤖",
)

# Step 6: Placeholder metrics — will show real data from W3+
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Oil Price Today", value="— baht/L", delta="Ask the agent")
with col2:
    st.metric(label="Menu Items Tracked", value="—", delta="Query via BigQuery")
with col3:
    st.metric(label="Avg Gross Margin", value="— %", delta="W3 tools")

st.divider()

# Step 7: Initialize chat history in Streamlit session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Step 8: Render existing chat messages from this session
st.subheader("Ask the FFIA Agent")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Step 9: Chat input
user_input = st.chat_input(
    "e.g. 'What is the current diesel price in Bangkok?' or "
    "'Show me our top 5 highest-cost menu items'"
)

if user_input:
    # Step 9a: Render the user's message immediately
    with st.chat_message("user"):
        st.markdown(user_input)

    # Step 9b: Build history for multi-turn context (role + content only)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]

    # Step 9c: Run the ReAct agent and render clean structured trace
    with st.chat_message("assistant"):

        # Step 9c-i: Run agent with spinner
        with st.spinner("FFIA is thinking..."):
            result = run_agent(user_input, history)

        # Step 9c-ii: Render structured ReAct trace inside expander
        # intermediate_steps is a list of (tool_name: str, observation: str) tuples
        steps = result.get("intermediate_steps", [])
        if steps:
            with st.expander("Agent Reasoning Trace", expanded=True):
                step_num = 1
                for tool_name, observation in steps:
                    st.markdown(f"**Step {step_num} — Action:** `{tool_name}`")
                    if observation:
                        st.markdown(f"**Observation:** {str(observation)[:500]}")
                    st.divider()
                    step_num += 1
                reply = result.get("output", "Sorry, I could not produce an answer.")
                st.markdown(f"**Final Answer:** {reply}")
        else:
            # Step 9c-iii: No tool calls — just show the direct answer
            reply = result.get("output", "Sorry, I could not produce an answer.")

        # Step 9c-iv: Always render the final answer cleanly below the expander
        st.markdown(reply)

    # Step 9d: Save both turns to session history
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.messages.append({"role": "assistant", "content": reply})

# Step 10: Footer
st.divider()
st.caption("Built with Claude Code · LangChain · Gemini 1.5 · Streamlit | Security: API keys in .env only")
