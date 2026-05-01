from datetime import datetime
from html import escape

import streamlit as st

from app.components.layout import _render_page_hero, _render_section_header
from data.db import (
    count_invoice_items,
    fetch_invoices_current_month,
    fetch_latest_restaurant_profile,
    get_connection,
    upsert_channel_mix,
)


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


@st.cache_data(ttl=300)
def _get_cached_monthly_invoices(user_id: str) -> list[dict]:
    """Fetch current-month invoices; cached per user for 5 minutes."""
    try:
        return fetch_invoices_current_month(user_id)
    except Exception:
        return []


@st.cache_data(ttl=300)
def _get_cached_profile(user_id: str) -> dict | None:
    """Fetch restaurant profile; cached per user for 5 minutes."""
    try:
        return fetch_latest_restaurant_profile(user_id)
    except Exception:
        return None


@st.cache_data(ttl=300)
def _get_cached_channel_mix(user_id: str) -> list[dict]:
    """Fetch active channel mix rows; cached per user for 5 minutes."""
    try:
        with get_connection(user_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT platform, revenue_share_pct, platform_fee_pct
                    FROM restaurant_channel_mix
                    WHERE user_id = %s AND is_active = true
                    ORDER BY revenue_share_pct DESC
                    """,
                    (user_id,),
                )
                return [
                    {
                        "platform": row[0],
                        "revenue_share_pct": float(row[1]),
                        "platform_fee_pct": float(row[2]),
                    }
                    for row in cur.fetchall()
                ]
    except Exception:
        return []


@st.cache_data(ttl=300)
def _get_cached_top_items(user_id: str, limit: int = 5) -> list[dict]:
    """Top N invoice items by total spend this calendar month; cached per user for 5 minutes."""
    try:
        with get_connection(user_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        ii.name,
                        SUM(ii.total) AS total_spend,
                        SUM(ii.qty)   AS total_qty
                    FROM invoice_items ii
                    JOIN invoices inv ON ii.invoice_id = inv.id
                    WHERE ii.user_id = %s
                      AND (ii.excluded_from_analysis IS NOT TRUE)
                      AND DATE_TRUNC('month', inv.invoice_date) = DATE_TRUNC('month', CURRENT_DATE)
                    GROUP BY ii.name
                    ORDER BY total_spend DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                return [
                    {
                        "name": row[0],
                        "total_spend": float(row[1]),
                        "total_qty": float(row[2]),
                    }
                    for row in cur.fetchall()
                ]
    except Exception:
        return []


# Step 7c: Label maps used by the Dashboard page
_STORE_TYPE_LABELS = {
    "ghost_kitchen":   "Ghost Kitchen",
    "hybrid_small":    "Hybrid / Small Dine-in",
    "full_restaurant": "Full Restaurant",
}

_FOOD_TYPE_LABELS = {
    "rice_curry":   "ข้าวแกง",
    "noodle":       "ก๋วยเตี๋ยว",
    "porridge":     "โจ๊ก/ข้าวต้ม",
    "chicken_rice": "ข้าวมันไก่",
    "spicy_soup":   "ต้มยำ",
    "stir_fry":     "ผัดกะเพรา",
    "isaan":        "อาหารอีสาน",
    "spicy_salad":  "ยำ",
    "healthy":      "Healthy",
    "vegan":        "Vegan",
    "meal_prep":    "Meal Prep",
}


# Step 7b: Dashboard viz page — KPIs, profile snapshot, channel mix, top spend items
def _render_dashboard_viz_page(current_user: dict):
    """Render the Dashboard page: 4 KPI cards, profile snapshot, channel mix, top spend items."""
    _uid = current_user["user_id"]

    # ── Header ────────────────────────────────────────────────────────────────
    _render_page_hero(
        "Dashboard",
        "Cost overview and performance metrics for your restaurant.",
        eyebrow="Cost Intelligence",
    )

    # Step A1: Fetch all data up front
    _diesel           = _get_cached_diesel_price()
    _item_count       = _get_cached_item_count(_uid)
    _monthly_invoices = _get_cached_monthly_invoices(_uid)
    _profile          = _get_cached_profile(_uid)
    _channel_mix      = _get_cached_channel_mix(_uid)
    _top_items        = _get_cached_top_items(_uid)

    _diesel_ok     = "error" not in _diesel
    _monthly_count = len(_monthly_invoices)
    _monthly_spend = sum(float(inv.get("total_amount", 0)) for inv in _monthly_invoices)
    _latest_vendor = _monthly_invoices[0].get("vendor", "—") if _monthly_invoices else "—"

    # Step A2: Status pills
    _fuel_pill_cls = "status-pill" if _diesel_ok else "status-pill error"
    _fuel_pill_lbl = "Fuel API: Connected" if _diesel_ok else "Fuel API: Unavailable"
    _count_label   = f"{_item_count} items tracked" if _item_count is not None else "No items yet"
    _inv_pill_lbl  = f"{_monthly_count} invoice{'s' if _monthly_count != 1 else ''} this month"
    st.markdown(f"""
<div class="status-pills-row">
  <span class="{_fuel_pill_cls}"><span class="pill-dot"></span>{_fuel_pill_lbl}</span>
  <span class="status-pill info"><span class="pill-dot"></span>{_count_label}</span>
  <span class="status-pill info"><span class="pill-dot"></span>{escape(_inv_pill_lbl)}</span>
</div>
""", unsafe_allow_html=True)

    # ── Section B: 4 KPI Cards ─────────────────────────────────────────────────
    _kpi1, _kpi2, _kpi3, _kpi4 = st.columns(4)

    # KPI 1 — Hi-Diesel Price (real: Bangchak API)
    if _diesel_ok:
        _price_val  = f"{_diesel['price_per_liter']:.2f}"
        _eff_raw    = str(_diesel.get("updated_at") or "N/A")
        _eff_disp   = _eff_raw
        try:
            _eff_disp = datetime.strptime(_eff_raw, "%d/%m/%Y").strftime("%d %b %Y")
        except (TypeError, ValueError):
            pass
        _kpi1_cls   = "decision-card warn"
        _kpi1_sub   = f"Effective {escape(_eff_disp)}"
        _kpi1_hint  = '<span class="dc-hint">฿/L · May affect delivery costs</span>'
    else:
        _price_val  = "—"
        _kpi1_cls   = "decision-card muted"
        _kpi1_sub   = "Could not reach Bangchak API"
        _kpi1_hint  = '<span class="dc-hint muted">Ask agent for latest price</span>'

    with _kpi1:
        st.markdown(f"""
<div class="{_kpi1_cls}">
  <div class="dc-label">Hi-Diesel Price</div>
  <div class="dc-value">{_price_val} <span style="font-size:0.9rem;font-weight:500;">฿/L</span></div>
  <div class="dc-sub">{_kpi1_sub}</div>
  {_kpi1_hint}
</div>
""", unsafe_allow_html=True)

    # KPI 2 — Monthly Spend (real: fetch_invoices_current_month)
    if _monthly_invoices:
        _kpi2_val  = f"฿{_monthly_spend:,.0f}"
        _kpi2_cls  = "decision-card ok"
        _kpi2_sub  = f"From {_monthly_count} invoice{'s' if _monthly_count != 1 else ''} · {escape(str(_latest_vendor))}"
        _kpi2_hint = '<span class="dc-hint ok">Real data · This month</span>'
    else:
        _kpi2_val  = "฿0"
        _kpi2_cls  = "decision-card muted"
        _kpi2_sub  = "No invoices this month"
        _kpi2_hint = '<span class="dc-hint info">Upload invoices to track spend</span>'

    with _kpi2:
        st.markdown(f"""
<div class="{_kpi2_cls}">
  <div class="dc-label">Monthly Spend</div>
  <div class="dc-value">{_kpi2_val}</div>
  <div class="dc-sub">{_kpi2_sub}</div>
  {_kpi2_hint}
</div>
""", unsafe_allow_html=True)

    # KPI 3 — Invoice Count This Month (real: fetch_invoices_current_month)
    _kpi3_cls  = "decision-card ok" if _monthly_count > 0 else "decision-card muted"
    _kpi3_hint = (
        '<span class="dc-hint ok">Real data · This month</span>'
        if _monthly_count > 0
        else '<span class="dc-hint info">Upload invoices to start</span>'
    )
    with _kpi3:
        st.markdown(f"""
<div class="{_kpi3_cls}">
  <div class="dc-label">Invoices This Month</div>
  <div class="dc-value">{_monthly_count}</div>
  <div class="dc-sub">{"Latest: " + escape(str(_latest_vendor)) if _monthly_invoices else "No invoices yet"}</div>
  {_kpi3_hint}
</div>
""", unsafe_allow_html=True)

    # KPI 4 — Items Tracked all-time (real: count_invoice_items)
    if _item_count is not None and _item_count > 0:
        _kpi4_val  = str(_item_count)
        _kpi4_sub  = "Line items across all invoices"
        _kpi4_cls  = "decision-card ok"
        _kpi4_hint = '<span class="dc-hint ok">Data available for analysis</span>'
    elif _item_count == 0:
        _kpi4_val  = "0"
        _kpi4_sub  = "No invoice items yet"
        _kpi4_cls  = "decision-card muted"
        _kpi4_hint = '<span class="dc-hint info">Upload invoices to start</span>'
    else:
        _kpi4_val  = "—"
        _kpi4_sub  = "Could not load count"
        _kpi4_cls  = "decision-card muted"
        _kpi4_hint = '<span class="dc-hint muted">Check database connection</span>'

    with _kpi4:
        st.markdown(f"""
<div class="{_kpi4_cls}">
  <div class="dc-label">Items Tracked</div>
  <div class="dc-value">{_kpi4_val}</div>
  <div class="dc-sub">{_kpi4_sub}</div>
  {_kpi4_hint}
</div>
""", unsafe_allow_html=True)

    st.write("")

    # ── Section C: Profile Snapshot + Channel Mix ──────────────────────────────
    _col_profile, _col_channels = st.columns(2)

    # Profile Snapshot (real: restaurant_profiles)
    with _col_profile:
        _render_section_header("Restaurant Profile")
        if _profile:
            _store_lbl = _STORE_TYPE_LABELS.get(
                str(_profile.get("store_type", "")),
                str(_profile.get("store_type", "—")),
            )
            _food_tags = " ".join(
                f'<span style="background:#fff7ed;border:1px solid rgba(251,146,60,0.35);'
                f'color:#ea580c;border-radius:999px;padding:2px 8px;'
                f'font-size:0.72rem;font-weight:600;">'
                f'{escape(_FOOD_TYPE_LABELS.get(ft, ft))}</span>'
                for ft in (_profile.get("food_types") or [])[:4]
            )
            _target  = _profile.get("target_margin_pct") or 0
            _warning = _profile.get("warning_margin_pct") or 0
            _risk    = _profile.get("risk_margin_pct") or 0
            st.markdown(f"""
<div class="decision-card ok" style="min-height:160px;">
  <div class="dc-label">{escape(str(_profile.get("restaurant_name", "—")))}</div>
  <div class="dc-sub" style="margin-top:0.3rem;">{escape(_store_lbl)}</div>
  <div style="margin-top:0.6rem;display:flex;flex-wrap:wrap;gap:4px;">{_food_tags}</div>
  <div style="margin-top:0.8rem;display:flex;gap:1rem;font-size:0.76rem;color:#64748b;">
    <span>🎯 Target {_target:.0f}%</span>
    <span>⚠️ Warning {_warning:.0f}%</span>
    <span>🔴 Risk {_risk:.0f}%</span>
  </div>
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div class="decision-card muted" style="min-height:160px;">
  <div class="dc-label">No Profile Yet</div>
  <div class="dc-sub">Complete Business Setup to see your restaurant profile here.</div>
  <span class="dc-hint info">Step 1 of Business Setup</span>
</div>
""", unsafe_allow_html=True)
            if st.button("Complete Business Setup", key="dash_go_profile", use_container_width=True):
                st.session_state["page"] = "profile_settings"
                st.rerun()

    # Channel Mix Summary (real: restaurant_channel_mix)
    with _col_channels:
        _render_section_header("Channel Mix")
        if _channel_mix:
            _ch_rows = "".join(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:0.4rem 0;border-bottom:1px solid var(--ffia-border);">'
                f'<span style="font-weight:600;font-size:0.82rem;color:var(--ffia-text);">'
                f'{escape(ch["platform"])}</span>'
                f'<span style="display:flex;gap:0.8rem;">'
                f'<span style="font-size:0.76rem;color:#64748b;">Rev {ch["revenue_share_pct"]:.0f}%</span>'
                f'<span style="font-size:0.76rem;color:#dc2626;">Fee {ch["platform_fee_pct"]:.0f}%</span>'
                f'</span></div>'
                for ch in _channel_mix
            )
            st.markdown(f"""
<div class="decision-card" style="min-height:160px;padding-bottom:0.6rem;">
  <div class="dc-label">Active Platforms</div>
  <div style="margin-top:0.6rem;">{_ch_rows}</div>
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div class="decision-card muted" style="min-height:160px;">
  <div class="dc-label">No Channels Configured</div>
  <div class="dc-sub">Set up your delivery platform mix in Business Setup Step 3.</div>
  <span class="dc-hint info">Complete Step 3 of Business Setup</span>
</div>
""", unsafe_allow_html=True)

    st.write("")

    # ── Section D: Top Spend Items This Month ─────────────────────────────────
    _render_section_header(
        "Top Spend Items — This Month",
        "Ingredients and supplies costing you the most this month.",
    )
    if _top_items:
        _max_spend = _top_items[0]["total_spend"] if _top_items else 1
        for _rank, _item in enumerate(_top_items, 1):
            _bar_pct   = (_item["total_spend"] / _max_spend * 100) if _max_spend > 0 else 0
            _bar_color = "#f97316" if _rank == 1 else "#fb923c" if _rank == 2 else "#fdba74"
            st.markdown(f"""
<div style="display:flex;align-items:center;gap:0.9rem;padding:0.45rem 0;
            border-bottom:1px solid var(--ffia-border);">
  <span style="width:1.4rem;font-size:0.72rem;font-weight:700;color:#94a3b8;text-align:right;">
    #{_rank}
  </span>
  <span style="flex:1;font-size:0.85rem;font-weight:600;color:var(--ffia-text);">
    {escape(str(_item["name"]))}
  </span>
  <div style="width:120px;height:6px;background:#f1f5f9;border-radius:999px;overflow:hidden;">
    <div style="width:{_bar_pct:.1f}%;height:100%;background:{_bar_color};border-radius:999px;"></div>
  </div>
  <span style="width:80px;text-align:right;font-size:0.82rem;font-weight:700;color:var(--ffia-text);">
    ฿{_item["total_spend"]:,.0f}
  </span>
</div>
""", unsafe_allow_html=True)
        st.write("")
    else:
        st.markdown("""
<div class="decision-card muted">
  <div class="dc-sub">No invoice items this month yet.
    Upload invoices to see your top spend breakdown.</div>
</div>
""", unsafe_allow_html=True)


# Step 8: Overview page renderer — hero, status pills, decision cards, onboarding, quick actions
def _render_dashboard_page(current_user: dict):
    """Render the Overview page: status cards, onboarding guide, and quick actions."""

    # Step 8-pre: One-time migration — persist session profile_channels to DB if table is empty
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
            pass  # Migration is best-effort — never block the overview

    # ── Section A: Header ──────────────────────────────────────────────────────
    _render_page_hero(
        "FFIA — Fuel & Food Impact Analyzer",
        "Your FFIA Agent is ready. Ask about diesel impact, margin risk, "
        "repricing ideas, or your latest invoice.",
        eyebrow="Restaurant Intelligence",
    )

    # ── Section A2: Onboarding guide ───────────────────────────────────────────
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

    # ── Section B: Quick Actions ───────────────────────────────────────────────
    _quick_actions_slot = st.empty()
    with _quick_actions_slot.container(border=True):
        _render_section_header(
            "Check your costs and profit",
            "Use a guided shortcut to start a common workflow, then continue the analysis in FFIA.",
        )

        _QUICK_ACTIONS = [
            ("⛽ ดีเซลขึ้น 5 บาท กระทบฉันแค่ไหน",    "ดีเซลขึ้น 5 บาท กระทบต้นทุนและกำไรของฉันแค่ไหน"),
            ("🛵 ช่องทางเดลิเวอรี่ยังทำกำไรไหม",       "ช่องทางเดลิเวอรี่ของฉันยังทำกำไรอยู่ไหม"),
            ("💸 โปรนี้ยังคุ้มไหม",                     "โปรโมชั่นที่ฉันจะทำยังคุ้มอยู่ไหม"),
            ("📊 ต้นทุนฉันแพงตรงไหน",                  "ต้นทุนของฉันแพงที่สุดตรงไหน"),
            ("📉 กำไรหายไปตรงไหน",                     "กำไรของฉันหายไปตรงไหน"),
            ("🧺 วัตถุดิบไหนแพงที่สุด",                 "วัตถุดิบไหนที่แพงที่สุดในเดือนนี้"),
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
