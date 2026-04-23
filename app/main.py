# =============================================================================
# FFIA — app/main.py
# Streamlit Chat UI — wired to LangChain ReAct agent (Gemini 2.5 Flash).
# Data Upload page persists invoices to PostgreSQL via data/db.py.
# =============================================================================

# Step 1: Add project root to path so agent/ package can be imported
import re
import sys
import base64
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import date, datetime
from html import escape
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 2: Streamlit and lightweight imports only — heavy AI/DB resources are lazy-loaded
import pandas as pd
import streamlit as st
from app.utils.auth import authenticate_user, load_auth_users
from app.utils.upload_cache import build_uploaded_file_cache_key
from data.db import (
    create_tables,
    get_connection,
    invoice_exists,
    save_invoice,
    get_recent_invoices,
    fetch_invoices_current_month,
    fetch_invoice_items,
    fetch_latest_restaurant_profile,
    upsert_restaurant_profile,
    upsert_channel_mix,
    count_invoice_items,
    delete_invoice,
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

section[data-testid="stSidebar"] .stButton > button:focus {
    box-shadow: none !important;
    border-color: transparent !important;
    outline: none !important;
}

section[data-testid="stSidebar"] .stButton > button:focus-visible {
    box-shadow: 0 0 0 3px rgba(119, 170, 248, 0.16) !important;
    border-color: rgba(168, 194, 223, 0.96) !important;
    outline: none !important;
}

/* ── Active sidebar nav item ────────────────────────────────────────────────────
   Each nav button is preceded by an empty marker div (.sb-nav-marker / .is-active).
   Streamlit renders each st.markdown() and st.button() call as adjacent sibling divs,
   so :has() bridges from the marker to the following sibling that contains the button.
   active_page parameter → is_active bool → .is-active class → CSS. No data-testid hacks.
   ────────────────────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] div:has(.sb-nav-marker.is-active) + div button {
    background: rgba(255, 255, 255, 0.7) !important;
    color: #2f6cb9 !important;
    font-weight: 700 !important;
    border-color: rgba(200, 215, 231, 0.82) !important;
    box-shadow: var(--ffia-shadow-soft), inset 4px 0 0 rgba(116, 170, 248, 0.86) !important;
    transform: translateY(-1px);
}

section[data-testid="stSidebar"] div:has(.sb-nav-marker.is-primary) + div button {
    background: transparent !important;
    color: #658099 !important;
    font-weight: 600 !important;
    border-color: transparent !important;
    box-shadow: none !important;
}

section[data-testid="stSidebar"] div:has(.sb-nav-marker.is-primary) + div button:hover {
    background: rgba(255, 255, 255, 0.7) !important;
    color: var(--ffia-text) !important;
    border-color: rgba(200, 215, 231, 0.82) !important;
    transform: translateY(-1px);
    box-shadow: var(--ffia-shadow-soft) !important;
}

section[data-testid="stSidebar"] div:has(.sb-nav-marker.is-primary.is-active) + div button {
    background: rgba(255, 255, 255, 0.7) !important;
    color: #2f6cb9 !important;
    font-weight: 700 !important;
    border-color: rgba(200, 215, 231, 0.82) !important;
    box-shadow: var(--ffia-shadow-soft), inset 4px 0 0 rgba(116, 170, 248, 0.86) !important;
    transform: translateY(-1px);
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
    padding: 1rem 1.2rem !important;
    margin-bottom: 1.2rem !important;
    min-height: 3rem;
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

/* ── FFIA AI Answer Card ────────────────────────────────────────────────────
   Scoped under .ffia-answer-card so none of these rules leak to other
   parts of the app. Each rule overrides the global p/li muted color.     */
.ffia-answer-card {
    padding: 2px 0 6px 0;
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
}

/* ── Fallback flat-card elements (non-structured answers) ── */
.ffia-answer-card .ffia-h {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: var(--ffia-accent-strong);
    margin: 22px 0 8px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--ffia-border);
    line-height: 1.4;
}
.ffia-answer-card .ffia-h:first-child { margin-top: 2px; }

.ffia-answer-card .ffia-p {
    font-size: 14.5px !important;
    line-height: 1.74 !important;
    color: var(--ffia-text) !important;
    margin: 5px 0 0 0 !important;
    padding: 0 !important;
}

.ffia-answer-card .ffia-ul {
    margin: 5px 0 0 0;
    padding-left: 0;
    list-style: none;
}

.ffia-answer-card .ffia-li {
    font-size: 14px !important;
    line-height: 1.70 !important;
    color: var(--ffia-text) !important;
    margin: 5px 0 !important;
    padding-left: 1.35em;
    position: relative;
}
.ffia-answer-card .ffia-li::before {
    content: "›";
    position: absolute;
    left: 0.15em;
    color: var(--ffia-accent-strong);
    font-weight: 800;
    font-size: 15px;
    line-height: 1.65;
}

.ffia-answer-card strong { color: var(--ffia-text) !important; font-weight: 600; }

.ffia-answer-card code {
    font-size: 13px;
    background: rgba(79, 143, 239, 0.09);
    color: var(--ffia-accent-strong);
    border-radius: 4px;
    padding: 1px 5px;
    font-family: "SF Mono", "Fira Code", monospace;
}

.ffia-answer-card .ffia-meta {
    font-size: 11.5px !important;
    color: var(--ffia-text-soft) !important;
    font-style: italic;
    margin-top: 20px;
    padding-top: 10px;
    border-top: 1px solid var(--ffia-border);
    line-height: 1.5;
}

/* ── Structured insight layout (profile / risk analysis answers) ── */

/* Main Risk hero — prominent, calm, no color noise */
.ffia-risk-hero {
    padding: 6px 0 6px 16px;
    border-left: 3px solid var(--ffia-accent-strong);
    margin-bottom: 22px;
}
.ffia-risk-hero-eyebrow {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--ffia-text-muted);
    margin-bottom: 7px;
    line-height: 1.4;
}
.ffia-risk-hero-body {
    font-size: 18px !important;
    font-weight: 700;
    color: var(--ffia-text) !important;
    line-height: 1.5 !important;
    margin: 0 !important;
    padding: 0 !important;
}
.ffia-risk-hero-body strong { color: var(--ffia-text) !important; font-weight: 800; }

/* Section — separated by space and a hairline, no background boxes */
.ffia-section {
    margin-top: 20px;
    padding-top: 18px;
    border-top: 1px solid var(--ffia-border);
}

/* Actions section — same spacing, accent title to signal "do this" */
.ffia-section--actions {
    background: none;
    border: none;
    border-top: 1px solid var(--ffia-border);
    border-radius: 0;
    padding: 18px 0 0 0;
    margin-top: 20px;
}

/* Section label — small caps only, no icon */
.ffia-section-head { margin-bottom: 10px; }
.ffia-section-title {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--ffia-text-muted);
}

/* Bullet list — used for why, evidence, and generic sections */
.ffia-blist {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 7px;
}
.ffia-bitem {
    font-size: 13.5px !important;
    color: var(--ffia-text) !important;
    line-height: 1.64 !important;
    padding-left: 1.1em;
    position: relative;
    margin: 0 !important;
}
.ffia-bitem::before {
    content: "·";
    position: absolute;
    left: 0;
    color: var(--ffia-text-muted);
    font-weight: 700;
    font-size: 17px;
    line-height: 1.38;
}
.ffia-bitem strong        { color: var(--ffia-text) !important; font-weight: 600; }
/* Inline evidence label — slightly muted, same size */
.ffia-ev-inline           { color: var(--ffia-text-muted) !important; font-weight: 600; }

/* Numbered action list — clean numbers, no boxes */
.ffia-alist {
    list-style: none;
    padding: 0;
    margin: 0;
    counter-reset: ffia-action;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.ffia-aitem {
    counter-increment: ffia-action;
    position: relative;
    padding: 0 0 0 26px;
    font-size: 13.5px !important;
    color: var(--ffia-text) !important;
    line-height: 1.60 !important;
    margin: 0 !important;
    background: none;
    border: none;
    border-radius: 0;
}
.ffia-aitem::before {
    content: counter(ffia-action);
    position: absolute;
    left: 0;
    top: 0;
    font-size: 11px;
    font-weight: 700;
    color: var(--ffia-accent-strong);
    line-height: 1.85;
    width: 16px;
    text-align: left;
}
.ffia-aitem strong { color: var(--ffia-text) !important; font-weight: 600; }
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
    is_primary: bool = False,
) -> bool:
    """Render a sidebar nav button preceded by a class marker div.

    Streamlit renders each call as an adjacent sibling div in the DOM — the marker div
    and the button div are siblings, never parent-child.  The CSS :has() rule in Step 3a
    styles the button based on the marker's .is-active class, bridging the sibling gap.
    active_page (passed by _render_sidebar) → is_active → class → CSS. No click state.
    """
    _classes = ["sb-nav-marker"]
    if is_active:
        _classes.append("is-active")
    if is_primary:
        _classes.append("is-primary")
    _cls = " ".join(_classes)
    st.markdown(f'<div class="{_cls}"></div>', unsafe_allow_html=True)
    return st.button(label, key=key, use_container_width=True)


def _render_sidebar(current_user: dict, active_page: str = "dashboard") -> None:
    """Render the FFIA sidebar: brand, grouped nav sections, and account.

    active_page is the single source of truth for which nav item appears highlighted.
    It is passed explicitly by the call site — the sidebar function never reads page
    state itself.  Each nav button receives is_active=(active_page == "<key>"), which
    sets the .sb-nav-marker.is-active class, which the CSS :has() rule picks up.
    """
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

        if _render_sidebar_nav_button("Overview", key="nav_dashboard", is_active=active_page == "dashboard"):
            st.session_state["page"] = "dashboard"
            st.rerun()

        if _render_sidebar_nav_button("Dashboard", key="nav_dashboard_viz", is_active=active_page == "dashboard_viz"):
            st.session_state["page"] = "dashboard_viz"
            st.rerun()

        if _render_sidebar_nav_button(
            "Business Profile",
            key="nav_profile",
            is_active=active_page == "profile_settings",
        ):
            st.session_state["page"] = "profile_settings"
            st.rerun()

        if _render_sidebar_nav_button("Upload Invoice", key="nav_upload", is_active=active_page == "upload"):
            st.session_state["page"] = "upload"
            st.rerun()

        if _render_sidebar_nav_button(
            "AI Assistant",
            key="nav_ai_assistant",
            is_active=active_page == "ai_assistant",
            is_primary=True,
        ):
            st.session_state["page"] = "ai_assistant"
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


_render_sidebar(_current_user, active_page=st.session_state.get("page", "dashboard"))

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

    # Step 6b: Display invoice rows with per-row delete button
    _hdr1, _hdr2, _hdr3, _hdr4, _hdr5 = st.columns([2, 3, 2, 2, 1])
    _hdr1.markdown("**Date**")
    _hdr2.markdown("**Vendor**")
    _hdr3.markdown("**Invoice No**")
    _hdr4.markdown("**Total (THB)**")
    _hdr5.markdown("**Del**")

    for _row in invoices:
        _inv_id   = _row["id"]
        _inv_no   = _row["invoice_no"]
        _vendor   = _row["vendor"]
        _inv_date = _row["invoice_date"]
        _total    = _row["total_amount"]
        _ck       = f"confirm_del_{_inv_id}"

        _c1, _c2, _c3, _c4, _c5 = st.columns([2, 3, 2, 2, 1])
        _c1.write(str(_inv_date))
        _c2.write(_vendor)
        _c3.write(_inv_no)
        _c4.write(f"{_total:,.2f}")

        if _c5.button("Delete", key=f"del_{_inv_id}", type="secondary"):
            st.session_state[_ck] = True

        if st.session_state.get(_ck):
            st.warning(f"Delete invoice {_inv_no} from {_vendor} ({_inv_date})?")
            st.markdown(
                f"""
                <style>
                [data-testid*="confirm_{_inv_id}"] > button {{
                    background-color: #dc2626 !important;
                    border-color: #dc2626 !important;
                    color: #ffffff !important;
                }}
                [data-testid*="confirm_{_inv_id}"] > button:hover {{
                    background-color: #b91c1c !important;
                    border-color: #b91c1c !important;
                    color: #ffffff !important;
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )
            _cc1, _cc2 = st.columns(2)
            if _cc1.button("Confirm", key=f"confirm_{_inv_id}", type="primary"):
                delete_invoice(_inv_id, current_user["user_id"])
                st.session_state.pop(_ck)
                st.success("ลบแล้ว")
                st.rerun()
            if _cc2.button("Cancel", key=f"cancel_{_inv_id}", type="secondary"):
                st.session_state.pop(_ck)
                st.rerun()

    st.divider()
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
        "profile_channels",
    ):
        st.session_state.pop(_k, None)
    # Clear all step3 widget keys (number_input / text_input keys prefixed step3_)
    _step3_keys = [k for k in list(st.session_state.keys()) if k.startswith("step3_")]
    for _k in _step3_keys:
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

    # Step 2d: Reset stale step2_seat_range widget key when invalid for the current store_type.
    # Deleting the key before rendering forces re-initialization from the index parameter,
    # preventing Streamlit from re-using a stale value across store_type changes.
    # profile_seat_range is NOT mutated here — only written on Next click alongside profile_store_type.
    if st.session_state.get("step2_seat_range") not in _valid_seats:
        st.session_state.pop("step2_seat_range", None)

    if _store_type == "ghost_kitchen":
        # Step 2e: Delivery-only — seat range is always "0", hide the field entirely
        _seat_range = "0"
    elif len(_valid_seats) == 1:
        # Step 2f: Single option (non-delivery) — show as read-only info field
        _seat_range = _valid_seats[0]
        st.text_input(
            "Seat Range",
            value=_SEAT_LABELS[_seat_range],
            disabled=True,
            help="Seat range is fixed for this store type.",
            key="step2_seat_range_display",
        )
    else:
        # Step 2g: Multiple options — show selectbox with only valid choices
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


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 helpers — Platform & Revenue (doc-first, MVP logic)
# Sources:
#   docs/business_rules.md — L4 COGS base ranges per cuisine group
#   docs/scenarios.md      — net margin scenario thresholds
# ─────────────────────────────────────────────────────────────────────────────

# MVP assumption: map food_type keys to COGS base midpoints from docs/business_rules.md L4
_FOOD_TYPE_COGS_BASE: dict = {
    "rice_curry":   0.375,  # lpg_intensive: 35–40%
    "noodle":       0.355,  # freshness_pkg: 33–38%
    "porridge":     0.355,  # freshness_pkg: 33–38%
    "chicken_rice": 0.375,  # lpg_intensive: 35–40%
    "spicy_soup":   0.375,  # lpg_intensive: 35–40%
    "stir_fry":     0.375,  # lpg_intensive: 35–40%
    "isaan":        0.375,  # lpg_intensive: 35–40%
    "spicy_salad":  0.355,  # freshness_pkg: 33–38%
    "healthy":      0.300,  # high_energy_ops: 25–35%
    "vegan":        0.300,  # high_energy_ops: 25–35%
    "meal_prep":    0.300,  # high_energy_ops: 25–35%
}

# LPG-intensive food type keys — map to lpg_intensive COGS group (business_rules.md L4)
_LPG_FOOD_TYPES = {"rice_curry", "stir_fry", "spicy_soup", "isaan", "chicken_rice"}

# Channel metadata:
# (session_key, display_label, default_rev_share, default_gp_pct, gp_editable, logo_file)
_PLATFORM_CHANNEL_META = [
    ("grab_food",       "Grab Food",            40, 28, True,  "grab.png"),
    ("line_man",        "LINE MAN",              30, 27, True,  "lineman.png"),
    ("shopee_food",     "Shopee Food",           20, 22, True,  "shopeefood.png"),
    ("walkin_selfpick", "Walk-in / Self-pickup", 10,  0, False, "walkin.png"),
]


def _load_logo_b64(filename: str) -> str | None:
    """Load a platform logo from app/assets/ and return as a base64 data URI, or None."""
    _path = Path(__file__).parent / "assets" / filename
    if not _path.exists():
        return None
    with open(_path, "rb") as _fh:
        _b64 = base64.b64encode(_fh.read()).decode()
    _ext = _path.suffix.lstrip(".")
    return f"data:image/{_ext};base64,{_b64}"


def _get_default_platform_values() -> dict:
    """Return default channel config keyed by session key."""
    return {
        ch_key: {"label": label, "revenue_share_pct": rev, "gp_pct": gp, "enabled": True}
        for ch_key, label, rev, gp, _, _logo in _PLATFORM_CHANNEL_META
    }


def _estimate_food_cost_pct(food_types: list) -> float:
    """Estimate avg food cost % from selected food types using L4 COGS base midpoints.

    MVP assumption: unmapped food types default to lpg_intensive midpoint (37.5%).
    """
    if not food_types:
        return 0.375  # MVP assumption: fallback to lpg_intensive midpoint
    bases = [_FOOD_TYPE_COGS_BASE.get(ft, 0.375) for ft in food_types]
    return sum(bases) / len(bases)


def _estimate_fixed_cost_pct(store_type: str, seat_range: str) -> float:
    """Estimate fixed overhead % from store type and seat range.

    MVP assumption: not explicitly defined in docs — derived from operational context.
    ghost_kitchen has the lowest overhead (delivery-only, no dine-in space);
    full large restaurant has the highest (rent, staff, utilities).
    """
    if store_type == "ghost_kitchen":
        return 0.15
    elif store_type == "hybrid_small":
        return 0.20
    elif seat_range == "31_plus":
        return 0.28
    else:  # full_restaurant, 11_30 seats
        return 0.25


def _compute_blended_margin_preview(
    channels: dict,
    food_types: list,
    store_type: str,
    seat_range: str,
) -> dict:
    """Compute blended GP cost, estimated food cost, fixed cost, and net margin.

    Formula (doc-first):
      blended_gp_pct  = weighted avg of each channel's gp_pct by revenue share
      food_cost_pct   = avg COGS base midpoint from selected food types (L4)
      fixed_cost_pct  = store_type + seat_range lookup (MVP assumption)
      net_margin_pct  = 100 - blended_gp - food_cost - fixed_cost
    """
    # Step P1: Weighted blended GP across all channels
    total_rev = sum(ch["revenue_share_pct"] for ch in channels.values())
    if total_rev <= 0:
        blended_gp = 0.0
    else:
        blended_gp = sum(
            (ch["revenue_share_pct"] / total_rev) * (ch["gp_pct"] / 100)
            for ch in channels.values()
        )

    # Step P2: Food cost and fixed cost estimates
    food_cost  = _estimate_food_cost_pct(food_types)
    fixed_cost = _estimate_fixed_cost_pct(store_type, seat_range)

    # Step P3: Net margin
    net_margin = 1.0 - blended_gp - food_cost - fixed_cost

    return {
        "blended_gp_pct": round(blended_gp  * 100, 1),
        "food_cost_pct":  round(food_cost   * 100, 1),
        "fixed_cost_pct": round(fixed_cost  * 100, 1),
        "net_margin_pct": round(net_margin  * 100, 1),
    }


def _render_profile_step_3() -> None:
    """Step 3: Platform & Revenue — optional channel cards with logos and live margin preview."""
    # Step 3a: Title and description
    st.subheader("Platform & Revenue")
    st.write(
        "Enable the channels you use, then set each one's revenue share and platform fee. "
        "FFIA uses this to estimate your blended margin in real-time."
    )

    # Step 3b: Initialize widget defaults on first entry — respect user edits on rerun
    _saved = st.session_state.get("profile_channels") or {}
    for _ch_key, _label, _def_rev, _def_gp, _gp_editable, _logo_file in _PLATFORM_CHANNEL_META:
        _en_key  = f"step3_{_ch_key}_enabled"
        _rev_key = f"step3_{_ch_key}_rev"
        _gp_key  = f"step3_{_ch_key}_gp"
        if _en_key not in st.session_state:
            st.session_state[_en_key] = bool(_saved.get(_ch_key, {}).get("enabled", True))
        if _rev_key not in st.session_state:
            st.session_state[_rev_key] = float(
                _saved.get(_ch_key, {}).get("revenue_share_pct", _def_rev)
            )
        if _gp_editable and _gp_key not in st.session_state:
            st.session_state[_gp_key] = float(
                _saved.get(_ch_key, {}).get("gp_pct", _def_gp)
            )

    # Step 3c: Render channel cards — 2 per row
    _cols_row1 = st.columns(2)
    _cols_row2 = st.columns(2)
    for _i, (_ch_key, _label, _def_rev, _def_gp, _gp_editable, _logo_file) in enumerate(
        _PLATFORM_CHANNEL_META
    ):
        _col    = _cols_row1[_i] if _i < 2 else _cols_row2[_i - 2]
        _en_key = f"step3_{_ch_key}_enabled"
        # Read enabled state from session state (already updated by widget on previous rerun)
        _is_enabled = bool(st.session_state.get(_en_key, True))

        with _col:
            with st.container(border=True):
                # Step 3c-i: Card header — logo + label on left, Enable toggle on right
                _hdr_left, _hdr_right = st.columns([3, 1])
                with _hdr_left:
                    _logo_uri = _load_logo_b64(_logo_file)
                    # Walk-in gets a "No commission" badge inline with its label
                    _badge_html = (
                        '<span style="margin-left:0.45rem;padding:0.12rem 0.5rem;'
                        'border-radius:999px;font-size:0.68rem;font-weight:700;'
                        'background:rgba(90,175,132,0.12);color:#3d9068;'
                        'border:1px solid rgba(90,175,132,0.35);white-space:nowrap;">'
                        'No commission</span>'
                        if _ch_key == "walkin_selfpick" else ""
                    )
                    if _logo_uri:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:0.55rem;'
                            f'padding:0.1rem 0 0.2rem 0;flex-wrap:wrap;">'
                            f'<img src="{_logo_uri}" style="height:28px;width:auto;'
                            f'border-radius:6px;object-fit:contain;">'
                            f'<span style="font-weight:700;font-size:0.95rem;'
                            f'color:var(--ffia-text);">{escape(_label)}</span>'
                            f'{_badge_html}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:0.45rem;">'
                            f'<strong>{escape(_label)}</strong>{_badge_html}</div>',
                            unsafe_allow_html=True,
                        )
                with _hdr_right:
                    # Checkbox key drives _is_enabled on the NEXT rerun
                    st.checkbox("Active channel", key=_en_key)

                # Step 3c-ii: Inputs — only shown when this channel is enabled
                if _is_enabled:
                    st.number_input(
                        "Revenue Share (%)",
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        format="%.0f",
                        key=f"step3_{_ch_key}_rev",
                        help="% of total monthly revenue from this channel.",
                    )
                    if _gp_editable:
                        st.number_input(
                            "Platform Fee (%)",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.5,
                            format="%.1f",
                            key=f"step3_{_ch_key}_gp",
                            help="Commission % charged by this platform.",
                        )
                    else:
                        st.caption("Platform fee: 0% — no commission")

    # Step 3d: Collect current values — disabled channels contribute 0 to the totals.
    # Auto-disable: if an enabled channel has revenue_share = 0, treat it as inactive
    # and update session state so the checkbox reflects the change on next rerun.
    _current_channels: dict = {}
    for _ch_key, _label, _def_rev, _def_gp, _gp_editable, _ in _PLATFORM_CHANNEL_META:
        _is_enabled = bool(st.session_state.get(f"step3_{_ch_key}_enabled", True))
        if _is_enabled:
            _rev = float(st.session_state.get(f"step3_{_ch_key}_rev", _def_rev))
            _gp  = float(st.session_state.get(f"step3_{_ch_key}_gp", _def_gp)) if _gp_editable else 0.0
            # Auto-disable when revenue share is set to 0
            if _rev == 0.0:
                st.session_state[f"step3_{_ch_key}_enabled"] = False
                _is_enabled = False
        else:
            _rev = 0.0
            _gp  = 0.0
        _current_channels[_ch_key] = {
            "label":             _label,
            "revenue_share_pct": _rev,
            "gp_pct":            _gp,
            "enabled":           _is_enabled,
        }

    # Step 3e: Validation banner — only enabled channels must total 100%
    _enabled_channels = {k: v for k, v in _current_channels.items() if v["enabled"]}
    _total_rev = sum(ch["revenue_share_pct"] for ch in _enabled_channels.values())
    st.write("")
    if not _enabled_channels:
        st.warning("Enable at least one channel to continue.")
    elif abs(_total_rev - 100.0) > 0.5:
        st.warning(
            f"Enabled channel revenue shares total **{_total_rev:.0f}%** — "
            "they must add up to **100%**. Adjust the values above."
        )
    else:
        st.success("Enabled channel revenue shares total 100% ✓")

    # Step 3f: Live blended margin preview card
    st.write("")
    with st.container(border=True):
        _render_section_header(
            "Estimated Blended Margin Preview",
            "Calculated from your enabled channels, food types, and store setup. Updates as you type.",
        )
        _preview = _compute_blended_margin_preview(
            channels   = _current_channels,  # disabled channels have 0 rev share — safe to pass all
            food_types = st.session_state.get("profile_food_types", []),
            store_type = st.session_state.get("profile_store_type", "ghost_kitchen"),
            seat_range = st.session_state.get("profile_seat_range", "0"),
        )
        _pm1, _pm2, _pm3, _pm4 = st.columns(4)
        with _pm1:
            st.metric(
                "Avg GP Cost",
                f"{_preview['blended_gp_pct']:.1f}%",
                help="Weighted avg platform commission across enabled channels.",
            )
        with _pm2:
            st.metric(
                "Est. Food Cost",
                f"{_preview['food_cost_pct']:.1f}%",
                help="Based on your selected food types (L4 COGS base midpoints).",
            )
        with _pm3:
            st.metric(
                "Est. Fixed Cost",
                f"{_preview['fixed_cost_pct']:.1f}%",
                help="Based on your store type and seating range (MVP assumption).",
            )
        with _pm4:
            st.metric(
                "Est. Net Margin",
                f"{_preview['net_margin_pct']:.1f}%",
                help="= 100% − GP Cost − Food Cost − Fixed Cost",
            )

        # Step 3g: Net margin status badge + one insight line
        _nm = _preview["net_margin_pct"]
        if _nm > 25:
            _status_color = "#3d9068"
            _status_bg    = "rgba(90,175,132,0.12)"
            _status_bd    = "rgba(90,175,132,0.35)"
            _status_label = "Good"
            _status_icon  = "✓"
        elif _nm >= 15:
            _status_color = "#c28747"
            _status_bg    = "rgba(255,190,90,0.12)"
            _status_bd    = "rgba(236,208,169,0.5)"
            _status_label = "Warning"
            _status_icon  = "⚠"
        else:
            _status_color = "#c16f6f"
            _status_bg    = "rgba(255,90,90,0.10)"
            _status_bd    = "rgba(237,197,197,0.55)"
            _status_label = "Risk"
            _status_icon  = "✕"

        st.markdown(
            f'<div style="display:inline-flex;align-items:center;gap:0.4rem;'
            f'margin:0.5rem 0 0.3rem 0;padding:0.3rem 0.75rem;border-radius:999px;'
            f'background:{_status_bg};border:1px solid {_status_bd};'
            f'color:{_status_color};font-size:0.82rem;font-weight:700;">'
            f'{_status_icon} Margin status: {_status_label}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Step 3h-insight: One actionable insight based on channel mix
        _delivery_rev = sum(
            _current_channels[k]["revenue_share_pct"]
            for k in ("grab_food", "line_man", "shopee_food")
            if _current_channels[k]["enabled"]
        )
        _walkin_rev = _current_channels["walkin_selfpick"]["revenue_share_pct"]
        if _delivery_rev >= 70:
            _insight = (
                f"💡 **{_delivery_rev:.0f}% of your revenue** depends on high-commission "
                "platforms. Consider promoting self-pickup to reduce GP cost."
            )
        elif _walkin_rev > 0 and _walkin_rev < 20:
            _gain = round(_preview["blended_gp_pct"] * 0.10 / 100 * 10, 1)
            _insight = (
                f"💡 Increasing Walk-in / Self-pickup by 10% could reduce your avg GP cost "
                f"by ~{_gain:.1f} percentage points."
            )
        else:
            _insight = "💡 Your channel mix looks balanced across delivery and direct sales."
        st.caption(_insight)

        # Step 3h-scenario: Scenario guidance from docs/scenarios.md
        if _nm < 15:
            st.error(
                "FFIA recommends an **Operational Optimization** strategy — switch to closer "
                "suppliers or promote self-pickup to reduce GP costs. *(Scenario 3)*"
            )
        elif _nm < 20:
            st.warning(
                "FFIA suggests a **Targeted Price Adjustment** on your most fuel-impacted items. "
                "*(Scenario 2)*"
            )

    # Step 3h: Navigation — Cancel | Back | Next
    st.write("")
    _col_cancel, _col_back, _col_spacer, _col_next = st.columns([1, 1, 2, 1])
    with _col_cancel:
        if st.button("Cancel", key="step3_cancel"):
            _clear_profile_stepper_state()
            st.session_state["page"] = "dashboard"
            st.rerun()
    with _col_back:
        if st.button("← Back", key="step3_back"):
            st.session_state["profile_step"] = 2
            st.rerun()
    with _col_next:
        if st.button("Next →", type="primary", key="step3_next"):
            # Step 3i: Validate before advancing
            _errors = []
            if not _enabled_channels:
                _errors.append("Enable at least one channel to continue.")
            else:
                for _ch_key, _label, _, _, _, _ in _PLATFORM_CHANNEL_META:
                    if not _current_channels[_ch_key]["enabled"]:
                        continue
                    _rev = _current_channels[_ch_key]["revenue_share_pct"]
                    _gp  = _current_channels[_ch_key]["gp_pct"]
                    if _rev <= 0:
                        _errors.append(f"{_label}: Active channels must have Revenue Share > 0%.")
                    elif not (0 < _rev <= 100):
                        _errors.append(f"{_label}: Revenue share must be between 0 and 100%.")
                    if not (0 <= _gp <= 100):
                        _errors.append(f"{_label}: Platform fee must be 0–100%.")
                if abs(_total_rev - 100.0) > 0.5:
                    _errors.append(
                        f"Enabled channel revenue shares must total 100% "
                        f"(currently {_total_rev:.0f}%)."
                    )
            if _errors:
                for _err in _errors:
                    st.warning(_err)
            else:
                # Step 3j: Persist to session state (no DB field yet — used in Step 4 + preview)
                st.session_state["profile_channels"] = _current_channels
                st.session_state["profile_step"] = 4
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 helpers — AI Risk Profile (doc-first)
# ─────────────────────────────────────────────────────────────────────────────

def _build_ai_profile_summary(store_type: str, food_types: list, channels: dict) -> str:
    """Build a one-line AI-style insight from store type, food types, and channel mix."""
    _STORE_LABELS = {
        "ghost_kitchen":   "Ghost Kitchen",
        "hybrid_small":    "Hybrid Small Restaurant",
        "full_restaurant": "Full-Service Restaurant",
    }
    _store = _STORE_LABELS.get(store_type, "Restaurant")

    # Menu trait — fuel-sensitive if majority of food types are LPG-intensive
    _lpg_count = sum(1 for ft in food_types if ft in _LPG_FOOD_TYPES)
    _menu_trait = (
        "fuel-sensitive menu"
        if food_types and _lpg_count >= len(food_types) / 2
        else "varied menu"
    )

    # Channel trait — based on delivery revenue share
    _enabled = {k: v for k, v in channels.items() if v.get("enabled")}
    _delivery_rev = sum(
        v["revenue_share_pct"] for k, v in _enabled.items()
        if k in ("grab_food", "line_man", "shopee_food")
    )
    if _delivery_rev >= 70:
        _channel_trait = "high GP dependency"
    elif _delivery_rev >= 40:
        _channel_trait = "mixed channel revenue"
    else:
        _channel_trait = "strong direct sales"

    return f"{_store} with {_channel_trait} and {_menu_trait}"


def _derive_risk_level(net_margin_pct: float) -> dict:
    """Map estimated net margin to a labelled risk level with display colours."""
    if net_margin_pct > 25:
        return {
            "label": "Healthy", "icon": "✓",
            "color": "#3d9068",
            "bg":    "rgba(90,175,132,0.10)",
            "bd":    "rgba(90,175,132,0.38)",
        }
    elif net_margin_pct >= 15:
        return {
            "label": "Warning", "icon": "⚠",
            "color": "#c28747",
            "bg":    "rgba(255,190,90,0.10)",
            "bd":    "rgba(236,208,169,0.55)",
        }
    else:
        return {
            "label": "Critical", "icon": "✕",
            "color": "#c16f6f",
            "bg":    "rgba(220,80,80,0.08)",
            "bd":    "rgba(237,197,197,0.60)",
        }


def _derive_capability_tags(food_types: list, channels: dict) -> list:
    """Derive actionable capability tags from user profile data."""
    _tags = []
    _enabled = {k: v for k, v in channels.items() if v.get("enabled")}
    _delivery_rev = sum(
        v["revenue_share_pct"] for k, v in _enabled.items()
        if k in ("grab_food", "line_man", "shopee_food")
    )
    _walkin_rev = channels.get("walkin_selfpick", {}).get("revenue_share_pct", 0)

    if any(ft in _LPG_FOOD_TYPES for ft in food_types):
        _tags.append(("LPG Defense",    "#5a87c9", "rgba(89,135,201,0.10)", "rgba(189,210,236,0.50)"))
    if _delivery_rev >= 60:
        _tags.append(("GP Optimizer",   "#c28747", "rgba(255,190,90,0.10)", "rgba(236,208,169,0.50)"))
    if _walkin_rev < 20:
        _tags.append(("Channel Mix Fix","#c16f6f", "rgba(220,80,80,0.08)",  "rgba(237,197,197,0.55)"))
    return _tags  # list of (label, color, bg, border)


def _top_delivery_platform(channels: dict) -> tuple[str, float, float]:
    """Return (label, revenue_share_pct, gp_pct) for the highest-revenue delivery platform."""
    _delivery_keys = [
        ("grab_food",   "Grab Food"),
        ("line_man",    "LINE MAN"),
        ("shopee_food", "Shopee Food"),
    ]
    _best_label, _best_rev, _best_gp = "delivery platform", 0.0, 30.0
    for _key, _label in _delivery_keys:
        _ch = channels.get(_key, {})
        if _ch.get("enabled") and _ch.get("revenue_share_pct", 0) > _best_rev:
            _best_rev   = _ch["revenue_share_pct"]
            _best_gp    = _ch.get("gp_pct", 30.0)
            _best_label = _label
    return _best_label, _best_rev, _best_gp


def _build_fuel_insight(food_types: list, nm: float, channels: dict) -> str:
    """One-line fuel sensitivity insight shown under the AI summary card.

    Estimates margin impact of a ฿5/L diesel increase based on LPG menu exposure.
    Formula: LPG-intensive dishes ≈ 40% of food cost; food cost ≈ 35% of revenue.
    A 10% diesel increase → ~0.35 × 0.40 × 0.10 ≈ 1.4% margin loss per ฿5/L rise.
    Rounded and labelled per sensitivity tier.
    """
    _lpg_count = sum(1 for ft in food_types if ft in _LPG_FOOD_TYPES)
    _total     = max(len(food_types), 1)
    _lpg_ratio = _lpg_count / _total

    if _lpg_ratio >= 0.6:
        _impact = "3–5%"
        _note   = "High fuel sensitivity — most of your menu relies on LPG cooking."
    elif _lpg_ratio >= 0.3:
        _impact = "1–3%"
        _note   = "Moderate fuel sensitivity — some LPG-intensive dishes on your menu."
    else:
        return "Diesel price has limited direct impact on your current menu mix."

    _suffix = " Act now — margin is already near the threshold." if nm < 18 else ""
    return f"A ฿5/L diesel increase could reduce your margin by ~{_impact}. {_note}{_suffix}"


def _generate_alert_cards(
    nm: float,
    channels: dict,
    food_types: list,
    store_type: str,
) -> list:
    """Generate exactly 3 alert dicts: one critical, one warning, one opportunity.

    Each dict: type, title, problem, reason, action.
    All numeric values are derived from real channel/margin data — no hardcoded figures.
    Logic derived from docs/business_rules.md and docs/scenarios.md.
    """
    _enabled = {k: v for k, v in channels.items() if v.get("enabled")}
    _delivery_rev = sum(
        v["revenue_share_pct"] for k, v in _enabled.items()
        if k in ("grab_food", "line_man", "shopee_food")
    )
    _walkin_rev = channels.get("walkin_selfpick", {}).get("revenue_share_pct", 0)
    _has_lpg    = any(ft in _LPG_FOOD_TYPES for ft in food_types)
    _top_name, _top_rev, _top_gp = _top_delivery_platform(channels)

    # ── Critical ──────────────────────────────────────────────────────────────
    if nm < 15:
        # Estimate GP savings if 10% of volume shifts to Walk-in (0% fee)
        _shift_pct  = 10
        _gp_recover = round(_top_gp * _shift_pct / 100, 1)
        _critical = {
            "type": "critical", "title": "Margin at Risk",
            "problem": f"Estimated net margin is {nm:.1f}% — below the 15% safety threshold.",
            "reason":  "Platform GP fees and food cost are compressing profitability simultaneously.",
            "action":  (
                f"Shift {_shift_pct}% from {_top_name} to Walk-in — "
                f"at {_top_gp:.0f}% commission this recovers ~{_gp_recover:.1f}% margin. "
                f"(Scenario 3)"
            ),
        }
    elif _delivery_rev >= 80:
        _shift_target = max(15, round(_delivery_rev - 65))
        _gp_recover   = round(_top_gp * _shift_target / 100, 1)
        _critical = {
            "type": "critical", "title": "Over-reliance on Delivery",
            "problem": f"{_delivery_rev:.0f}% of your revenue flows through high-commission platforms.",
            "reason":  "Platform GP fees consume margin before ingredient costs are even counted.",
            "action":  (
                f"Shift {_shift_target}% from {_top_name} to Walk-in — "
                f"recovering ~{_gp_recover:.1f}% of revenue currently lost to commission."
            ),
        }
    else:
        _critical = {
            "type": "critical", "title": "No Critical Risk Detected",
            "problem": "Your current setup has no critical margin threats.",
            "reason":  "Margin, channel mix, and cost structure are within acceptable ranges.",
            "action":  "Continue monitoring diesel price and ingredient costs weekly via FFIA.",
        }

    # ── Warning ───────────────────────────────────────────────────────────────
    if _has_lpg and nm < 20:
        _lpg_count    = sum(1 for ft in food_types if ft in _LPG_FOOD_TYPES)
        _reprice_pct  = 5 if nm >= 17 else 10
        _warning = {
            "type": "warning", "title": "LPG Cost Exposure",
            "problem": (
                f"Your menu has {_lpg_count} LPG-intensive dish type(s) and margin is "
                f"{nm:.1f}% — approaching pressure territory."
            ),
            "reason":  "Stir fry, rice curry, and spicy soup are directly exposed to diesel price swings.",
            "action":  (
                f"Reprice your top LPG items by {_reprice_pct}–{_reprice_pct + 5}%, "
                f"or bundle them with a low-COGS side to absorb cost increases. (Scenario 2)"
            ),
        }
    elif _delivery_rev >= 60:
        _over_target = max(10, round(_delivery_rev - 60))
        _fee_recover = round(_top_gp * _over_target / 100, 1)
        _warning = {
            "type": "warning", "title": "GP Fee Pressure",
            "problem": (
                f"Delivery platforms account for {_delivery_rev:.0f}% of revenue "
                f"(target: below 60%)."
            ),
            "reason":  f"{_top_name} charges {_top_gp:.0f}% commission — reducing effective margin on every order.",
            "action":  (
                f"Promote self-pickup to shift {_over_target}% off {_top_name} — "
                f"this could recover ~{_fee_recover:.1f}% in GP fees per month."
            ),
        }
    else:
        _warning = {
            "type": "warning", "title": "Monitor Ingredient Cost",
            "problem": "Food cost is the largest variable affecting your margin.",
            "reason":  "Market price swings for key ingredients can erode profitability quickly.",
            "action":  "Review your top 5 ingredient prices monthly against Ministry of Commerce benchmarks.",
        }

    # ── Opportunity ───────────────────────────────────────────────────────────
    if _walkin_rev < 20:
        _shift_to_walkin = min(10, max(5, round(20 - _walkin_rev)))
        _gp_save = round(_top_gp * _shift_to_walkin / 100, 1)
        _opportunity = {
            "type": "opportunity", "title": "Self-Pickup Opportunity",
            "problem": f"Walk-in / Self-pickup is only {_walkin_rev:.0f}% of revenue (potential: 20%+).",
            "reason":  "Direct orders have 0% platform fee — the highest margin per order available.",
            "action":  (
                f"Offer a self-pickup discount to shift {_shift_to_walkin}% from {_top_name} — "
                f"saving ~{_gp_save:.1f}% in GP fees on those orders."
            ),
        }
    elif nm > 25 and store_type != "ghost_kitchen":
        _opportunity = {
            "type": "opportunity", "title": "Margin Room to Grow",
            "problem": f"Healthy margin of {nm:.1f}% gives room for a strategic promotion.",
            "reason":  "A margin buffer above 25% allows selective discounting without risk.",
            "action":  "Run a flash sale on your 2–3 lowest-COGS items to drive order volume.",
        }
    else:
        _opportunity = {
            "type": "opportunity", "title": "Optimise Procurement Cycle",
            "problem": "Frequent small purchases increase per-unit logistics cost.",
            "reason":  "Daily procurement adds fuel and delivery surcharges to ingredient cost.",
            "action":  "Switch to every-other-day procurement to reduce logistics overhead by ~10%.",
        }

    return [_critical, _warning, _opportunity]


def _render_profile_step_4(current_user: dict, profile: dict | None) -> None:
    """Step 4: AI Risk Profile — insight summary, risk level, tags, alert cards, save."""

    # Step 4a: Gather all session data needed for analysis
    _store_type  = st.session_state.get("profile_store_type", "ghost_kitchen")
    _seat_range  = st.session_state.get("profile_seat_range", "0")
    _food_types  = st.session_state.get("profile_food_types", [])
    _channels    = st.session_state.get("profile_channels") or {}
    _name        = st.session_state.get("profile_restaurant_name", "")

    # Step 4b: Compute margin preview (same formula as Step 3)
    _preview = _compute_blended_margin_preview(
        channels   = _channels,
        food_types = _food_types,
        store_type = _store_type,
        seat_range = _seat_range,
    )
    _nm = _preview["net_margin_pct"]

    # Step 4c: Derive AI outputs from profile data
    _summary      = _build_ai_profile_summary(_store_type, _food_types, _channels)
    _fuel_insight = _build_fuel_insight(_food_types, _nm, _channels)
    _risk         = _derive_risk_level(_nm)
    _tags         = _derive_capability_tags(_food_types, _channels)
    _alerts       = _generate_alert_cards(_nm, _channels, _food_types, _store_type)

    # ── Section A: Header + AI summary card ───────────────────────────────────
    st.subheader("AI Risk Profile")
    st.caption("Generated from your store setup, food types, and revenue channel mix.")

    with st.container(border=True):
        _left, _right = st.columns([3, 1])

        with _left:
            # Step 4d: Restaurant name + AI profile summary line
            st.markdown(
                f'<div style="font-weight:750;font-size:1.05rem;margin-bottom:0.25rem;">'
                f'{escape(_name) if _name else "Your Restaurant"}</div>'
                f'<div style="color:var(--ffia-text-muted);font-size:0.9rem;">{escape(_summary)}</div>',
                unsafe_allow_html=True,
            )

            # Step 4d-insight: Fuel sensitivity insight line
            st.markdown(
                f'<div style="margin-top:0.6rem;padding:0.35rem 0.7rem;border-radius:10px;'
                f'background:rgba(89,135,201,0.07);border:1px solid rgba(89,135,201,0.22);'
                f'font-size:0.78rem;color:#4a6fa5;line-height:1.45;">'
                f'💡 {escape(_fuel_insight)}</div>',
                unsafe_allow_html=True,
            )

            # Step 4e: Capability tags
            if _tags:
                _tag_html = "".join(
                    f'<span style="display:inline-flex;align-items:center;margin:0.45rem 0.35rem 0 0;'
                    f'padding:0.22rem 0.65rem;border-radius:999px;font-size:0.75rem;font-weight:700;'
                    f'color:{c};background:{bg};border:1px solid {bd};">{label}</span>'
                    for label, c, bg, bd in _tags
                )
                st.markdown(
                    f'<div style="margin-top:0.6rem;">{_tag_html}</div>',
                    unsafe_allow_html=True,
                )

        with _right:
            # Step 4f: Risk level badge
            st.markdown(
                f'<div style="display:flex;flex-direction:column;align-items:center;'
                f'justify-content:center;height:100%;gap:0.3rem;">'
                f'<div style="padding:0.5rem 1rem;border-radius:16px;text-align:center;'
                f'background:{_risk["bg"]};border:1px solid {_risk["bd"]};">'
                f'<div style="font-size:1.3rem;font-weight:800;color:{_risk["color"]};">'
                f'{_risk["icon"]}</div>'
                f'<div style="font-size:0.72rem;font-weight:700;color:{_risk["color"]};'
                f'text-transform:uppercase;letter-spacing:0.06em;">{_risk["label"]}</div>'
                f'<div style="font-size:0.68rem;color:var(--ffia-text-muted);margin-top:0.15rem;">'
                f'Est. {_nm:.1f}% margin</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    # ── Section B: Alert cards ─────────────────────────────────────────────────
    st.write("")
    _render_section_header(
        "Risk & Opportunity Alerts",
        "FFIA identified these based on your profile. Review and approve to save.",
    )

    # Step 4g-styles: Visual hierarchy — critical is dominant, opportunity is lighter.
    # border-width and title font-size reinforce the severity signal.
    _ALERT_STYLES = {
        "critical":    ("risk",  "✕ Critical",   "#c16f6f", "2px",  "1.02rem"),
        "warning":     ("warn",  "⚠ Warning",    "#c28747", "1.5px","0.95rem"),
        "opportunity": ("ok",    "✓ Opportunity", "#3d9068", "1px",  "0.88rem"),
    }

    _ac1, _ac2, _ac3 = st.columns(3)
    for _col, _alert in zip((_ac1, _ac2, _ac3), _alerts):
        _css_mod, _type_label, _type_color, _border_w, _title_fs = _ALERT_STYLES[_alert["type"]]
        with _col:
            st.markdown(
                f'<div class="decision-card {_css_mod}" style="height:100%;border-width:{_border_w};">'
                f'<div class="dc-label" style="color:{_type_color};">{_type_label}</div>'
                f'<div style="font-weight:700;font-size:{_title_fs};margin-bottom:0.7rem;'
                f'line-height:1.3;color:var(--ffia-text);">{escape(_alert["title"])}</div>'
                f'<div style="font-size:0.82rem;margin-bottom:0.4rem;">'
                f'<strong>Problem:</strong> {escape(_alert["problem"])}</div>'
                f'<div style="font-size:0.8rem;color:var(--ffia-text-muted);margin-bottom:0.4rem;">'
                f'<strong>Why:</strong> {escape(_alert["reason"])}</div>'
                f'<div style="font-size:0.8rem;">'
                f'<strong>Action:</strong> {escape(_alert["action"])}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Section C: Action buttons + navigation ─────────────────────────────────
    st.write("")

    _can_save = bool(_name.strip() and _food_types)
    if not _can_save:
        st.warning("Some required fields are missing — please go back and complete Steps 1 and 2.")

    _col_back, _col_ignore, _col_spacer, _col_approve = st.columns([1, 1, 2, 2])
    with _col_back:
        if st.button("← Back", key="step4_back"):
            st.session_state["profile_step"] = 3
            st.rerun()
    with _col_ignore:
        if st.button("Ignore", key="step4_ignore"):
            # Discard stepper without saving — go to dashboard
            _clear_profile_stepper_state()
            st.session_state["page"] = "dashboard"
            st.rerun()
    with _col_approve:
        if st.button(
            "Apply optimization plan →",
            type="primary",
            key="step4_approve",
            disabled=not _can_save,
            use_container_width=True,
        ):
            # Step 4g: Resolve DB defaults for fields not collected in this stepper
            _existing_btype    = (profile.get("business_type") or "restaurant") if profile else "restaurant"
            _existing_currency = (profile.get("currency") or "THB") if profile else "THB"
            _existing_target   = float(profile.get("target_margin_pct") or 30.0) if profile else 30.0
            _existing_warning  = float(profile.get("warning_margin_pct") or 25.0) if profile else 25.0
            _existing_risk     = float(profile.get("risk_margin_pct") or 20.0) if profile else 20.0

            # Step 4h: Persist to DB using existing upsert helper
            try:
                upsert_restaurant_profile(
                    user_id=current_user["user_id"],
                    restaurant_name=_name,
                    business_type=_existing_btype,
                    food_types=_food_types,
                    store_type=_store_type,
                    seat_range=_seat_range,
                    currency=_existing_currency,
                    target_margin_pct=_existing_target,
                    warning_margin_pct=_existing_warning,
                    risk_margin_pct=_existing_risk,
                )
                # Step 4h2: Persist channel mix — write Step 3 selections to restaurant_channel_mix
                _channels_to_save = st.session_state.get("profile_channels") or {}
                if _channels_to_save:
                    upsert_channel_mix(
                        user_id=current_user["user_id"],
                        channels=_channels_to_save,
                    )
                # Step 4i: Clear stepper state, signal success, rerun to reset
                _clear_profile_stepper_state()
                st.session_state["profile_save_success"] = True
                st.rerun()
            except Exception:
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
        # Step 4c-guard: Ensure seat_range loaded from DB is valid for the saved store_type.
        # Fixes corrupted profiles (e.g. ghost_kitchen + seat_range="1_10") before Step 2 renders.
        _SEAT_VALID_FOR_STORE = {
            "ghost_kitchen":   ["0"],
            "hybrid_small":    ["1_10"],
            "full_restaurant": ["11_30", "31_plus"],
        }
        _init_store = st.session_state.get("profile_store_type", "ghost_kitchen")
        _init_seat  = st.session_state.get("profile_seat_range", "0")
        if _init_seat not in _SEAT_VALID_FOR_STORE.get(_init_store, ["0"]):
            st.session_state["profile_seat_range"] = _SEAT_VALID_FOR_STORE.get(_init_store, ["0"])[0]

        # profile_channels is populated when the user completes Step 3.
        # No DB field exists yet — session-only until a future schema extension.
        if "profile_channels" not in st.session_state:
            st.session_state["profile_channels"] = {}

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

@st.cache_data(ttl=300)
def _get_cached_diesel_price() -> dict:
    """Fetch diesel price from Bangchak API; cached for 5 minutes across all sessions."""
    try:
        from agent.tools.oil_price_tool import get_oil_price_from_bangchak  # noqa: PLC0415
        return get_oil_price_from_bangchak("hi diesel s")
    except Exception as _e:
        return {"error": str(_e)}


@st.cache_data(ttl=300)
def _get_cached_item_count(user_id: str) -> int | None:
    """Count invoice line items; cached per user for 5 minutes."""
    try:
        return count_invoice_items(user_id)
    except Exception:
        return None


# Step 7a: Render AI answer as a structured insight panel.
# Profile/risk analysis answers → 4-section visual layout (hero + sections).
# All other answers (oil price, invoice queries, etc.) → fallback flat card.
def _render_ai_answer(reply: str, response_language: str | None = None) -> None:
    """Render FFIA agent answer: structured insight card or flat fallback."""

    _lang = response_language if response_language in {"en", "th"} else (
        "th" if re.search(r"[ก-๙]", reply or "") else "en"
    )
    _labels = {
        "main_risk": "ความเสี่ยงหลัก" if _lang == "th" else "Main Risk",
        "why": "ทำไมถึงเสี่ยง" if _lang == "th" else "Why This Is Risky",
        "evidence": "หลักฐานจากข้อมูลของคุณ" if _lang == "th" else "Evidence From Your Data",
        "actions": "แนวทางแก้ไข" if _lang == "th" else "Recommended Actions",
    }

    # ── Inline helpers ──────────────────────────────────────────────────────
    def _esc(t: str) -> str:
        return escape(t)

    def _inline(t: str) -> str:
        """Convert **bold** and `code` in already HTML-escaped text."""
        t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
        t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
        return t

    def _p(t: str) -> str:
        return _inline(_esc(t))

    def _is_meta(s: str) -> bool:
        sl = s.lower()
        return sl.startswith('data from:') or sl.startswith('ข้อมูลจาก:')

    def _strip_bullet(s: str) -> str:
        return s[2:] if (s.startswith('- ') or s.startswith('* ')) else s

    def _is_internal_scaffold_label(h: str | None) -> bool:
        if not h:
            return False
        _norm = re.sub(r'[^a-z0-9 ]+', '', h.lower()).strip()
        return _norm in {"verdict", "key number", "what to do"}

    # ── Parse ## headings into sections ────────────────────────────────────
    sections: list[tuple[str | None, list[str]]] = []
    cur_h: str | None = None
    cur_ls: list[str] = []

    for raw in reply.split('\n'):
        line = raw.rstrip()
        if line.startswith('## '):
            sections.append((cur_h, cur_ls))
            cur_h = line[3:].strip()
            cur_ls = []
        else:
            cur_ls.append(line)
    sections.append((cur_h, cur_ls))

    # ── Classify each section ───────────────────────────────────────────────
    def _classify(h: str | None) -> str:
        if not h:
            return 'preamble'
        hl = h.lower()
        if any(k in hl for k in ('เสี่ยงหลัก', 'main risk', 'biggest')):
            return 'main_risk'
        if any(k in hl for k in ('ทำไม', 'why', 'risky')):
            return 'why'
        if any(k in hl for k in ('หลักฐาน', 'evidence')):
            return 'evidence'
        if any(k in hl for k in ('แนวทาง', 'action', 'recommend')):
            return 'actions'
        return 'generic'

    typed = [(h, ls, _classify(h)) for h, ls in sections]
    types_found = {t for _, _, t in typed}
    is_structured = bool(types_found & {'main_risk', 'why', 'actions'})

    # ── FALLBACK: flat card for non-profile answers ─────────────────────────
    if not is_structured:
        parts = ['<div class="ffia-answer-card">']
        in_ul = False
        for heading, ls, _ in typed:
            if heading and not _is_internal_scaffold_label(heading):
                if in_ul:
                    parts.append('</ul>')
                    in_ul = False
                parts.append(f'<div class="ffia-h">{_p(heading)}</div>')
            for line in ls:
                s = line.strip()
                if not s:
                    if in_ul:
                        parts.append('</ul>')
                        in_ul = False
                    continue
                if _is_meta(s):
                    if in_ul:
                        parts.append('</ul>')
                        in_ul = False
                    parts.append(f'<div class="ffia-meta">{_esc(s)}</div>')
                elif s.startswith('- ') or s.startswith('* '):
                    if not in_ul:
                        parts.append('<ul class="ffia-ul">')
                        in_ul = True
                    parts.append(f'<li class="ffia-li">{_p(s[2:])}</li>')
                else:
                    if in_ul:
                        parts.append('</ul>')
                        in_ul = False
                    parts.append(f'<p class="ffia-p">{_p(s)}</p>')
        if in_ul:
            parts.append('</ul>')
        parts.append('</div>')
        st.markdown('\n'.join(parts), unsafe_allow_html=True)
        return

    # ── STRUCTURED layout: profile / risk analysis answers ─────────────────
    html: list[str] = ['<div class="ffia-answer-card">']
    meta_line = ''

    # Step A: pre-process — strip blank lines and extract meta from all sections
    processed: list[tuple[str | None, list[str], str]] = []
    for heading, lines, stype in typed:
        content = []
        for raw_l in lines:
            s = raw_l.strip()
            if not s:
                continue
            if _is_meta(s):
                if not meta_line:
                    meta_line = s
            else:
                content.append(s)
        processed.append((heading, content, stype))

    # Step B: sort into original display order
    # Main Risk → Why → Evidence → Recommended Actions → generic → preamble
    _DISPLAY_ORDER = {'main_risk': 0, 'why': 1, 'evidence': 2, 'actions': 3, 'generic': 4, 'preamble': 5}
    processed.sort(key=lambda x: _DISPLAY_ORDER.get(x[2], 6))

    for heading, content, stype in processed:
        if not content and stype not in ('main_risk',):
            continue

        if stype == 'main_risk':
            # Join all content lines into the hero body
            body_text = ' '.join(content)
            html.append(
                f'<div class="ffia-risk-hero">'
                f'<div class="ffia-risk-hero-eyebrow">⚠ {_labels["main_risk"]}</div>'
                f'<p class="ffia-risk-hero-body">{_p(body_text)}</p>'
                f'</div>'
            )

        elif stype == 'why':
            items = ''.join(
                f'<li class="ffia-bitem">{_p(_strip_bullet(s))}</li>'
                for s in content
            )
            title = _esc(heading) if (heading and not _is_internal_scaffold_label(heading)) else _labels["why"]
            html.append(
                f'<div class="ffia-section">'
                f'<div class="ffia-section-head"><span class="ffia-section-title">{title}</span></div>'
                f'<ul class="ffia-blist">{items}</ul>'
                f'</div>'
            )

        elif stype == 'evidence':
            # Render as annotated bullets: "Label: value" → bold inline label + text
            items = []
            for s in content:
                s = _strip_bullet(s)
                if ':' in s:
                    label, _, value = s.partition(':')
                    items.append(
                        f'<li class="ffia-bitem">'
                        f'<span class="ffia-ev-inline">{_esc(label.strip())}:</span>'
                        f' {_p(value.strip())}'
                        f'</li>'
                    )
                else:
                    items.append(f'<li class="ffia-bitem">{_p(s)}</li>')
            title = _esc(heading) if (heading and not _is_internal_scaffold_label(heading)) else _labels["evidence"]
            html.append(
                f'<div class="ffia-section">'
                f'<div class="ffia-section-head"><span class="ffia-section-title">{title}</span></div>'
                f'<ul class="ffia-blist">{"".join(items)}</ul>'
                f'</div>'
            )

        elif stype == 'actions':
            items = ''.join(
                f'<li class="ffia-aitem">{_p(_strip_bullet(s))}</li>'
                for s in content
            )
            title = _esc(heading) if (heading and not _is_internal_scaffold_label(heading)) else _labels["actions"]
            html.append(
                f'<div class="ffia-section ffia-section--actions">'
                f'<div class="ffia-section-head"><span class="ffia-section-title">{title}</span></div>'
                f'<ol class="ffia-alist">{items}</ol>'
                f'</div>'
            )

        elif stype == 'generic' and content:
            items = ''.join(
                f'<li class="ffia-bitem">{_p(_strip_bullet(s))}</li>'
                for s in content
            )
            title = _esc(heading) if (heading and not _is_internal_scaffold_label(heading)) else ''
            html.append(
                f'<div class="ffia-section">'
                + (f'<div class="ffia-section-head"><span class="ffia-section-title">{title}</span></div>' if title else '')
                + f'<ul class="ffia-blist">{items}</ul>'
                f'</div>'
            )

        elif stype == 'preamble' and content:
            for s in content:
                html.append(f'<p class="ffia-p">{_p(s)}</p>')

    if meta_line:
        html.append(f'<div class="ffia-meta">{_esc(meta_line)}</div>')

    html.append('</div>')
    st.markdown('\n'.join(html), unsafe_allow_html=True)


# Step 7b: Helper — run agent and append result to session messages
def _run_agent_turn(prompt: str, current_user: dict, msg_container) -> None:
    """Append user msg, run agent, append assistant msg.
    Does NOT render st.chat_message() — all chat bubble rendering lives in the message loop.
    """
    # Step 7b-1: Append user message — the loop renders it on the next rerun
    _response_language = "th" if re.search(r"[ก-๙]", prompt or "") else "en"
    _agent_prompt = (
        "Language lock: respond entirely in English. Determine output language from the latest user message only. "
        "Ignore language in examples, tool observations, database values, prior turns, and prompt headers.\n\n"
        f"User question:\n{prompt}"
        if _response_language == "en"
        else
        "Language lock: ตอบเป็นภาษาไทยทั้งหมด โดยกำหนดภาษาจากข้อความล่าสุดของผู้ใช้เท่านั้น "
        "ให้เพิกเฉยต่อภาษาจากตัวอย่าง ผลลัพธ์เครื่องมือ ค่าจากฐานข้อมูล บทสนทนาก่อนหน้า และหัวข้อในพรอมป์ต์\n\n"
        f"คำถามผู้ใช้:\n{prompt}"
    )
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Step 7b-2: Build history (exclude the just-appended user message)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
    ]
    _language_guard = (
        "Language lock: respond entirely in English. Determine language from the latest user message only. "
        "Ignore language in examples, tool observations, database values, prior turns, and prompt headers."
        if _response_language == "en"
        else
        "Language lock: ตอบเป็นภาษาไทยทั้งหมด โดยกำหนดภาษาจากข้อความล่าสุดของผู้ใช้เท่านั้น "
        "ให้เพิกเฉยต่อภาษาจากตัวอย่าง ผลลัพธ์เครื่องมือ ค่าจากฐานข้อมูล บทสนทนาก่อนหน้า และหัวข้อในพรอมป์ต์"
    )
    history.insert(0, {"role": "system", "content": _language_guard})

    # Step 7b-3: Run agent with a temporary staged status block inside the chat workspace.
    # The final answer still renders only through the normal rerun-driven message loop.
    _loading_steps = (
        "Checking your data...",
        "Calculating cost impact...",
        "Preparing recommendation...",
    )
    _step_interval_sec = 0.9
    _poll_interval_sec = 0.1
    _run_agent = _get_run_agent()

    with msg_container:
        with st.status(_loading_steps[0], expanded=True) as _status:
            _status.write(_loading_steps[0])
            _shown_steps = 1
            _next_step_at = time.monotonic() + _step_interval_sec

            with ThreadPoolExecutor(max_workers=1) as _executor:
                _future = _executor.submit(
                    _run_agent,
                    _agent_prompt,
                    history,
                    current_user_id=current_user["user_id"],
                )

                while not _future.done():
                    _now = time.monotonic()
                    if _shown_steps < len(_loading_steps) and _now >= _next_step_at:
                        _step_text = _loading_steps[_shown_steps]
                        _status.update(label=_step_text, state="running")
                        _status.write(_step_text)
                        _shown_steps += 1
                        _next_step_at = _now + _step_interval_sec
                    time.sleep(_poll_interval_sec)

                result = _future.result()

    # Step 7b-4: Store steps alongside the reply so the loop can render the trace expander
    steps = result.get("intermediate_steps", [])
    reply = result.get("output", "Sorry, I could not produce an answer.")
    import logging as _logging
    _logging.getLogger(__name__).debug("[UI STORED ANSWER]\n%s", reply)
    st.session_state.messages.append({
        "role": "assistant",
        "content": reply,
        "steps": steps,
        "response_language": _response_language,
    })


# Step 7b: Dashboard viz page — stub for dev to build out
def _render_dashboard_viz_page(current_user: dict):
    """Render the Dashboard viz page: cost overview and performance metrics."""
    st.title("Dashboard")
    st.caption("Cost overview and performance metrics for your restaurant.")
    # TODO: Junior dev builds below this line
    st.info("Charts coming soon.")


# Step 8: Dashboard page renderer — decision cockpit layout
def _render_dashboard_page(current_user: dict):
    """Render the main Dashboard: header, decision cards, and quick actions."""

    # Step 8-pre: One-time migration — if restaurant_channel_mix has no rows for this user
    # but session_state["profile_channels"] exists, persist it silently to the DB now.
    _uid = current_user["user_id"]
    if st.session_state.get("profile_channels"):
        try:
            with get_connection(_uid) as _mig_conn:
                with _mig_conn.cursor() as _mig_cur:
                    _mig_cur.execute(
                        "SELECT COUNT(*) FROM restaurant_channel_mix WHERE user_id = %s",
                        (_uid,),
                    )
                    if _mig_cur.fetchone()[0] == 0:
                        upsert_channel_mix(_uid, st.session_state["profile_channels"])
        except Exception:
            pass  # Migration is best-effort — never block the dashboard

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

    # ── Section A2: Onboarding — additive "Get started" guide for first-time users ──
    with st.container():
        st.markdown("""
<div class="decision-card" style="margin-bottom:1.2rem;">
  <div class="dc-label">🚀 Get started with FFIA</div>
  <div class="dc-sub" style="margin-bottom:1rem;">
    Follow these steps to set up your restaurant and get accurate insights.
  </div>
</div>
""", unsafe_allow_html=True)

        _ob1, _ob2, _ob3 = st.columns(3)
        with _ob1:
            st.markdown("""
<div class="decision-card">
  <div class="dc-label">① Set up your Business Profile</div>
  <div class="dc-sub">Tell FFIA about your restaurant type and operations.</div>
</div>
""", unsafe_allow_html=True)
            if st.button("Go to Business Profile", key="onboard_profile", use_container_width=True):
                st.session_state["page"] = "profile_settings"
                st.rerun()

        with _ob2:
            st.markdown("""
<div class="decision-card">
  <div class="dc-label">② Upload your first invoice</div>
  <div class="dc-sub">Add real cost data to improve analysis accuracy.</div>
</div>
""", unsafe_allow_html=True)
            if st.button("Upload Invoice", key="onboard_upload", use_container_width=True):
                st.session_state["page"] = "upload"
                st.rerun()

        with _ob3:
            st.markdown("""
<div class="decision-card">
  <div class="dc-label">③ Ask FFIA for insights</div>
  <div class="dc-sub">Get pricing, margin, and fuel impact recommendations.</div>
</div>
""", unsafe_allow_html=True)
            if st.button("Ask FFIA", key="onboard_ai", use_container_width=True):
                st.session_state["page"] = "ai_assistant"
                st.rerun()

    st.write("")

    # ── Section B: Decision Cards ──────────────────────────────────────────────
    _dc1, _dc2, _dc3 = st.columns(3)

    # Card 1 — Diesel Price
    if _diesel_ok:
        _price_val = f"{_diesel['price_per_liter']:.2f} ฿/L"
        _effective_raw = str(_diesel.get("updated_at") or "N/A")
        _effective_disp = _effective_raw
        _effective_date = None
        _as_of_date = None
        try:
            _effective_date = datetime.strptime(_effective_raw, "%d/%m/%Y").date()
            _effective_disp = _effective_date.strftime("%d %b %Y")
        except (TypeError, ValueError):
            pass

        _as_of_raw = str(_diesel.get("data_as_of") or "")
        try:
            _as_of_date = datetime.strptime(_as_of_raw, "%d/%m/%Y").date()
        except (TypeError, ValueError):
            pass

        if _effective_raw == "N/A":
            _base_sub = "Effective date unavailable"
        else:
            _base_sub = f"Effective since {escape(_effective_disp)}"

        _price_sub = f"{_base_sub}<br>Last checked: Today"
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
  <div class="dc-label">Hi-Diesel Price Today</div>
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
    _quick_actions_slot = st.empty()
    with _quick_actions_slot.container(border=True):
        _render_section_header(
            "Check your costs and profit",
            "Use a guided shortcut to start a common workflow, then continue the analysis in FFIA.",
        )

        _QUICK_ACTIONS = [
            ("⛽ Today's fuel price",        "What is today's diesel price?"),
            ("📉 Low-profit menu items",      "Which of my menu items have the lowest margin?"),
            ("📊 Impact of +5฿ fuel",         "What happens to my costs if diesel increases by 5 baht?"),
            ("🧾 Review my costs",            "Summarize my invoice costs this month"),
            ("💰 What should I reprice?",     "Suggest menu repricing based on current fuel costs"),
            ("📦 Where is profit lost?",      "Show me a margin breakdown for my menu items"),
        ]

        _row1_cols = st.columns(3)
        _row2_cols = st.columns(3)
        for _col_idx, (_label, _prompt) in enumerate(_QUICK_ACTIONS):
            _col = _row1_cols[_col_idx] if _col_idx < 3 else _row2_cols[_col_idx - 3]
            with _col:
                st.markdown('<div class="action-card">', unsafe_allow_html=True)
                if st.button(_label, key=f"qa_{_col_idx}", use_container_width=True):
                    st.session_state["pending_prompt"] = _prompt
                    st.session_state["page"] = "ai_assistant"
                    _quick_actions_slot.empty()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)


# Step 8b: AI Assistant page renderer — chat-only workspace
def _render_ai_assistant_page(current_user: dict):
    """Render the dedicated AI Assistant page: shortcuts, chat, and analysis history."""
    _render_page_hero(
        "AI Assistant",
        "Ask FFIA about fuel impact, invoice costs, margin risk, and pricing decisions.",
        eyebrow="AI Assistant",
    )

    # Step A: Initialize chat state before rendering prompt shortcuts/workspace.
    if "messages" not in st.session_state:
        st.session_state.messages = []
    _chat_is_active = bool(st.session_state.messages) or bool(st.session_state.get("pending_prompt"))

    st.write("")
    # Step B: Show the shortcut prompt block only before the chat becomes active.
    # This prevents an extra empty bordered card from appearing when the user
    # arrives here from a Dashboard quick action with a pending prompt.
    if not _chat_is_active:
        with st.container(border=True):
            _render_section_header(
                "Ask FFIA Agent",
                "Get cost impact analysis, pricing suggestions, and fuel-risk insights in plain language.",
            )

            _CHIPS = [
                ("⛽ What's today's fuel price?",          "What is today's diesel price?"),
                ("📉 Which items are losing money?",        "Which of my menu items have the highest cost risk?"),
                ("🔺 How will fuel increase affect profit?","What happens to my costs if diesel increases by 5 baht?"),
                ("🧾 Show my latest costs",                 "Summarize my invoice costs this month"),
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

    # Step D3: Render the chat container only when the chat is active so the
    # dashboard opens at the top with no large empty workspace reserving space.
    # pending_prompt counts as active, which keeps the spinner inside the same
    # bordered chat workspace during loading.
    if _chat_is_active:
        _msg_container = st.container(height=640, border=True)
        with _msg_container:
            for _msg in st.session_state.messages:
                with st.chat_message(_msg["role"]):
                    if _msg["role"] == "assistant":
                        _steps = _msg.get("steps", [])
                        if _steps:
                            with st.expander("Agent Reasoning Trace (click to expand)", expanded=False):
                                for _i, (_tool_name, _obs) in enumerate(_steps, 1):
                                    st.markdown(f"**Step {_i} — Action:** `{_tool_name}`")
                                    if _obs:
                                        st.markdown(f"**Observation:** {str(_obs)[:500]}")
                                    st.divider()
                                st.markdown(f"**Final Answer:** {_msg['content']}")
                        _render_ai_answer(_msg["content"], _msg.get("response_language"))
                    else:
                        st.markdown(_msg["content"])
    else:
        _msg_container = st.container()

    # Step D4: Process pending prompt (from quick actions / chips)
    _pending = st.session_state.pop("pending_prompt", None)
    if _pending:
        _run_agent_turn(_pending, current_user, _msg_container)
        st.rerun()

    # Step D5: Chat input
    _user_input = st.chat_input("Ask about diesel price, invoice costs, margin risk...")
    if _user_input:
        _run_agent_turn(_user_input, current_user, _msg_container)
        st.rerun()

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
_page_root = st.empty()
with _page_root.container():
    if _active_page == "upload":
        _render_upload_page(_current_user)
    elif _active_page == "profile_settings":
        _render_profile_settings_page(_current_user)
    elif _active_page == "ai_assistant":
        _render_ai_assistant_page(_current_user)
    elif _active_page == "dashboard_viz":
        _render_dashboard_viz_page(_current_user)
    else:
        _render_dashboard_page(_current_user)
