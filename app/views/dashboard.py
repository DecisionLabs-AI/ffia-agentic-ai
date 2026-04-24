from datetime import datetime
from html import escape

import streamlit as st

from app.components.layout import _render_page_hero, _render_section_header
from data.db import count_invoice_items, get_connection, upsert_channel_mix


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
  <div class="dc-label">① Complete your Business Setup</div>
  <div class="dc-sub">Tell FFIA about your restaurant type and operations.</div>
</div>
""", unsafe_allow_html=True)
            if st.button("Go to Business Setup", key="onboard_profile", use_container_width=True):
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
                st.session_state["page"] = "profile_settings"
                st.session_state["setup_step"] = 2
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
