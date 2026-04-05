# =============================================================================
# FFIA — app/main.py
# Streamlit Chat UI — W2: wired to LangChain ReAct agent (Gemini 1.5).
# Displays agent reasoning trace (Thought/Action/Observation) in st.expander.
# =============================================================================

# Step 1: Add project root to path so agent/ package can be imported
import sys
import base64
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

# Step 3a: CSS — dark sidebar, metric cards
st.markdown("""
<style>
/* ── Sidebar shell ── */
section[data-testid="stSidebar"] {
    min-width: 240px; max-width: 240px;
    background: #0f172a !important;
}
section[data-testid="stSidebar"] > div:first-child {
    background: #0f172a !important;
}
[data-testid="stSidebarContent"] {
    background: #0f172a !important;
    padding: 1.25rem 0.75rem 1rem 0.75rem !important;
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 0;
}
/* Kill default Streamlit element spacing inside sidebar */
section[data-testid="stSidebar"] .stMarkdown {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
/* ── Metric cards (main area) ── */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
/* ── Sidebar nav items ── */
.sb-nav-active {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 12px; border-radius: 8px;
    background: #1e293b;
    cursor: default; margin-bottom: 2px;
}
.sb-nav-active .sb-label {
    font-size: 0.95rem; font-weight: 600; color: #f1f5f9; letter-spacing: 0.01em;
}
.sb-nav-inactive {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 12px; border-radius: 8px;
    cursor: default; margin-bottom: 2px;
}
.sb-nav-inactive .sb-label {
    font-size: 0.95rem; font-weight: 500; color: #64748b; letter-spacing: 0.01em;
}
/* ── Bottom account block ── */
.sb-account {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 12px 4px 12px;
    border-top: 1px solid #1e293b;
    margin-top: auto;
}
.sb-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    background: #1e293b; border: 1.5px solid #334155;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.sb-acc-name { font-size: 0.9rem; font-weight: 600; color: #e2e8f0; line-height: 1.3; }
.sb-acc-role { font-size: 0.78rem; color: #475569; line-height: 1.2; }
/* ── Chat input disclaimer — injected below the pinned input bar ── */
[data-testid="stBottom"] {
    padding-bottom: 0.5rem !important;
}
[data-testid="stBottom"]::after {
    content: "FFIA can make mistakes. Always validate critical insights with domain experts before making decisions.";
    display: block;
    font-size: 0.7rem;
    color: #94a3b8;
    text-align: center;
    padding: 4px 1rem 0 1rem;
    line-height: 1.4;
}
</style>
""", unsafe_allow_html=True)

# Step 4: Sidebar — dark navy: brand block + nav + bottom account
with st.sidebar:
    # Step 4a: Load logo as base64; fall back to "F" badge on dark bg if missing
    _logo_path = Path(__file__).parent / "assets" / "ffia_logo_design.png"
    if _logo_path.exists():
        with open(_logo_path, "rb") as _fh:
            _b64 = base64.b64encode(_fh.read()).decode()
        _icon_html = (
            f'<img src="data:image/png;base64,{_b64}" '
            f'style="width:100%;height:100%;object-fit:cover;border-radius:8px;">'
        )
    else:
        _icon_html = (
            '<div style="width:100%;height:100%;display:flex;align-items:center;'
            'justify-content:center;background:#1e3a5f;border-radius:8px;'
            'font-size:1.3rem;font-weight:700;color:#93c5fd;">F</div>'
        )

    # Step 4b: Brand block
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:0 4px 20px 4px;">
    <div style="width:40px;height:40px;border-radius:8px;overflow:hidden;flex-shrink:0;background:#1e293b;">
        {_icon_html}
    </div>
    <div style="display:flex;flex-direction:column;justify-content:center;gap:2px;">
        <span style="font-weight:700;color:#f1f5f9;font-size:1.15rem;line-height:1.2;">FFIA</span>
        <span style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:0.12em;line-height:1.2;">Impact Analyzer</span>
    </div>
</div>
""", unsafe_allow_html=True)

    # Step 4c: Nav items — inline SVG icons, no emoji
    # Dashboard (active) — bar-chart icon
    # Data Upload (inactive) — upload/document icon
    st.markdown("""
<div class="sb-nav-active">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
        <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
    <span class="sb-label">Dashboard</span>
</div>
<div class="sb-nav-inactive">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="12" y1="18" x2="12" y2="12"/>
        <polyline points="9 15 12 12 15 15"/>
    </svg>
    <span class="sb-label">Data Upload</span>
</div>
""", unsafe_allow_html=True)

    # Step 4d: Bottom account block — margin-top:auto pins to sidebar bottom
    st.markdown("""
<div class="sb-account">
    <div class="sb-avatar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
        </svg>
    </div>
    <div>
        <div class="sb-acc-name">Admin</div>
        <div class="sb-acc-role">Powered by FFIA Solutions</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Step 5: Header — title and caption only (profile moved to sidebar bottom)
st.title("FFIA — Fuel & Food Impact Analyzer")
st.caption(
    "AI-powered cost optimization for restaurants. Analyze fuel-driven cost impact "
    "and improve your menu profitability."
)
st.divider()

# Step 6: Build stage banner — W2
st.info(
    "**FFIA Agent is ready.** Analyze cost impact, identify margin risk, and get "
    "actionable recommendations for smarter menu decisions.",
    icon="✨",
)

# Step 7: Placeholder metrics — will show real data from W3+
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Oil Price Today", value="— baht/L", delta="Ask the agent")
with col2:
    st.metric(label="Menu Items Tracked", value="—", delta="Query via BigQuery")
with col3:
    st.metric(label="Avg Gross Margin", value="— %", delta="W3 tools")

st.divider()

# Step 8: Initialize chat history in Streamlit session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Step 9: Render existing chat messages from this session
st.subheader("What would you like to analyze today?")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Step 9a: Chat input
user_input = st.chat_input(
    "e.g. 'What is the current diesel price in Bangkok?' or "
    "'Show me our top 5 highest-cost menu items'"
)

if user_input:
    # Step 9b: Render the user's message immediately
    with st.chat_message("user"):
        st.markdown(user_input)

    # Step 9c: Build history for multi-turn context (role + content only)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]

    # Step 9d: Run the ReAct agent and render clean structured trace
    with st.chat_message("assistant"):

        # Step 9d-i: Run agent with spinner
        with st.spinner("FFIA is thinking..."):
            result = run_agent(user_input, history)

        # Step 9d-ii: Render structured ReAct trace inside expander
        # intermediate_steps is a list of (tool_name: str, observation: str) tuples
        steps = result.get("intermediate_steps", [])
        if steps:
            with st.expander("Agent Reasoning Trace (click to expand)", expanded=False):
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
            # Step 9d-iii: No tool calls — just show the direct answer
            reply = result.get("output", "Sorry, I could not produce an answer.")

        # Step 9d-iv: Always render the final answer cleanly below the expander
        st.markdown(reply)

    # Step 9e: Save both turns to session history
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.messages.append({"role": "assistant", "content": reply})

