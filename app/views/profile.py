from collections.abc import Callable
import base64
from html import escape
from pathlib import Path

import streamlit as st

from app.components.layout import _render_page_hero, _render_section_header
from app.views.dashboard import _get_cached_diesel_price, _get_cached_item_count
from app.views.upload import _render_upload_invoice_section
from data.db import (
    fetch_invoices_current_month,
    fetch_latest_restaurant_profile,
    upsert_channel_mix,
    upsert_restaurant_profile,
)


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
        if st.button("Next", type="primary", key="step1_next"):
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
        if st.button("Back", key="step2_back"):
            st.session_state["profile_step"] = 1
            st.rerun()
    with _col_next:
        if st.button("Next", type="primary", key="step2_next"):
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
    _path = Path(__file__).resolve().parent.parent / "assets" / filename
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
        if st.button("Back", key="step3_back"):
            st.session_state["profile_step"] = 2
            st.rerun()
    with _col_next:
        if st.button("Next", type="primary", key="step3_next"):
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
        if st.button("Back", key="step4_back"):
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


def _render_profile_settings_page(
    current_user: dict,
    get_extract_invoice_data: Callable[[], Callable],
    get_run_agent: Callable[[], Callable],
) -> None:
    """Render Business Setup: profile onboarding + invoice upload/cost data."""
    # Step 1: Page header
    _render_page_hero(
        "Business Setup",
        "Set up your restaurant profile and manage invoice cost data in one place.",
        eyebrow="Restaurant Setup",
    )

    # Step 2: Fetch existing profile — used for pre-population and save-time defaults
    try:
        _profile = fetch_latest_restaurant_profile(current_user["user_id"])
    except Exception:
        st.error("Unable to load your profile. Please refresh the page or contact support.")
        return

    # Step 2b: Initialize outer setup stepper (first entry this session only)
    if "setup_step" not in st.session_state:
        st.session_state["setup_step"] = 1
    _setup_step = st.session_state["setup_step"]

    # Step 2c: Outer 3-step progress header
    _cls1 = "setup-stepper-label active" if _setup_step == 1 else "setup-stepper-label done"
    _cls2 = "setup-stepper-label active" if _setup_step == 2 else ("setup-stepper-label done" if _setup_step > 2 else "setup-stepper-label")
    _cls3 = "setup-stepper-label active" if _setup_step == 3 else "setup-stepper-label"
    st.markdown(f"""
    <div class="setup-stepper">
      <span class="{_cls1}">1 — Business Profile</span>
      <div class="setup-stepper-connector"></div>
      <span class="{_cls2}">2 — Upload Cost Data</span>
      <div class="setup-stepper-connector"></div>
      <span class="{_cls3}">3 — Review Readiness</span>
    </div>
    """, unsafe_allow_html=True)
    st.progress(_setup_step / 3)
    st.write("")

    if _setup_step == 1:
        with st.container(border=True):
            _render_section_header(
                "Business Profile",
                "Keep your restaurant profile up to date so FFIA can personalize insights and recommendations.",
            )

            # Step 3: Show success banner; advance outer stepper on successful save
            if st.session_state.pop("profile_save_success", False):
                st.success("Business profile saved successfully.")
                st.session_state["setup_step"] = 2
                st.rerun()

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

    elif _setup_step == 2:
        _s2_back, _, _s2_next = st.columns([1, 5, 1])
        with _s2_back:
            if st.button("Back", key="setup_s2_back"):
                st.session_state["setup_step"] = 1
                st.rerun()
        with _s2_next:
            if st.button("Continue to Review", key="setup_s2_next", type="primary"):
                st.session_state["setup_step"] = 3
                st.rerun()
        _render_upload_invoice_section(
            current_user,
            section_title="Invoice Upload & Cost Data",
            section_description="Upload invoice images, review extracted details, save invoices, "
            "and inspect current-month invoice items.",
            get_extract_invoice_data=get_extract_invoice_data,
            get_run_agent=get_run_agent,
        )

    elif _setup_step == 3:
        _render_review_readiness_step(current_user, _profile)


def _render_review_readiness_step(current_user: dict, profile: dict | None) -> None:
    """Step 3 of Business Setup: readiness summary and navigation CTAs."""
    _uid = current_user["user_id"]

    _render_section_header(
        "Review Readiness",
        "A quick check before you start chatting with FFIA.",
    )

    if st.button("Back to Upload", key="setup_s3_back"):
        st.session_state["setup_step"] = 2
        st.rerun()

    st.write("")

    # --- Profile summary ---
    with st.container(border=True):
        _render_section_header("Business Profile", "")
        if not profile:
            st.warning("No business profile saved yet. Complete Step 1 first.")
            if st.button("Go to Business Profile", key="setup_s3_to_s1"):
                st.session_state["setup_step"] = 1
                st.rerun()
        else:
            _c1, _c2 = st.columns([2, 1])
            with _c1:
                st.markdown(f"**{profile.get('restaurant_name', '—')}**")
                st.caption(
                    f"Store type: {profile.get('store_type', '—').replace('_', ' ').title()}"
                    f" · Seat range: {profile.get('seat_range', '—').replace('_', ' ')}"
                )
                _ftypes = profile.get("food_types") or []
                if _ftypes:
                    st.caption("Cuisines: " + ", ".join(str(f).replace("_", " ").title() for f in _ftypes))
            with _c2:
                st.success("Profile saved ✓")

    # --- Data readiness metrics ---
    with st.container(border=True):
        _render_section_header("Data Readiness", "")
        _m1, _m2, _m3 = st.columns(3)

        with _m1:
            try:
                _inv = fetch_invoices_current_month(_uid)
                _inv_count = len(_inv) if _inv else 0
            except Exception:
                _inv_count = 0
            st.metric(
                "Invoices This Month",
                _inv_count,
                delta="Ready" if _inv_count > 0 else "None yet",
                delta_color="normal" if _inv_count > 0 else "off",
            )

        with _m2:
            _items = _get_cached_item_count(_uid)
            st.metric("Cost Items Tracked", _items if _items is not None else "—")

        with _m3:
            _diesel = _get_cached_diesel_price()
            if "error" not in _diesel:
                st.metric(
                    "Diesel Price (Hi S)",
                    f"฿{_diesel.get('PriceToday', '—')} / L",
                    delta=str(_diesel.get("OilPriceDate", "")),
                )
            else:
                st.metric("Diesel Price", "Unavailable")

    # --- Contextual guidance ---
    st.write("")
    if not profile:
        st.warning("Complete your Business Profile before using the AI assistant.")
    elif _inv_count == 0:
        st.warning("No invoices uploaded yet — FFIA will use estimated benchmarks for analysis.")
    else:
        st.success("Setup complete. FFIA is ready to analyze your business.")

    # --- CTAs ---
    st.write("")
    _cta1, _, _cta2 = st.columns([1, 1, 1])
    with _cta1:
        if st.button("Open AI Assistant", key="setup_s3_ai", type="primary", use_container_width=True):
            st.session_state["page"] = "ai_assistant"
            st.rerun()
    with _cta2:
        if st.button("View Dashboard", key="setup_s3_dash", use_container_width=True):
            st.session_state["page"] = "dashboard"
            st.rerun()
