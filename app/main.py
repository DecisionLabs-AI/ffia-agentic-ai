# =============================================================================
# FFIA — app/main.py
# Streamlit Chat UI — wired to LangChain ReAct agent (Gemini 2.5 Flash).
# Data Upload page persists invoices to PostgreSQL via data/db.py.
# =============================================================================

# Step 1: Add project root to path so agent/ package can be imported
import sys
import base64
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 2: Streamlit and lightweight imports only — heavy AI/DB resources are lazy-loaded
import pandas as pd
import streamlit as st
from app.utils.auth import authenticate_user, load_auth_users
from app.utils.upload_cache import build_uploaded_file_cache_key
from data.db import create_tables, invoice_exists, save_invoice, get_recent_invoices


def _safe_invoice_date(value: object) -> date:
    """Return a valid date for the form even if OCR left the field blank."""
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return date.today()


def _build_items_df(items: object) -> pd.DataFrame:
    """Keep the line-item editor usable even when OCR returns no rows."""
    return pd.DataFrame(items or [], columns=["name", "qty", "unit_price", "total"])


def _clear_user_session() -> None:
    """Clear per-user session state on logout."""
    for key in list(st.session_state.keys()):
        if key == "page":
            continue
        del st.session_state[key]


def _require_authenticated_user() -> dict:
    """Render a login form and stop the app until the user is authenticated."""
    try:
        load_auth_users()
    except Exception as exc:
        st.error(
            "Authentication is not configured correctly. "
            f"Update FFIA_AUTH_USERS_JSON before using the app.\n\nDetails: {exc}"
        )
        st.stop()

    current_user = st.session_state.get("auth_user")
    if current_user:
        return current_user

    st.markdown(
        "<h2 style='text-align:center;margin-bottom:0.25rem;'>FFIA Sign In</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#64748b;margin-bottom:1.75rem;font-size:0.92rem;'>"
        "Sign in to access only your invoices and analysis history.</p>",
        unsafe_allow_html=True,
    )

    # Step 0: Center the form in a narrow middle column (~480px).
    # st.container(border=True) scopes the card styling to this block only —
    # avoids global CSS that would pollute forms elsewhere in the app.
    _left, _mid, _right = st.columns([1, 2, 1])
    with _mid:
        with st.container(border=True):
            with st.form("ffia_login_form", clear_on_submit=False):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

    if submitted:
        authenticated_user = authenticate_user(username, password)
        if authenticated_user:
            st.session_state["auth_user"] = authenticated_user
            st.session_state["page"] = "dashboard"
            st.rerun()
        with _mid:
            st.error("Invalid username or password.")

    st.stop()

# Step 4: Configure the page — must be the first st.* command
st.set_page_config(
    page_title="FFIA — Restaurant Cost Optimizer",
    page_icon="📈",
    layout="wide",
)

# Step 4a: Lazy loader for the ReAct agent — cached for the process lifetime.
# Defined after set_page_config() per Streamlit's required initialization order.
# Deferred import prevents ChatGoogleGenerativeAI + LangGraph from running at startup.
@st.cache_resource(show_spinner=False)
def _get_run_agent():
    from agent.main import run_agent  # noqa: PLC0415
    return run_agent


# Step 4b: Lazy loader for OCR extraction — cached for the process lifetime.
# Deferred import prevents the Gemini Vision LLM from being instantiated at startup.
@st.cache_resource(show_spinner=False)
def _get_extract_invoice_data():
    from app.utils.ocr import extract_invoice_data  # noqa: PLC0415
    return extract_invoice_data

_current_user = _require_authenticated_user()

# Step 3: Ensure PostgreSQL tables exist — run once per session, not on every rerun
if not st.session_state.get("_tables_created"):
    try:
        create_tables()
        st.session_state["_tables_created"] = True
    except Exception as _db_err:
        st.error(f"Database connection failed: {_db_err}")
        st.stop()

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
/* ── Sidebar nav buttons — base style (inactive) ── */
section[data-testid="stSidebar"] .stButton > button {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 9px 12px !important;
    border-radius: 8px !important;
    border: none !important;
    background: transparent !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: #64748b !important;
    letter-spacing: 0.01em !important;
    cursor: pointer !important;
    box-shadow: none !important;
    margin-bottom: 2px !important;
    justify-content: flex-start !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #1e293b !important;
    color: #cbd5e1 !important;
    border: none !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .stButton > button:focus,
section[data-testid="stSidebar"] .stButton > button:active {
    box-shadow: none !important;
    border: none !important;
    outline: none !important;
}
/* Active nav item — key contains "_active" suffix */
section[data-testid="stSidebar"] [data-testid*="_active"] > button {
    background: #1e293b !important;
    color: #f1f5f9 !important;
    font-weight: 600 !important;
}
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

# Step 5: Sidebar — dark navy: brand block + nav + bottom account
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

    # Step 4c: Nav items — pure st.button, styled via CSS by key suffix (_active/_inactive)
    # Active key triggers the highlighted CSS rule; no HTML div overlay needed.
    _page = st.session_state.get("page", "dashboard")

    _dash_key  = "nav_dashboard_active"  if _page == "dashboard" else "nav_dashboard_inactive"
    _upload_key = "nav_upload_active"    if _page == "upload"    else "nav_upload_inactive"

    if st.button("  Dashboard",  key=_dash_key,  use_container_width=True):
        st.session_state["page"] = "dashboard"
        st.rerun()
    if st.button("  Data Upload", key=_upload_key, use_container_width=True):
        st.session_state["page"] = "upload"
        st.rerun()
    if st.button("Logout", key="nav_logout", use_container_width=True):
        _clear_user_session()
        st.rerun()

    # Step 4d: Bottom account block — margin-top:auto pins to sidebar bottom
    st.markdown(f"""
<div class="sb-account">
    <div class="sb-avatar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
        </svg>
    </div>
    <div>
        <div class="sb-acc-name">{_current_user["display_name"]}</div>
        <div class="sb-acc-role">@{_current_user["username"]}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Step 6: Data Upload page renderer — OCR → editable form → FFIA analysis
def _render_upload_page(current_user: dict):
    """Render the Data Upload page: upload image → preview → extract → edit → analyze."""
    st.title("Data Upload — Invoice Image OCR")
    st.caption(
        "Upload a fuel or supplier invoice image to extract cost data, "
        "review it, and run FFIA analysis."
    )
    st.divider()

    # Step 5a: Upload
    st.subheader("Step 1: Upload Invoice Image")
    st.caption("Supported formats: JPG, JPEG, PNG")
    uploaded = st.file_uploader(
        "Choose invoice image",
        type=["png", "jpg", "jpeg"],
        label_visibility="collapsed",
    )

    if not uploaded:
        st.info("Upload an invoice image above to begin.")
        return

    # Step 5b: Preview
    st.subheader("Step 2: Preview")
    st.image(uploaded, width=480)

    # Step 5c: Extract — run once per file, cache in session state
    st.subheader("Step 3: Review & Edit Extracted Data")
    st.caption("Please review and adjust extracted data before analysis.")

    _cache_key = build_uploaded_file_cache_key(uploaded)
    if _cache_key not in st.session_state:
        with st.spinner("Extracting data from image..."):
            st.session_state[_cache_key] = _get_extract_invoice_data()(uploaded)
    data = st.session_state[_cache_key]
    _ocr_error = data.get("_ocr_error", "")
    _raw_ocr = data.get("_ocr_raw_response", "")
    _cleaned_ocr = data.get("_ocr_cleaned_response", "")

    if _ocr_error:
        st.warning(
            "OCR output could not be parsed cleanly. You can still review and edit the "
            "invoice below, and the raw OCR response is shown for debugging."
        )

    with st.expander("OCR Debug Output", expanded=bool(_ocr_error)):
        if _ocr_error:
            st.caption(_ocr_error)
        st.text_area("Raw OCR response", value=_raw_ocr, height=180, disabled=True)
        st.text_area(
            "Cleaned response before JSON parse",
            value=_cleaned_ocr,
            height=180,
            disabled=True,
        )

    # Step 5d: Header fields — two columns
    _col_a, _col_b = st.columns(2)
    with _col_a:
        vendor  = st.text_input("Vendor",     value=data["vendor"])
        inv_no  = st.text_input("Invoice No", value=data["invoice_no"])
    with _col_b:
        inv_date = st.date_input(
            "Invoice Date",
            value=_safe_invoice_date(data.get("invoice_date")),
        )
        total = st.number_input(
            "Total Amount (฿)",
            value=float(data["total_amount"]),
            step=0.01,
            format="%.2f",
        )

    # Step 5e: Line items — editable table
    st.markdown("**Line Items**")
    items_df = _build_items_df(data.get("items"))
    edited_df = st.data_editor(
        items_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name":       st.column_config.TextColumn("Item Name"),
            "qty":        st.column_config.NumberColumn("Qty", step=1),
            "unit_price": st.column_config.NumberColumn("Unit Price (฿)", format="%.2f"),
            "total":      st.column_config.NumberColumn("Total (฿)", format="%.2f"),
        },
    )

    st.divider()

    # Step 5f: Save to database button
    st.subheader("Step 4: Save Invoice")
    _col_save, _ = st.columns([1, 3])
    with _col_save:
        if st.button("Save Invoice to Database", type="primary", use_container_width=True):
            try:
                _invoice_no = str(inv_no).strip()
                if invoice_exists(current_user["user_id"], _invoice_no):
                    st.warning("⚠️ This invoice already exists")
                else:
                    _inv_id = save_invoice(
                        user_id=current_user["user_id"],
                        vendor=vendor,
                        invoice_no=_invoice_no,
                        invoice_date=inv_date,
                        total_amount=total,
                        items=edited_df.to_dict(orient="records"),
                    )
                    st.success(f"Invoice **{_invoice_no}** saved (ID: {_inv_id})")
            except Exception as _e:
                st.error(f"Failed to save: {_e}")

    # Step 5g: Recent saved invoices
    with st.expander("Recent Saved Invoices", expanded=False):
        try:
            _recent = get_recent_invoices(current_user["user_id"])
            if _recent:
                st.dataframe(pd.DataFrame(_recent), use_container_width=True)
            else:
                st.caption("No invoices saved yet.")
        except Exception as _e:
            st.error(f"Could not load invoices: {_e}")

    st.divider()

    # Step 5h: Analyze button
    st.subheader("Step 5: Analyze with FFIA")
    _has_data = len(edited_df) > 0
    if st.button("Analyze with FFIA", disabled=not _has_data):
        _prompt = (
            "Analyze this invoice for fuel-related cost impact and provide cost optimization "
            "recommendations for a restaurant.\n\n"
            f"Vendor: {vendor}\n"
            f"Invoice No: {inv_no}\n"
            f"Date: {inv_date}\n"
            f"Total: ฿{total:,.2f}\n\n"
            f"Line items:\n{edited_df.to_string(index=False)}"
        )
        with st.spinner("FFIA is analyzing..."):
            _result = _get_run_agent()(_prompt, current_user_id=current_user["user_id"])

        # Step 5i: FFIA Insight
        st.subheader("FFIA Insight")
        st.markdown(_result.get("output", "No response from agent."))

        _steps = _result.get("intermediate_steps", [])
        if _steps:
            with st.expander("Agent Reasoning Trace (click to expand)", expanded=False):
                for _i, (_tool_name, _obs) in enumerate(_steps, 1):
                    st.markdown(f"**Step {_i} — Action:** `{_tool_name}`")
                    if _obs:
                        st.markdown(f"**Observation:** {str(_obs)[:500]}")
                    st.divider()


# Step 7: Dashboard page renderer — all existing chat + metrics logic
def _render_dashboard_page(current_user: dict):
    """Render the main Dashboard page: header, metrics, chat agent."""
    # Step 6a: Header
    st.title("FFIA — Fuel & Food Impact Analyzer")
    st.caption(
        "AI-powered cost optimization for restaurants. Analyze fuel-driven cost impact "
        "and improve your menu profitability."
    )
    st.divider()

    # Step 6b: Build stage banner
    st.info(
        "**FFIA Agent is ready.** Analyze cost impact, identify margin risk, and get "
        "actionable recommendations for smarter menu decisions.",
        icon="✨",
    )

    # Step 6c: Placeholder metrics — will show real data from W3+
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Oil Price Today", value="— baht/L", delta="Ask the agent")
    with col2:
        st.metric(label="Menu Items Tracked", value="—", delta="Query via PostgreSQL")
    with col3:
        st.metric(label="Avg Gross Margin", value="— %", delta="W3 tools")

    st.divider()

    # Step 6d: Initialize chat history in Streamlit session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Step 6e: Render chat messages inside a scrollable container
    # This keeps messages bounded so the page doesn't scroll — input stays at bottom.
    st.subheader("What would you like to analyze today?")
    _msg_container = st.container(height=480, border=False)
    with _msg_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Step 6f: Chat input — already rendered in Streamlit's fixed stBottom container
    user_input = st.chat_input(
        "e.g. 'What is the current diesel price in Bangkok?' or "
        "'Show me our top 5 highest-cost menu items'"
    )

    if user_input:
        # Step 6f-i: Append user message and rerender inside the scroll container
        st.session_state.messages.append({"role": "user", "content": user_input})

        with _msg_container:
            with st.chat_message("user"):
                st.markdown(user_input)

            # Step 6f-ii: Build history for multi-turn context (role + content only)
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1]
            ]

            # Step 6f-iii: Run the ReAct agent and render inside scroll container
            with st.chat_message("assistant"):
                with st.spinner("FFIA is thinking..."):
                    result = _get_run_agent()(user_input, history, current_user_id=current_user["user_id"])

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
                    reply = result.get("output", "Sorry, I could not produce an answer.")

                # Always render the final answer cleanly below the expander
                st.markdown(reply)

        # Step 6f-iv: Save assistant turn to session history
        st.session_state.messages.append({"role": "assistant", "content": reply})


# Step 8: Page router — dispatch to correct page based on session state
if st.session_state.get("page", "dashboard") == "upload":
    _render_upload_page(_current_user)
else:
    _render_dashboard_page(_current_user)
