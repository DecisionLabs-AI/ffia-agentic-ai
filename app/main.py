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
from html import escape
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 2: Streamlit and lightweight imports only — heavy AI/DB resources are lazy-loaded
import pandas as pd
import streamlit as st
from app.utils.auth import authenticate_user, load_auth_users
from app.utils.upload_cache import build_uploaded_file_cache_key
from data.db import (
    create_tables,
    invoice_exists,
    save_invoice,
    get_recent_invoices,
    fetch_invoices_current_month,
    fetch_invoice_items,
    fetch_latest_restaurant_profile,
    upsert_restaurant_profile,
    count_invoice_items,
)


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
    _preserve_keys = {"_tables_created"}
    for key in list(st.session_state.keys()):
        if key in _preserve_keys:
            continue
        del st.session_state[key]
    st.session_state["page"] = "dashboard"


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

    # Step 0: Center hero + form in one balanced composition.
    _left, _mid, _right = st.columns([1.1, 2.8, 1.1])
    with _mid:
        _render_page_hero(
            "FFIA Sign In",
            "Sign in to access only your invoices and analysis history.",
            eyebrow="Secure Access",
            extra_class="page-hero--compact page-hero--login",
        )
        with st.container(border=True):
            with st.form("ffia_login_form", clear_on_submit=False):
                username = st.text_input("Username", value="admin")
                password = st.text_input("Password", type="password", value="admin@madt2026")
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


def _render_page_hero(
    title: str,
    subtitle: str,
    eyebrow: str | None = None,
    extra_class: str = "",
) -> None:
    """Render a premium page hero without affecting page logic."""
    _eyebrow_html = (
        f'<span class="page-hero__eyebrow">{escape(eyebrow)}</span>'
        if eyebrow else ""
    )
    _class_attr = f"page-hero {extra_class}".strip()
    st.markdown(
        f"""
<div class="{_class_attr}">
  {_eyebrow_html}
  <h1>{escape(title)}</h1>
  <p>{escape(subtitle)}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_section_header(title: str, subtitle: str | None = None) -> None:
    """Render a softer section heading used across pages."""
    _subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f"""
<div class="section-heading">
  <h2>{escape(title)}</h2>
  {_subtitle_html}
</div>
""",
        unsafe_allow_html=True,
    )

# Step 3a: CSS — soft premium dashboard theme
st.markdown("""
<style>
:root {
    --ffia-bg: #f4f7fb;
    --ffia-bg-soft: #eef4fb;
    --ffia-surface: rgba(255, 255, 255, 0.9);
    --ffia-surface-strong: #ffffff;
    --ffia-surface-tint: #f7fbff;
    --ffia-sidebar: #eaf1f8;
    --ffia-sidebar-strong: #dfe8f3;
    --ffia-border: #d8e3ef;
    --ffia-border-strong: #c7d7e8;
    --ffia-text: #18354d;
    --ffia-text-muted: #6d8498;
    --ffia-text-soft: #91a3b5;
    --ffia-accent: #77aaf8;
    --ffia-accent-strong: #4f8fef;
    --ffia-accent-soft: #eaf4ff;
    --ffia-green: #5aaf84;
    --ffia-amber: #d7a05a;
    --ffia-red: #d77777;
    --ffia-shadow: 0 24px 48px -34px rgba(70, 101, 135, 0.38);
    --ffia-shadow-soft: 0 16px 34px -28px rgba(77, 106, 138, 0.28);
    --ffia-radius-lg: 24px;
    --ffia-radius-md: 18px;
    --ffia-radius-sm: 14px;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at top right, rgba(133, 179, 245, 0.18), transparent 26%),
        radial-gradient(circle at top left, rgba(192, 221, 255, 0.14), transparent 22%),
        linear-gradient(180deg, #f9fbff 0%, #f3f7fc 58%, #f5f8fd 100%) !important;
}

[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background: transparent !important;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 2rem !important;
    padding-bottom: 7rem !important;
    max-width: 1360px !important;
}

html, body, [class*="css"] {
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--ffia-text);
    letter-spacing: -0.02em;
}

p, li, label, .stCaption, .stMarkdown, .stText, .st-emotion-cache-10trblm {
    color: var(--ffia-text-muted);
}

[data-testid="stMarkdownContainer"] p {
    color: var(--ffia-text-muted);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: inherit;
}

[data-testid="stHeadingWithActionElements"] h1,
[data-testid="stHeadingWithActionElements"] h2,
[data-testid="stHeadingWithActionElements"] h3 {
    color: var(--ffia-text);
}

[data-testid="stDivider"] {
    margin: 1.4rem 0 !important;
}

[data-testid="stDivider"] hr {
    border-color: rgba(199, 215, 232, 0.72) !important;
}

/* ── Reusable page hero ── */
.page-hero {
    position: relative;
    overflow: hidden;
    padding: 1.6rem 1.75rem 1.7rem 1.75rem;
    border-radius: 28px;
    border: 1px solid rgba(205, 221, 238, 0.9);
    background:
        linear-gradient(140deg, rgba(255,255,255,0.94) 0%, rgba(244,249,255,0.92) 65%, rgba(237,246,255,0.95) 100%);
    box-shadow: var(--ffia-shadow);
    margin-bottom: 1.05rem;
}

.page-hero::after {
    content: "";
    position: absolute;
    top: -56px;
    right: -32px;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(125, 174, 244, 0.18) 0%, rgba(125, 174, 244, 0.02) 70%);
    pointer-events: none;
}

.page-hero__eyebrow {
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.8rem;
    margin-bottom: 0.9rem;
    border-radius: 999px;
    background: rgba(234, 244, 255, 0.96);
    border: 1px solid rgba(177, 203, 233, 0.65);
    color: #5e7ea3;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.page-hero h1 {
    margin: 0;
    font-size: 2.15rem;
    line-height: 1.08;
    font-weight: 750;
    color: var(--ffia-text);
}

.page-hero p {
    margin: 0.7rem 0 0;
    max-width: 760px;
    color: var(--ffia-text-muted);
    font-size: 1rem;
    line-height: 1.62;
}

.page-hero--compact {
    padding: 1.18rem 1.35rem 1.22rem 1.35rem;
    border-radius: 24px;
    margin-bottom: 0.75rem;
}

.page-hero--compact::after {
    top: -72px;
    right: -42px;
    width: 148px;
    height: 148px;
    opacity: 0.88;
}

.page-hero--login {
    box-shadow: 0 18px 34px -30px rgba(70, 101, 135, 0.34);
}

.page-hero--login h1 {
    font-size: 1.82rem;
    line-height: 1.08;
}

.page-hero--login p {
    max-width: 560px;
    margin-top: 0.55rem;
    font-size: 0.96rem;
    line-height: 1.56;
}

.page-hero--login .page-hero__eyebrow {
    margin-bottom: 0.7rem;
    padding: 0.32rem 0.72rem;
    font-size: 0.69rem;
}

.section-heading {
    margin-bottom: 0.95rem;
}

.section-heading h2 {
    margin: 0;
    color: var(--ffia-text);
    font-size: 1.1rem;
    line-height: 1.2;
    font-weight: 700;
    letter-spacing: -0.01em;
}

.section-heading p {
    margin: 0.35rem 0 0;
    color: var(--ffia-text-muted);
    font-size: 0.92rem;
    line-height: 1.55;
}

.step-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.42rem 0.86rem;
    border-radius: 999px;
    background: rgba(234, 244, 255, 0.96);
    border: 1px solid rgba(180, 204, 232, 0.7);
    color: #587598;
    font-size: 0.79rem;
    font-weight: 700;
    margin-bottom: 0.85rem;
}

/* ── Sidebar shell ── */
section[data-testid="stSidebar"] {
    min-width: 276px;
    max-width: 276px;
    background:
        linear-gradient(180deg, #edf3fa 0%, #e8eff8 100%) !important;
    border-right: 1px solid rgba(201, 215, 231, 0.86);
}
section[data-testid="stSidebar"] > div:first-child {
    background: transparent !important;
}
[data-testid="stSidebarContent"] {
    background: transparent !important;
    padding: 1.25rem 0.8rem 1rem 0.8rem !important;
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 0.05rem;
}

section[data-testid="stSidebar"] .stMarkdown {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

.sb-brand {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding: 0.15rem 0.2rem 1rem 0.2rem;
    margin-bottom: 0.3rem;
    border-bottom: 1px solid rgba(197, 213, 229, 0.88);
}

.sb-brand-logo {
    width: 42px;
    height: 42px;
    border-radius: 14px;
    overflow: hidden;
    flex-shrink: 0;
    background: rgba(255,255,255,0.8);
    border: 1px solid rgba(194, 209, 225, 0.92);
    box-shadow: 0 12px 22px -20px rgba(70, 101, 135, 0.5);
}

.sb-brand-copy {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
}

.sb-brand-name {
    font-size: 1.02rem;
    font-weight: 750;
    line-height: 1.1;
    letter-spacing: -0.02em;
    color: var(--ffia-text);
}

.sb-brand-subtitle {
    font-size: 0.67rem;
    line-height: 1.2;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    color: #7a91a8;
}

.sb-brand-fallback {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(180deg, #eff6ff 0%, #dfeeff 100%);
    color: #5f94ed;
    font-size: 1.15rem;
    font-weight: 800;
}

.sb-nav-item {
    margin-bottom: 0.14rem;
}

.sb-account {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.9rem 0.8rem 0.15rem 0.8rem;
    border-top: 1px solid rgba(197, 213, 229, 0.9);
    margin-top: auto;
}

.sb-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(180deg, #ffffff 0%, #f1f6fc 100%);
    border: 1px solid rgba(191, 207, 224, 0.95);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 12px 24px -24px rgba(70, 101, 135, 0.52);
}

.sb-avatar span {
    font-size: 0.74rem;
    font-weight: 700;
    color: #58708b;
    letter-spacing: 0.03em;
}

.sb-acc-name {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--ffia-text);
    line-height: 1.25;
}

.sb-acc-role {
    font-size: 0.74rem;
    color: #7b8fa5;
    line-height: 1.2;
}

/* ── Sidebar nav buttons ── */
section[data-testid="stSidebar"] .stButton > button {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    width: 100% !important;
    min-height: 42px !important;
    padding: 0.65rem 0.9rem !important;
    border-radius: 16px !important;
    border: 1px solid transparent !important;
    background: transparent !important;
    font-size: 0.89rem !important;
    font-weight: 600 !important;
    color: #658099 !important;
    letter-spacing: 0.01em !important;
    cursor: pointer !important;
    box-shadow: none !important;
    margin-bottom: 0.14rem !important;
    text-align: left !important;
    transition: background 0.18s, border-color 0.18s, color 0.18s, transform 0.18s, box-shadow 0.18s !important;
}

section[data-testid="stSidebar"] .stButton > button p {
    text-align: left !important;
    margin: 0 !important;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.7) !important;
    color: var(--ffia-text) !important;
    border-color: rgba(200, 215, 231, 0.82) !important;
    transform: translateY(-1px);
    box-shadow: var(--ffia-shadow-soft) !important;
}

section[data-testid="stSidebar"] .stButton > button:focus,
section[data-testid="stSidebar"] .stButton > button:active {
    box-shadow: 0 0 0 3px rgba(119, 170, 248, 0.16) !important;
    border-color: rgba(168, 194, 223, 0.96) !important;
    outline: none !important;
}

.sb-nav-item.active > div > button {
    background: linear-gradient(180deg, #ffffff 0%, #f5faff 100%) !important;
    color: #2f6cb9 !important;
    font-weight: 700 !important;
    border-color: rgba(177, 201, 230, 0.95) !important;
    box-shadow:
        inset 4px 0 0 rgba(116, 170, 248, 0.86),
        0 14px 28px -28px rgba(72, 112, 150, 0.42) !important;
}

/* ── Sidebar section labels ── */
.sb-section-label {
    font-size: 0.62rem;
    font-weight: 700;
    color: #7d93a8;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 0.82rem 0.85rem 0.34rem 0.85rem;
    margin-top: 0.15rem;
    border-top: 1px solid rgba(199, 214, 231, 0.86);
}

.sb-nav-disabled {
    display: flex;
    align-items: center;
    min-height: 38px;
    padding: 0.3rem 0.9rem;
    font-size: 0.84rem;
    font-weight: 500;
    color: #8ba0b2;
    margin-bottom: 0.08rem;
    line-height: 1.3;
    user-select: none;
    border-radius: 14px;
}

section[data-testid="stSidebar"] [data-testid*="nav_logout"] > button {
    color: #8499ac !important;
    font-size: 0.84rem !important;
    margin-top: 0.25rem !important;
}

section[data-testid="stSidebar"] [data-testid*="nav_logout"] > button:hover {
    color: #c56363 !important;
    background: rgba(255, 245, 245, 0.95) !important;
    border-color: rgba(232, 189, 189, 0.72) !important;
}

/* ── Surface cards / bordered containers ── */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stForm"] {
    border-radius: var(--ffia-radius-lg) !important;
    border: 1px solid rgba(208, 220, 234, 0.95) !important;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(249,252,255,0.92) 100%) !important;
    box-shadow: var(--ffia-shadow-soft) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    padding: 0.35rem 0.45rem !important;
}

[data-testid="stForm"] {
    padding: 0.2rem 0.2rem 0.05rem !important;
}

[data-testid="stFormSubmitButton"] {
    margin-top: 0.35rem !important;
}

/* ── Inputs / form controls ── */
div[data-baseweb="input"] > div,
div[data-baseweb="base-input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div,
[data-testid="stDateInput"] > div > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stTextInput"] > div > div {
    border-radius: 16px !important;
    border: 1px solid rgba(208, 220, 234, 0.96) !important;
    background: rgba(251, 253, 255, 0.96) !important;
    box-shadow: none !important;
}

div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea,
div[data-baseweb="select"] input {
    color: var(--ffia-text) !important;
}

div[data-baseweb="input"] > div:hover,
div[data-baseweb="base-input"] > div:hover,
div[data-baseweb="select"] > div:hover,
div[data-baseweb="textarea"] > div:hover {
    border-color: rgba(178, 201, 227, 0.96) !important;
}

div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="base-input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within {
    border-color: rgba(119, 170, 248, 0.98) !important;
    box-shadow: 0 0 0 4px rgba(119, 170, 248, 0.14) !important;
}

[data-testid="stFileUploaderDropzone"] {
    border-radius: 22px !important;
    border: 1.5px dashed rgba(184, 203, 226, 0.98) !important;
    background:
        linear-gradient(180deg, rgba(252,254,255,0.95) 0%, rgba(244,249,255,0.95) 100%) !important;
    padding: 1.4rem !important;
}

[data-testid="stFileUploaderDropzone"]:hover {
    border-color: rgba(119, 170, 248, 0.98) !important;
    background: rgba(241, 248, 255, 0.98) !important;
}

/* ── Buttons ── */
.stButton > button,
[data-testid="stFormSubmitButton"] > button {
    min-height: 44px !important;
    border-radius: 16px !important;
    border: 1px solid rgba(208, 220, 234, 0.96) !important;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(247,251,255,0.98) 100%) !important;
    color: var(--ffia-text) !important;
    font-weight: 650 !important;
    letter-spacing: -0.01em !important;
    box-shadow: none !important;
    transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s, background 0.18s, color 0.18s !important;
}

.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-1px);
    border-color: rgba(180, 202, 228, 0.98) !important;
    box-shadow: var(--ffia-shadow-soft) !important;
}

.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button[kind="primary"] {
    border-color: rgba(98, 150, 232, 0.98) !important;
    background:
        linear-gradient(180deg, #86b8ff 0%, #5d97ee 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 14px 26px -18px rgba(95, 154, 242, 0.46) !important;
}

.stButton > button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
    border-color: rgba(86, 139, 222, 0.98) !important;
    background:
        linear-gradient(180deg, #7cb1ff 0%, #528ce6 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 18px 30px -20px rgba(82, 140, 230, 0.52) !important;
}

/* ── Alerts / metrics / progress ── */
[data-testid="stAlert"] {
    border-radius: 18px !important;
    border: 1px solid rgba(208, 220, 234, 0.96) !important;
    background: rgba(251, 253, 255, 0.94) !important;
    box-shadow: none !important;
}

[data-testid="stMetric"] {
    background:
        linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,252,255,0.98) 100%);
    border: 1px solid rgba(213, 224, 236, 0.98);
    border-radius: 22px;
    padding: 1rem 1.2rem !important;
    box-shadow: var(--ffia-shadow-soft);
}

[data-testid="stMetricLabel"] {
    color: var(--ffia-text-muted) !important;
}

[data-testid="stMetricValue"] {
    color: var(--ffia-text) !important;
}

[data-testid="stProgressBar"] {
    height: 0.52rem !important;
    border-radius: 999px !important;
    background: rgba(226, 236, 246, 0.95) !important;
}

[data-testid="stProgressBar"] > div {
    background:
        linear-gradient(90deg, #8bb8ff 0%, #5e98ee 100%) !important;
    border-radius: 999px !important;
}

/* ── Tables / expanders / media ── */
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    border-radius: 20px !important;
    overflow: hidden !important;
    border: 1px solid rgba(213, 224, 236, 0.96) !important;
    box-shadow: var(--ffia-shadow-soft) !important;
    background: rgba(255, 255, 255, 0.94) !important;
}

[data-testid="stExpander"] {
    border-radius: 18px !important;
    border: 1px solid rgba(213, 224, 236, 0.92) !important;
    background: rgba(252, 254, 255, 0.9) !important;
    overflow: hidden !important;
}

[data-testid="stImage"] img {
    border-radius: 22px !important;
    border: 1px solid rgba(213, 224, 236, 0.96) !important;
    box-shadow: var(--ffia-shadow-soft) !important;
}

/* ── Chat workspace ── */
[data-testid="stChatMessage"] {
    border-radius: 20px !important;
    border: 1px solid rgba(213, 224, 236, 0.92) !important;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(248,251,255,0.92) 100%) !important;
    box-shadow: var(--ffia-shadow-soft) !important;
    padding: 0.35rem 0.45rem !important;
    margin-bottom: 0.8rem !important;
}

[data-testid="stBottom"] {
    background:
        linear-gradient(180deg, rgba(245,248,252,0) 0%, rgba(245,248,252,0.92) 26%, rgba(245,248,252,1) 100%) !important;
    padding: 0.85rem 0 0.65rem !important;
}

[data-testid="stChatInput"] {
    border-radius: 22px !important;
    border: 1px solid rgba(210, 222, 235, 0.96) !important;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(248,252,255,0.98) 100%) !important;
    box-shadow: var(--ffia-shadow) !important;
}

[data-testid="stChatInput"] textarea {
    color: var(--ffia-text) !important;
}

[data-testid="stBottom"]::after {
    content: "FFIA can make mistakes. Always validate critical insights with domain experts before making decisions.";
    display: block;
    font-size: 0.72rem;
    color: #8ca0b4;
    text-align: center;
    padding: 0.45rem 1rem 0 1rem;
    line-height: 1.45;
}

/* ── Status pills ── */
.status-pills-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.7rem;
    margin: 0 0 1.2rem 0;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.48rem 0.88rem;
    border-radius: 999px;
    font-size: 0.79rem;
    font-weight: 600;
    background: rgba(241, 251, 245, 0.98);
    color: #4d9a73;
    border: 1px solid rgba(186, 225, 204, 0.94);
}

.status-pill.warn {
    background: rgba(255, 248, 239, 0.98);
    color: #c28747;
    border-color: rgba(236, 208, 169, 0.94);
}

.status-pill.info {
    background: rgba(236, 245, 255, 0.98);
    color: #5a87c9;
    border-color: rgba(189, 210, 236, 0.94);
}

.status-pill.error {
    background: rgba(255, 244, 244, 0.98);
    color: #c16f6f;
    border-color: rgba(237, 197, 197, 0.94);
}

.pill-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
    flex-shrink: 0;
}

/* ── Decision cards ── */
.decision-card {
    --decision-accent: rgba(119, 170, 248, 0.92);
    position: relative;
    overflow: hidden;
    height: 100%;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,252,255,0.98) 100%);
    border: 1px solid rgba(213, 224, 236, 0.98);
    border-radius: 24px;
    padding: 1.22rem 1.3rem 1.12rem 1.3rem;
    box-shadow: var(--ffia-shadow-soft);
    height: 100%;
}

.decision-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--decision-accent) 0%, rgba(255,255,255,0) 85%);
}

.decision-card::after {
    content: "";
    position: absolute;
    top: -42px;
    right: -34px;
    width: 126px;
    height: 126px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(119, 170, 248, 0.14) 0%, rgba(119, 170, 248, 0) 72%);
    pointer-events: none;
}

.decision-card.warn  { --decision-accent: rgba(215, 160, 90, 0.95); }
.decision-card.risk  { --decision-accent: rgba(215, 119, 119, 0.95); }
.decision-card.ok    { --decision-accent: rgba(90, 175, 132, 0.95); }
.decision-card.muted { --decision-accent: rgba(184, 199, 214, 0.92); }

.dc-label {
    font-size: 0.72rem;
    color: #738aa0;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.62rem;
}

.dc-value {
    font-size: 1.92rem;
    font-weight: 760;
    color: var(--ffia-text);
    line-height: 1.05;
    letter-spacing: -0.03em;
}

.dc-sub {
    font-size: 0.82rem;
    color: var(--ffia-text-muted);
    margin-top: 0.42rem;
    line-height: 1.45;
}

.dc-hint {
    display: inline-flex;
    align-items: center;
    margin-top: 0.8rem;
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    background: rgba(255, 248, 239, 0.95);
    border: 1px solid rgba(236, 208, 169, 0.86);
    font-size: 0.76rem;
    color: #c28747;
    font-weight: 700;
}

.dc-hint.ok {
    background: rgba(241, 251, 245, 0.95);
    border-color: rgba(186, 225, 204, 0.86);
    color: #4f9c74;
}

.dc-hint.info {
    background: rgba(236, 245, 255, 0.95);
    border-color: rgba(189, 210, 236, 0.86);
    color: #5a87c9;
}

.dc-hint.muted {
    background: rgba(247, 250, 253, 0.96);
    border-color: rgba(212, 222, 233, 0.92);
    color: #8ea2b6;
}

/* ── Quick action buttons ── */
.action-card > div > button {
    height: 92px !important;
    border-radius: 20px !important;
    border: 1px solid rgba(213, 224, 236, 0.96) !important;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(246,250,255,0.98) 100%) !important;
    font-size: 0.9rem !important;
    font-weight: 650 !important;
    color: #1e293b !important;
    white-space: normal !important;
    line-height: 1.45 !important;
    box-shadow: none !important;
}

.action-card > div > button:hover {
    background: rgba(241, 248, 255, 0.98) !important;
    border-color: rgba(137, 182, 243, 0.98) !important;
    color: #346fb9 !important;
    box-shadow: var(--ffia-shadow-soft) !important;
}

/* ── Prompt chips ── */
.prompt-chip > div > button {
    border-radius: 999px !important;
    border: 1px solid rgba(209, 221, 235, 0.96) !important;
    background: rgba(248, 251, 255, 0.96) !important;
    font-size: 0.81rem !important;
    font-weight: 600 !important;
    color: #5f7790 !important;
    padding: 0.38rem 0.92rem !important;
    height: auto !important;
    min-height: 36px !important;
    box-shadow: none !important;
}

.prompt-chip > div > button:hover {
    background: rgba(235, 245, 255, 0.98) !important;
    border-color: rgba(137, 182, 243, 0.98) !important;
    color: #3f74bc !important;
}

@media (max-width: 992px) {
    .page-hero {
        padding: 1.3rem 1.2rem 1.35rem 1.2rem;
        border-radius: 24px;
    }

    .page-hero h1 {
        font-size: 1.8rem;
    }

    .page-hero--login h1 {
        font-size: 1.68rem;
    }
}

@media (max-width: 768px) {
    [data-testid="stMainBlockContainer"] {
        padding-top: 1.2rem !important;
    }

    .page-hero h1 {
        font-size: 1.55rem;
    }

    .page-hero--compact {
        padding: 1rem 1rem 1.05rem 1rem;
        margin-bottom: 0.65rem;
    }

    .page-hero--login h1 {
        font-size: 1.48rem;
    }

    .page-hero--login p {
        font-size: 0.93rem;
    }
}
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state["page"] = "dashboard"

_current_user = _require_authenticated_user()

# Step 4: Ensure PostgreSQL tables exist — run only after authentication.
if not st.session_state.get("_tables_created"):
    try:
        create_tables()
        st.session_state["_tables_created"] = True
    except Exception as _db_err:
        st.error(f"Database connection failed: {_db_err}")
        st.stop()

# Step 5: Sidebar — smart control panel with grouped nav, insight card, account block
def _render_sidebar_nav_button(
    label: str,
    key: str,
    is_active: bool = False,
) -> bool:
    """Render a sidebar nav button with a persistent active class."""
    _active_class = " active" if is_active else ""
    st.markdown(f'<div class="sb-nav-item{_active_class}">', unsafe_allow_html=True)
    _clicked = st.button(label, key=key, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    return _clicked


def _render_sidebar(current_user: dict) -> None:
    """Render the FFIA sidebar: brand, grouped nav sections, and account."""
    with st.sidebar:
        # Step 5a: Load logo (base64) — fall back to "F" badge if file missing
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
                '<div class="sb-brand-fallback">F</div>'
            )

        # Step 5b: Brand block — clean identity, minimal
        st.markdown(f"""
<div class="sb-brand">
    <div class="sb-brand-logo">
        {_icon_html}
    </div>
    <div class="sb-brand-copy">
        <span class="sb-brand-name">FFIA</span>
        <span class="sb-brand-subtitle">Fuel &amp; Food Impact Analyzer</span>
    </div>
</div>
""", unsafe_allow_html=True)

        _page = st.session_state["page"]

        # Step 5c: OVERVIEW — Dashboard
        st.markdown('<div class="sb-section-label">Overview</div>', unsafe_allow_html=True)

        if _render_sidebar_nav_button("Dashboard", key="nav_dashboard", is_active=_page == "dashboard"):
            st.session_state["page"] = "dashboard"
            st.rerun()

        # Step 5d: YOUR DATA — Upload live; Menu Cost + Invoices ghost (W4+)
        st.markdown('<div class="sb-section-label">Your Data</div>', unsafe_allow_html=True)

        if _render_sidebar_nav_button("Data Upload", key="nav_upload", is_active=_page == "upload"):
            st.session_state["page"] = "upload"
            st.rerun()

        st.markdown("""
<div class="sb-nav-disabled">Menu Cost Data</div>
<div class="sb-nav-disabled">Invoices</div>
""", unsafe_allow_html=True)

        # Step 5e: ANALYSIS — all ghost (W4+)
        st.markdown('<div class="sb-section-label">Analysis</div>', unsafe_allow_html=True)
        st.markdown("""
<div class="sb-nav-disabled">Margin Analysis</div>
<div class="sb-nav-disabled">Fuel Impact</div>
<div class="sb-nav-disabled">Scenario Simulation</div>
""", unsafe_allow_html=True)

        # Step 5f: SETTINGS — Business Profile live
        st.markdown('<div class="sb-section-label">Settings</div>', unsafe_allow_html=True)

        if _render_sidebar_nav_button(
            "Business Profile",
            key="nav_profile",
            is_active=_page == "profile_settings",
        ):
            st.session_state["page"] = "profile_settings"
            st.rerun()

        # Step 5g: Sign out — muted, sits above the account block
        if st.button("Sign out", key="nav_logout", use_container_width=True):
            _clear_user_session()
            st.rerun()

        # Step 5h: Account identity block — pinned to sidebar bottom via margin-top:auto CSS
        _initials = "".join(w[0].upper() for w in current_user["display_name"].split()[:2])
        st.markdown(f"""
<div class="sb-account">
    <div class="sb-avatar">
        <span>{_initials}</span>
    </div>
    <div>
        <div class="sb-acc-name">{current_user["display_name"]}</div>
        <div class="sb-acc-role">@{current_user["username"]}</div>
    </div>
</div>
""", unsafe_allow_html=True)


_render_sidebar(_current_user)

# Step 6: Monthly invoices section — always visible below the upload flow
def _render_monthly_invoices_section(current_user: dict) -> None:
    """Render the current-month invoice list and item detail view."""
    st.subheader("Uploaded Invoices (Current Month)")

    # Step 6a: Fetch this month's invoices for the authenticated user
    try:
        invoices = fetch_invoices_current_month(current_user["user_id"])
    except Exception as _e:
        st.error(f"Could not load invoices: {_e}")
        return

    if not invoices:
        st.info("No invoices uploaded this month.")
        return

    # Step 6b: Display invoice table (date, vendor, invoice_no, total_amount)
    _inv_df = pd.DataFrame(invoices)[["invoice_date", "vendor", "invoice_no", "total_amount"]]
    st.dataframe(_inv_df, use_container_width=True, hide_index=True)

    # Step 6c: Invoice selectbox — label combines invoice_no, vendor, date for clarity
    _options = {
        f"{r['invoice_no']} — {r['vendor']} ({r['invoice_date']})": r["id"]
        for r in invoices
    }
    _selected_label = st.selectbox("Select an invoice to view items", list(_options.keys()))
    _selected_id = _options[_selected_label]

    # Step 6d: Fetch and display line items for the selected invoice
    try:
        _items = fetch_invoice_items(_selected_id, current_user["user_id"])
    except Exception as _e:
        st.error(f"Could not load items: {_e}")
        return

    if not _items:
        st.caption("No line items found for this invoice.")
        return

    st.markdown(f"**Line Items — {_selected_label}**")
    st.dataframe(
        pd.DataFrame(_items)[["item_name", "qty", "unit_price", "total"]],
        use_container_width=True,
        hide_index=True,
    )


# Step 7: Data Upload page renderer — OCR → editable form → FFIA analysis
def _render_upload_page(current_user: dict):
    """Render the Data Upload page: upload image → preview → extract → edit → analyze."""
    _render_page_hero(
        "Data Upload — Invoice Image OCR",
        "Upload a fuel or supplier invoice image to extract cost data, "
        "review it, and run FFIA analysis.",
        eyebrow="Invoice Intelligence",
    )

    with st.container(border=True):
        _render_section_header(
            "Upload & Review",
            "Extract invoice details, validate the OCR output, then save or analyze the invoice.",
        )

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
        else:
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

    # Step 5j: Monthly invoice list — always visible, below the upload flow
    st.write("")
    with st.container(border=True):
        _render_monthly_invoices_section(current_user)


# Step 7b: Business Profile — stepper helpers and orchestrator

def _clear_profile_stepper_state() -> None:
    """Clear all stepper session state keys. Called on Cancel and after successful save."""
    for _k in (
        "profile_step", "profile_restaurant_name",
        "profile_food_types", "profile_store_type", "profile_seat_range",
    ):
        st.session_state.pop(_k, None)


def _render_profile_step_1() -> None:
    """Step 1: Restaurant name + food types."""
    # Step 1a: Title and helper text
    st.subheader("Your Restaurant")
    st.write("Start with the basics — your restaurant name and the food you serve.")

    # Step 1b: Restaurant name input (required)
    _restaurant_name = st.text_input(
        "Restaurant Name",
        value=st.session_state["profile_restaurant_name"],
        placeholder="e.g. My Restaurant",
        key="step1_restaurant_name",
    )

    # Step 1c: Cuisine-based food type options (Thai + English labels, English keys stored)
    _FOOD_OPTIONS = {
        "rice_curry":   "ข้าวแกง / ข้าวราดแกง (Rice Curry)",
        "noodle":       "ก๋วยเตี๋ยว / ราเมน (Noodle / Ramen)",
        "porridge":     "โจ๊ก / ข้าวต้ม (Porridge / Rice Soup)",
        "chicken_rice": "ข้าวมันไก่ / ข้าวขาหมู (Chicken Rice / Pork Leg Rice)",
        "spicy_soup":   "ต้มยำ / ต้มแซ่บ / แกงป่า (Spicy Soup)",
        "stir_fry":     "ข้าวผัด / ผัดกะเพรา (Stir Fry)",
        "isaan":        "ส้มตำ / อาหารอีสาน (Isaan Food)",
        "spicy_salad":  "ยำ / อาหารรสจัด (Spicy Salad)",
        "healthy":      "อาหารเพื่อสุขภาพ / สลัดบ็อกซ์ (Healthy / Salad Box)",
        "vegan":        "อาหารมังสวิรัติ / Vegan (Vegan)",
        "meal_prep":    "ข้าวกล่อง / Meal Prep (Meal Prep)",
    }
    # Step 1d: Filter existing selections — drop any legacy cost-logic keys not in new list
    _valid_keys = set(_FOOD_OPTIONS.keys())
    _existing_food = [k for k in st.session_state["profile_food_types"] if k in _valid_keys]

    # Step 1e: Food types multiselect (at least 1 required)
    _food_types = st.multiselect(
        "Select what your restaurant sells",
        options=list(_FOOD_OPTIONS.keys()),
        default=_existing_food,
        format_func=lambda k: _FOOD_OPTIONS[k],
        help="This helps us understand your menu and cost structure",
        key="step1_food_types",
    )

    # Step 1f: Navigation — Cancel | Next
    st.write("")
    _col_cancel, _col_spacer, _col_next = st.columns([1, 3, 1])
    with _col_cancel:
        if st.button("Cancel", key="step1_cancel"):
            _clear_profile_stepper_state()
            st.session_state["page"] = "dashboard"
            st.rerun()
    with _col_next:
        if st.button("Next →", type="primary", key="step1_next"):
            # Step 1g: Validate both required fields before advancing
            if not _restaurant_name.strip():
                st.warning("Please enter your restaurant name to continue.")
            elif not _food_types:
                st.warning("Please select at least one food type to continue.")
            else:
                st.session_state["profile_restaurant_name"] = _restaurant_name.strip()
                st.session_state["profile_food_types"] = _food_types
                st.session_state["profile_step"] = 2
                st.rerun()


def _render_profile_step_2() -> None:
    """Step 2: Store type and seat range (seat_range options depend on store_type)."""
    # Step 2a: Title
    st.subheader("Store Setup")
    st.write("Tell us how your restaurant operates.")

    # Step 2b: Store type selectbox
    _STORE_OPTIONS = ["ghost_kitchen", "hybrid_small", "full_restaurant"]
    _STORE_LABELS = {
        "ghost_kitchen":   "Ghost Kitchen (Delivery Only)",
        "hybrid_small":    "Hybrid Small (Dine-in + Delivery)",
        "full_restaurant": "Full Restaurant (Dine-in Focus)",
    }
    _store_idx = (
        _STORE_OPTIONS.index(st.session_state["profile_store_type"])
        if st.session_state["profile_store_type"] in _STORE_OPTIONS else 0
    )
    _store_type = st.selectbox(
        "Store Type",
        options=_STORE_OPTIONS,
        index=_store_idx,
        format_func=lambda v: _STORE_LABELS[v],
        key="step2_store_type",
    )

    # Step 2c: Seat range — valid options depend on selected store_type
    _SEAT_LABELS = {
        "0":       "ไม่มีที่นั่ง (Delivery Only)",
        "1_10":    "1–10 ที่นั่ง (ร้านขนาดเล็ก)",
        "11_30":   "11–30 ที่นั่ง (ร้านขนาดกลาง)",
        "31_plus": "มากกว่า 30 ที่นั่ง (ร้านขนาดใหญ่)",
    }
    _SEAT_FOR_STORE = {
        "ghost_kitchen":   ["0"],
        "hybrid_small":    ["1_10"],
        "full_restaurant": ["11_30", "31_plus"],
    }
    _valid_seats = _SEAT_FOR_STORE[_store_type]

    # Step 2d: Auto-correct stale session state when current value is invalid for store_type
    if st.session_state["profile_seat_range"] not in _valid_seats:
        st.session_state["profile_seat_range"] = _valid_seats[0]

    if len(_valid_seats) == 1:
        # Step 2e: Single option — show as read-only info field, no user input needed
        _seat_range = _valid_seats[0]
        st.text_input(
            "Seat Range",
            value=_SEAT_LABELS[_seat_range],
            disabled=True,
            help="Seat range is fixed for this store type.",
            key="step2_seat_range_display",
        )
    else:
        # Step 2f: Multiple options — show selectbox with only valid choices
        _seat_idx = (
            _valid_seats.index(st.session_state["profile_seat_range"])
            if st.session_state["profile_seat_range"] in _valid_seats else 0
        )
        _seat_range = st.selectbox(
            "Seat Range",
            options=_valid_seats,
            index=_seat_idx,
            format_func=lambda v: _SEAT_LABELS[v],
            key="step2_seat_range",
        )

    # Step 2g: Navigation — Cancel | Back | Next
    st.write("")
    _col_cancel, _col_back, _col_spacer, _col_next = st.columns([1, 1, 2, 1])
    with _col_cancel:
        if st.button("Cancel", key="step2_cancel"):
            _clear_profile_stepper_state()
            st.session_state["page"] = "dashboard"
            st.rerun()
    with _col_back:
        if st.button("← Back", key="step2_back"):
            st.session_state["profile_step"] = 1
            st.rerun()
    with _col_next:
        if st.button("Next →", type="primary", key="step2_next"):
            # Step 2h: Final guard — reject invalid store_type + seat_range combinations
            if _seat_range not in _SEAT_FOR_STORE[_store_type]:
                st.warning("Please select a valid seat range for your store type.")
            else:
                st.session_state["profile_store_type"] = _store_type
                st.session_state["profile_seat_range"] = _seat_range
                st.session_state["profile_step"] = 3
                st.rerun()


def _render_profile_step_3() -> None:
    """Step 3: Platform & Revenue Configuration — placeholder."""
    # Step 3a: Title and placeholder with forward-looking explanation
    st.subheader("Platform & Revenue")
    st.info(
        "Step 3 configuration will be added later.\n\n"
        "**Coming soon:** Configure your delivery platforms (Grab, FoodPanda, LINE MAN, etc.) "
        "and revenue breakdown. This will allow FFIA to estimate your delivery fee impact on margin."
    )

    # Step 3b: Navigation — Cancel | Back | Next
    st.write("")
    _col_cancel, _col_back, _col_spacer, _col_next = st.columns([1, 1, 2, 1])
    with _col_cancel:
        if st.button("Cancel", key="step3_cancel"):
            _clear_profile_stepper_state()
            st.session_state["page"] = "dashboard"
            st.rerun()
    with _col_back:
        if st.button("\u2190 Back", key="step3_back"):
            st.session_state["profile_step"] = 2
            st.rerun()
    with _col_next:
        if st.button("Next \u2192", type="primary", key="step3_next"):
            st.session_state["profile_step"] = 4
            st.rerun()


def _render_profile_step_4(current_user: dict, profile: dict | None) -> None:
    """Step 4: AI Risk Profile placeholder + summary + Save."""
    # Step 4a: AI profile placeholder with forward-looking context
    st.subheader("AI Risk Profile")
    st.info(
        "Step 4 AI profile will be added later.\n\n"
        "**Coming soon:** FFIA will automatically suggest your Target, Warning, and Risk margin "
        "thresholds based on your food types and store setup."
    )
    st.write("")

    # Step 4b: Summary of all collected inputs
    st.subheader("Profile Summary")
    st.caption(
        "Your profile will be used to personalize margin analysis and fuel impact recommendations."
    )
    st.write("**Restaurant Name:**", st.session_state["profile_restaurant_name"] or "\u2014")
    st.write("**Food Types:**", ", ".join(st.session_state["profile_food_types"]) or "\u2014")
    st.write("**Store Type:**", st.session_state["profile_store_type"])
    st.write("**Seat Range:**", st.session_state["profile_seat_range"])
    st.divider()

    # Step 4c: Final guard — disable Save if required data is missing
    _can_save = bool(
        st.session_state["profile_restaurant_name"].strip()
        and st.session_state["profile_food_types"]
    )
    if not _can_save:
        st.warning("Some required fields are missing. Please go back and complete all steps.")

    # Step 4d: Navigation — Cancel | Back | Save Profile
    _col_cancel, _col_back, _col_spacer, _col_save = st.columns([1, 1, 2, 1])
    with _col_cancel:
        if st.button("Cancel", key="step4_cancel"):
            _clear_profile_stepper_state()
            st.session_state["page"] = "dashboard"
            st.rerun()
    with _col_back:
        if st.button("\u2190 Back", key="step4_back"):
            st.session_state["profile_step"] = 3
            st.rerun()
    with _col_save:
        if st.button("Save Profile", type="primary", key="step4_save", disabled=not _can_save):
            # Step 4e: Resolve defaults for fields not collected in this stepper
            _existing_btype    = (profile.get("business_type") or "restaurant") if profile else "restaurant"
            _existing_currency = (profile.get("currency") or "THB") if profile else "THB"
            _existing_target   = float(profile.get("target_margin_pct") or 30.0) if profile else 30.0
            _existing_warning  = float(profile.get("warning_margin_pct") or 25.0) if profile else 25.0
            _existing_risk     = float(profile.get("risk_margin_pct") or 20.0) if profile else 20.0

            # Step 4f: Persist to DB using existing upsert helper
            try:
                upsert_restaurant_profile(
                    user_id=current_user["user_id"],
                    restaurant_name=st.session_state["profile_restaurant_name"],
                    business_type=_existing_btype,
                    food_types=st.session_state["profile_food_types"],
                    store_type=st.session_state["profile_store_type"],
                    seat_range=st.session_state["profile_seat_range"],
                    currency=_existing_currency,
                    target_margin_pct=_existing_target,
                    warning_margin_pct=_existing_warning,
                    risk_margin_pct=_existing_risk,
                )
                # Step 4g: Clear stepper state, signal success, rerun to reset to Step 1
                _clear_profile_stepper_state()
                st.session_state["profile_save_success"] = True
                st.rerun()
            except Exception:
                # Step 4h: DB failure — friendly message, raw exception not exposed
                st.error("Your profile could not be saved. Please try again or contact support.")


def _render_profile_settings_page(current_user: dict) -> None:
    """Orchestrate the 4-step Business Profile onboarding stepper."""
    # Step 1: Page header
    _render_page_hero(
        "Business Profile Setup",
        "Let\u2019s set up your restaurant profile in a few quick steps.",
        eyebrow="Restaurant Profile",
    )

    # Step 2: Fetch existing profile — used for pre-population and save-time defaults
    try:
        _profile = fetch_latest_restaurant_profile(current_user["user_id"])
    except Exception:
        st.error("Unable to load your profile. Please refresh the page or contact support.")
        return

    with st.container(border=True):
        _render_section_header(
            "Profile Details",
            "Keep your restaurant profile up to date so FFIA can personalize insights and recommendations.",
        )

        # Step 3: Show success banner if returning from a just-completed save
        if st.session_state.pop("profile_save_success", False):
            st.success("Business profile saved successfully.")

        # Step 4: Initialize stepper session state (only on first entry this session)
        if "profile_step" not in st.session_state:
            st.session_state["profile_step"] = 1
        if "profile_restaurant_name" not in st.session_state:
            st.session_state["profile_restaurant_name"] = (
                (_profile.get("restaurant_name") or "") if _profile else ""
            )
        if "profile_food_types" not in st.session_state:
            st.session_state["profile_food_types"] = (
                list(_profile.get("food_types") or []) if _profile else []
            )
        if "profile_store_type" not in st.session_state:
            st.session_state["profile_store_type"] = (
                (_profile.get("store_type") or "ghost_kitchen") if _profile else "ghost_kitchen"
            )
        if "profile_seat_range" not in st.session_state:
            st.session_state["profile_seat_range"] = (
                (_profile.get("seat_range") or "0") if _profile else "0"
            )

        # Step 5: Step indicator
        _step = st.session_state["profile_step"]
        st.markdown(f'<div class="step-badge">Step {_step} of 4</div>', unsafe_allow_html=True)
        st.progress(_step / 4)
        st.write("")

        # Step 6: Dispatch to active step renderer
        if _step == 1:
            _render_profile_step_1()
        elif _step == 2:
            _render_profile_step_2()
        elif _step == 3:
            _render_profile_step_3()
        else:
            _render_profile_step_4(current_user, _profile)


# Step 7: Dashboard helpers — session-cached data fetchers

def _get_cached_diesel_price() -> dict:
    """Fetch diesel price once per session from Bangchak API; cache result."""
    if "cached_diesel" not in st.session_state:
        try:
            from agent.tools.oil_price_tool import get_oil_price_from_bangchak  # noqa: PLC0415
            st.session_state["cached_diesel"] = get_oil_price_from_bangchak("diesel")
        except Exception as _e:
            st.session_state["cached_diesel"] = {"error": str(_e)}
    return st.session_state["cached_diesel"]


def _get_cached_item_count(user_id: str) -> int | None:
    """Count invoice line items once per session."""
    if "cached_item_count" not in st.session_state:
        try:
            st.session_state["cached_item_count"] = count_invoice_items(user_id)
        except Exception:
            st.session_state["cached_item_count"] = None
    return st.session_state["cached_item_count"]


# Step 7b: Helper — run agent and append result to session messages
def _run_agent_turn(prompt: str, current_user: dict, msg_container) -> None:
    """Append prompt as user message, call agent, render response inside msg_container."""
    st.session_state.messages.append({"role": "user", "content": prompt})

    with msg_container:
        with st.chat_message("user"):
            st.markdown(prompt)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]

        with st.chat_message("assistant"):
            with st.spinner("FFIA is thinking..."):
                result = _get_run_agent()(prompt, history, current_user_id=current_user["user_id"])

            steps = result.get("intermediate_steps", [])
            if steps:
                with st.expander("Agent Reasoning Trace (click to expand)", expanded=False):
                    for _i, (_tool_name, _obs) in enumerate(steps, 1):
                        st.markdown(f"**Step {_i} — Action:** `{_tool_name}`")
                        if _obs:
                            st.markdown(f"**Observation:** {str(_obs)[:500]}")
                        st.divider()
                    reply = result.get("output", "Sorry, I could not produce an answer.")
                    st.markdown(f"**Final Answer:** {reply}")
            else:
                reply = result.get("output", "Sorry, I could not produce an answer.")

            st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})


# Step 8: Dashboard page renderer — decision cockpit layout
def _render_dashboard_page(current_user: dict):
    """Render the main Dashboard: header, decision cards, quick actions, agent workspace."""

    # ── Section A: Header ──────────────────────────────────────────────────────
    _render_page_hero(
        "FFIA — Fuel & Food Impact Analyzer",
        "Your FFIA Agent is ready. Ask about diesel impact, margin risk, "
        "repricing ideas, or your latest invoice.",
        eyebrow="Restaurant Intelligence",
    )

    # Step A1: Fetch data for status pills and decision cards
    _diesel = _get_cached_diesel_price()
    _item_count = _get_cached_item_count(current_user["user_id"])
    _diesel_ok = "error" not in _diesel

    # Step A2: Status pills row
    _fuel_pill_class = "status-pill" if _diesel_ok else "status-pill error"
    _fuel_pill_label = "Fuel API: Connected" if _diesel_ok else "Fuel API: Unavailable"
    _count_label = f"{_item_count} items tracked" if _item_count is not None else "No items yet"
    st.markdown(f"""
<div class="status-pills-row">
  <span class="{_fuel_pill_class}"><span class="pill-dot"></span>{_fuel_pill_label}</span>
  <span class="status-pill info"><span class="pill-dot"></span>{_count_label}</span>
  <span class="status-pill info"><span class="pill-dot"></span>Last sync: today</span>
</div>
""", unsafe_allow_html=True)

    # ── Section B: Decision Cards ──────────────────────────────────────────────
    _dc1, _dc2, _dc3 = st.columns(3)

    # Card 1 — Diesel Price
    if _diesel_ok:
        _price_val = f"{_diesel['price_per_liter']:.2f} ฿/L"
        _price_sub = f"Updated {_diesel.get('updated_at', 'N/A')}"
        _card1_class = "decision-card warn"
        _card1_hint  = '<span class="dc-hint">May affect delivery costs</span>'
    else:
        _price_val = "Unavailable"
        _price_sub = "Could not reach Bangchak API"
        _card1_class = "decision-card muted"
        _card1_hint  = '<span class="dc-hint muted">Ask agent for latest price</span>'

    with _dc1:
        st.markdown(f"""
<div class="{_card1_class}">
  <div class="dc-label">Diesel Price Today</div>
  <div class="dc-value">{_price_val}</div>
  <div class="dc-sub">{_price_sub}</div>
  {_card1_hint}
</div>
""", unsafe_allow_html=True)

    # Card 2 — Menu Items Tracked
    if _item_count is not None and _item_count > 0:
        _items_val  = str(_item_count)
        _items_sub  = "Line items from your invoices"
        _card2_class = "decision-card ok"
        _card2_hint  = '<span class="dc-hint ok">Data available for analysis</span>'
    elif _item_count == 0:
        _items_val  = "0"
        _items_sub  = "No invoice items yet"
        _card2_class = "decision-card muted"
        _card2_hint  = '<span class="dc-hint info">Upload invoices to start</span>'
    else:
        _items_val  = "—"
        _items_sub  = "Could not load count"
        _card2_class = "decision-card muted"
        _card2_hint  = '<span class="dc-hint muted">Check database connection</span>'

    with _dc2:
        st.markdown(f"""
<div class="{_card2_class}">
  <div class="dc-label">Menu Items Tracked</div>
  <div class="dc-value">{_items_val}</div>
  <div class="dc-sub">{_items_sub}</div>
  {_card2_hint}
</div>
""", unsafe_allow_html=True)

    # Card 3 — Avg Gross Margin (W4+ feature placeholder)
    with _dc3:
        st.markdown("""
<div class="decision-card muted">
  <div class="dc-label">Avg Gross Margin</div>
  <div class="dc-value" style="font-size:1.2rem;color:#94a3b8;">Upload invoices<br>to calculate</div>
  <div class="dc-sub">Requires cost + revenue data</div>
  <span class="dc-hint info">W4+ feature</span>
</div>
""", unsafe_allow_html=True)

    st.write("")

    # ── Section C: Quick Actions ───────────────────────────────────────────────
    with st.container(border=True):
        _render_section_header(
            "What would you like to do today?",
            "Use a guided shortcut to start a common workflow, then continue the analysis in FFIA.",
        )

        _QUICK_ACTIONS = [
            ("⛽ Check Diesel Price",      "What is today's diesel price?"),
            ("📉 Find Low-Margin Items",    "Which of my menu items have the lowest margin?"),
            ("📈 Simulate +5฿ Oil",         "What happens to my costs if diesel increases by 5 baht?"),
            ("🧾 Analyze My Invoices",      "Summarize my invoice costs this month"),
            ("💡 Suggest Repricing",        "Suggest menu repricing based on current fuel costs"),
            ("📊 View Margin Breakdown",    "Show me a margin breakdown for my menu items"),
        ]

        _row1_cols = st.columns(3)
        _row2_cols = st.columns(3)
        for _col_idx, (_label, _prompt) in enumerate(_QUICK_ACTIONS):
            _col = _row1_cols[_col_idx] if _col_idx < 3 else _row2_cols[_col_idx - 3]
            with _col:
                st.markdown('<div class="action-card">', unsafe_allow_html=True)
                if st.button(_label, key=f"qa_{_col_idx}", use_container_width=True):
                    st.session_state["pending_prompt"] = _prompt
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # ── Section D: Agent Workspace ─────────────────────────────────────────────
    st.write("")
    with st.container(border=True):
        _render_section_header(
            "Ask FFIA Agent",
            "Get cost impact analysis, pricing suggestions, and fuel-risk insights in plain language.",
        )

        # Step D1: Prompt chips
        _CHIPS = [
            ("Today's diesel price?",     "What is today's diesel price?"),
            ("Riskiest menu items?",       "Which of my menu items have the highest cost risk?"),
            ("+5 baht fuel impact?",       "What happens to my costs if diesel increases by 5 baht?"),
            ("My invoice summary",         "Summarize my invoice costs this month"),
        ]
        _chip_cols = st.columns(len(_CHIPS))
        for _ci, (_chip_label, _chip_prompt) in enumerate(_CHIPS):
            with _chip_cols[_ci]:
                st.markdown('<div class="prompt-chip">', unsafe_allow_html=True)
                if st.button(_chip_label, key=f"chip_{_ci}", use_container_width=True):
                    st.session_state["pending_prompt"] = _chip_prompt
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    st.write("")

    # Step D2: Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Step D3: Scrollable chat messages container
    _msg_container = st.container(height=400, border=True)
    with _msg_container:
        for _msg in st.session_state.messages:
            with st.chat_message(_msg["role"]):
                st.markdown(_msg["content"])

    # Step D4: Process pending prompt (from quick actions / chips)
    _pending = st.session_state.pop("pending_prompt", None)
    if _pending:
        _run_agent_turn(_pending, current_user, _msg_container)

    # Step D5: Chat input
    _user_input = st.chat_input("Ask about diesel price, invoice costs, margin risk...")
    if _user_input:
        _run_agent_turn(_user_input, current_user, _msg_container)

    # ── Section E: Analysis History ────────────────────────────────────────────
    _past_assistant = [
        m["content"] for m in st.session_state.messages if m["role"] == "assistant"
    ]
    if _past_assistant:
        with st.expander(f"Analysis History ({len(_past_assistant)} responses)", expanded=False):
            for _idx, _answer in enumerate(reversed(_past_assistant[-10:]), 1):
                st.markdown(f"**{_idx}.** {_answer[:300]}{'...' if len(_answer) > 300 else ''}")
                if _idx < len(_past_assistant):
                    st.divider()


# Step 9: Page router — dispatch to correct page based on session state
_active_page = st.session_state.get("page", "dashboard")
if _active_page == "upload":
    _render_upload_page(_current_user)
elif _active_page == "profile_settings":
    _render_profile_settings_page(_current_user)
else:
    _render_dashboard_page(_current_user)
