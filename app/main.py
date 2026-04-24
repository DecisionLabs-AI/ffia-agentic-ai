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
from app.styles.main_css import _get_main_css
from app.components.layout import _render_page_hero, _render_section_header
from app.components.sidebar import _render_sidebar_nav_button, _render_sidebar
from app.views.dashboard import (
    _get_cached_diesel_price,
    _get_cached_item_count,
    _render_dashboard_page,
    _render_dashboard_viz_page,
)
from app.views.chat import _render_ai_assistant_page
from app.views.upload import _render_upload_invoice_section, _render_upload_page
from app.views.profile import _render_profile_settings_page
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

    _assets_dir = Path(__file__).parent / "assets"

    def _load_image_data_uri(asset_path: Path) -> str | None:
        """Return a base64 data URI for inline login visuals."""
        try:
            _encoded = base64.b64encode(asset_path.read_bytes()).decode("utf-8")
        except OSError:
            return None
        _ext = asset_path.suffix.lower().lstrip(".") or "png"
        return f"data:image/{_ext};base64,{_encoded}"

    _home_screen_data_uri = _load_image_data_uri(_assets_dir / "home_screen.png")

    st.markdown(
        """
<style>
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background: #ffffff !important;
}

.st-key-ffia_login_screen {
    --ffia-login-desktop-height: clamp(640px, 72vh, 700px);
    margin-top: 0.35rem;
}

.st-key-ffia_login_screen [data-testid="stHorizontalBlock"] {
    align-items: stretch;
    gap: clamp(1rem, 2.5vw, 1.75rem);
}

.st-key-ffia_login_visual_shell .ffia-login-visual {
    position: relative;
    min-height: var(--ffia-login-desktop-height);
    height: var(--ffia-login-desktop-height);
    border-radius: 24px;
    overflow: hidden;
    background: #f4efe9;
    box-shadow: 0 20px 46px -34px rgba(42, 31, 24, 0.42);
}

.st-key-ffia_login_visual_shell .ffia-login-visual__img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
}

.st-key-ffia_login_visual_shell .ffia-login-visual::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: 1;
    background: linear-gradient(180deg, rgba(20, 14, 10, 0.08) 12%, rgba(20, 14, 10, 0.64) 100%);
}

.st-key-ffia_login_visual_shell .ffia-login-visual__overlay {
    position: absolute;
    left: clamp(1rem, 2.3vw, 1.85rem);
    right: clamp(1rem, 2.3vw, 1.85rem);
    bottom: clamp(1.15rem, 2.3vw, 1.85rem);
    z-index: 2;
    color: #ffffff;
}

.st-key-ffia_login_visual_shell .ffia-login-visual__badge {
    display: inline-block;
    padding: 0.28rem 0.7rem;
    margin-bottom: 0.7rem;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.34);
    background: rgba(234, 109, 47, 0.92);
    color: #ffffff;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.st-key-ffia_login_visual_shell .ffia-login-visual__overlay h2 {
    margin: 0;
    color: #ffffff;
    font-size: clamp(1.2rem, 2vw, 1.72rem);
    line-height: 1.14;
    letter-spacing: 0.01em;
    max-width: 24ch;
}

.st-key-ffia_login_visual_shell .ffia-login-visual__overlay p {
    margin: 0.62rem 0 0;
    color: rgba(255, 255, 255, 0.94);
    font-size: 0.93rem;
    line-height: 1.5;
    max-width: 43ch;
}

.st-key-ffia_login_right_align {
    min-height: var(--ffia-login-desktop-height);
    height: var(--ffia-login-desktop-height);
    display: flex;
    align-items: center;
    justify-content: center;
}

.st-key-ffia_login_right_align > div[data-testid="stVerticalBlock"] {
    width: 100%;
    min-height: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}

.st-key-ffia_login_right_align > div[data-testid="stVerticalBlock"] > div {
    width: 100%;
}

.st-key-ffia_login_panel_shell {
    width: 100%;
}

.st-key-ffia_login_panel_shell [data-testid="stVerticalBlockBorderWrapper"] {
    min-height: auto;
    height: auto;
    border-radius: 24px !important;
    border: none !important;
    background: #ffffff !important;
    box-shadow: none !important;
    padding: clamp(1.15rem, 2.2vw, 1.9rem) !important;
}

.ffia-login-panel-copy {
    margin-bottom: 1rem;
}

.ffia-login-brand {
    margin: 0 0 0.5rem;
    color: #E8760A;
    font-size: 2.8rem;
    font-weight: 900;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.ffia-login-panel-copy h1 {
    margin: 0;
    color: #211711;
    font-size: clamp(1.95rem, 2.2vw, 2.4rem);
    line-height: 1.06;
    letter-spacing: -0.02em;
}

.ffia-login-panel-copy p {
    margin: 0.62rem 0 0;
    color: #7a6355;
    font-size: 0.95rem;
    line-height: 1.5;
    max-width: 32ch;
}

.st-key-ffia_login_panel_shell [data-testid="stForm"] {
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
}

.st-key-ffia_login_panel_shell [data-testid="stTextInput"] label p {
    color: #59493f !important;
    font-weight: 600 !important;
}

.st-key-ffia_login_panel_shell div[data-baseweb="input"] > div {
    border-radius: 12px !important;
    border: 1px solid #e8ded6 !important;
    background: #ffffff !important;
}

.st-key-ffia_login_panel_shell div[data-baseweb="input"] > div:hover {
    border-color: #d9c1af !important;
}

.st-key-ffia_login_panel_shell div[data-baseweb="input"] > div:focus-within {
    border-color: #ea6d2f !important;
    box-shadow: 0 0 0 3px rgba(234, 109, 47, 0.16) !important;
}

.st-key-ffia_login_panel_shell div[data-baseweb="input"] input {
    color: #2a1d16 !important;
}

.st-key-ffia_login_panel_shell [data-testid="stFormSubmitButton"] > button,
.st-key-ffia_login_panel_shell [data-testid="stFormSubmitButton"] > button[kind="primary"] {
    min-height: 50px !important;
    border: 1px solid #ea6d2f !important;
    border-radius: 12px !important;
    background: #ea6d2f !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    box-shadow: 0 12px 24px -18px rgba(234, 109, 47, 0.72) !important;
}

.st-key-ffia_login_panel_shell [data-testid="stFormSubmitButton"] > button p {
    color: #ffffff !important;
}

.st-key-ffia_login_panel_shell [data-testid="stFormSubmitButton"] > button:hover,
.st-key-ffia_login_panel_shell [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
    border-color: #d85b1f !important;
    background: #d85b1f !important;
    color: #ffffff !important;
    box-shadow: 0 14px 26px -18px rgba(216, 91, 31, 0.72) !important;
}

.st-key-ffia_login_panel_shell [data-testid="stFormSubmitButton"] > button:focus-visible {
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(234, 109, 47, 0.2) !important;
}

.st-key-ffia_login_panel_shell [data-testid="stAlert"] {
    border-radius: 14px !important;
    border: 1px solid #f0d8c8 !important;
    background: #fff9f4 !important;
}

@media (max-width: 1100px) {
    .st-key-ffia_login_screen {
        --ffia-login-desktop-height: 640px;
    }
}

@media (max-width: 860px) {
    .st-key-ffia_login_screen [data-testid="stHorizontalBlock"] {
        align-items: stretch;
    }

    .st-key-ffia_login_visual_shell .ffia-login-visual {
        min-height: 250px;
        max-height: 300px;
    }

    .st-key-ffia_login_right_align {
        min-height: auto;
        height: auto;
        display: block;
    }

    .st-key-ffia_login_right_align > div[data-testid="stVerticalBlock"] {
        min-height: auto;
        height: auto;
        display: block;
    }

    .st-key-ffia_login_panel_shell [data-testid="stVerticalBlockBorderWrapper"] {
        min-height: auto;
    }
}
</style>
""",
        unsafe_allow_html=True,
    )

    with st.container(key="ffia_login_screen"):
        _left_col, _right_col = st.columns([1.2, 1], gap="large")

        with _left_col:
            with st.container(key="ffia_login_visual_shell"):
                _visual_style = (
                    f'<img class="ffia-login-visual__img" src="{_home_screen_data_uri}" alt="FFIA home screen" />'
                    if _home_screen_data_uri else ""
                )
                st.markdown(
                    f"""
<div class="ffia-login-visual">
  {_visual_style}
  <div class="ffia-login-visual__overlay">
    <span class="ffia-login-visual__badge">FFIA</span>
    <h2>SHARPER COST CONTROL FOR MODERN RESTAURANT TEAMS.</h2>
    <p>Track invoices, understand margins, and move faster with decision-grade insights.</p>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )

        with _right_col:
            with st.container(key="ffia_login_right_align"):
                with st.container(key="ffia_login_panel_shell", border=False):
                    st.markdown(
                        """
<div class="ffia-login-panel-copy">
  <p style="font-size:2.8rem;font-weight:900;color:#E8760A;letter-spacing:0.12em;text-transform:uppercase;margin:0 0 0.5rem;">FFIA</p>
  <h1>Sign In</h1>
  <p>Enter your username and password to continue.</p>
</div>
""",
                        unsafe_allow_html=True,
                    )

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
        with _right_col:
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


# Step 3a: CSS — soft premium dashboard theme
st.markdown(_get_main_css(), unsafe_allow_html=True)

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
_render_sidebar(
    _current_user,
    active_page=st.session_state.get("page", "dashboard"),
    clear_user_session=_clear_user_session,
)

# Step 9: Page router — dispatch to correct page based on session state
_active_page = st.session_state.get("page", "dashboard")
_page_root = st.empty()
with _page_root.container():
    if _active_page == "upload":
        _render_upload_page(
            _current_user,
            get_extract_invoice_data=_get_extract_invoice_data,
            get_run_agent=_get_run_agent,
        )
    elif _active_page == "profile_settings":
        _render_profile_settings_page(
            _current_user,
            get_extract_invoice_data=_get_extract_invoice_data,
            get_run_agent=_get_run_agent,
        )
    elif _active_page == "ai_assistant":
        _render_ai_assistant_page(_current_user, get_run_agent=_get_run_agent)
    elif _active_page == "dashboard_viz":
        _render_dashboard_viz_page(_current_user)
    else:
        _render_dashboard_page(_current_user)
