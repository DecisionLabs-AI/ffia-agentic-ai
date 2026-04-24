import base64
from collections.abc import Callable
from pathlib import Path

import streamlit as st


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


def _render_sidebar(
    current_user: dict,
    active_page: str = "dashboard",
    clear_user_session: Callable[[], None] | None = None,
) -> None:
    """Render the FFIA sidebar: brand, grouped nav sections, and account.

    active_page is the single source of truth for which nav item appears highlighted.
    It is passed explicitly by the call site — the sidebar function never reads page
    state itself.  Each nav button receives is_active=(active_page == "<key>"), which
    sets the .sb-nav-marker.is-active class, which the CSS :has() rule picks up.
    """
    with st.sidebar:
        # Step 5a: Load logo (base64) — fall back to "F" badge if file missing
        _logo_path = Path(__file__).resolve().parent.parent / "assets" / "ffia_logo_design.png"
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

        if _render_sidebar_nav_button(
            "Business Setup",
            key="nav_profile",
            is_active=active_page == "profile_settings",
        ):
            st.session_state["page"] = "profile_settings"
            st.rerun()

        if _render_sidebar_nav_button("Dashboard", key="nav_dashboard_viz", is_active=active_page == "dashboard_viz"):
            st.session_state["page"] = "dashboard_viz"
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
            if clear_user_session is not None:
                clear_user_session()
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
