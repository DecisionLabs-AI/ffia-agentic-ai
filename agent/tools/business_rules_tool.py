# =============================================================================
# FFIA — agent/tools/business_rules_tool.py
# Business rule tools: L1 Platform Floor Guard, L3 Promo Profitability,
# L4 COGS Alert, and Scenario Classifier.
#
# Source of truth:
#   docs/business_rules.md  — Rules L1, L3, L4
#   docs/scenarios.md       — Scenario 1 / 2 / 3 selection logic
# =============================================================================

# Step 1: Imports
from langchain_core.tools import tool

# Step 2: Constants — defined strictly from docs/business_rules.md

# L3 magic number list (docs/business_rules.md — Rule L3, Pricing rule)
_MAGIC_NUMBERS = [49, 59, 69, 79, 89, 99, 109, 119, 129, 149, 169, 189, 199, 249, 299]

# L4 COGS base midpoints by cuisine group (docs/business_rules.md — Rule L4, COGS Base per Cuisine Group)
# Range is given in docs; midpoint used as representative value.
# MVP assumption: use range midpoint when no specific point is documented.
_COGS_BASE = {
    "lpg_intensive":    0.375,   # docs: 35–40%
    "freshness_pkg":    0.355,   # docs: 33–38%
    "high_cogs_import": 0.470,   # docs: 42–52% (before THB depreciation adjustment)
    "high_energy_ops":  0.300,   # docs: 25–35%
}

# L4 substitute map (docs/business_rules.md — Rule L4, Substitute map)
# Triggered when market_price_increase_pct > 15%
_SUBSTITUTE_MAP = {
    "lpg_intensive":    "Switch pork → chicken; increase portion rice by 10%",
    "high_cogs_import": "Switch salmon → local shrimp; switch imported beef → local beef",
    "freshness_pkg":    "Reduce lime per dish by 20%; reduce packaging size",
    "high_energy_ops":  "Reduce espresso shot by 0.5; increase blend ratio by 10%",
}


# Step 3: Internal helper — round up to nearest psychological price
def _round_to_magic_number(price: float) -> int:
    """Return the first magic number >= price. If above range, return int(price)."""
    for m in _MAGIC_NUMBERS:
        if m >= price:
            return m
    return int(price)  # above defined magic number range


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Tool — Platform Cost Floor Guard (Rule L1)
# Source: docs/business_rules.md — Rule L1
# ─────────────────────────────────────────────────────────────────────────────
@tool
def platform_floor_guard_tool(
    gross_revenue: float,
    gp_pct: float,
    fuel_surcharge: float,
    promo_discount: float,
) -> str:
    """Check whether a delivery order's platform cost floor is healthy (Rule L1).

    Always fetch gp_pct from the platform_fee table using postgres_tool first
    (e.g. SELECT fee_percent / 100 FROM platform_fee WHERE platform = 'Grab').
    Use this tool when the user asks about platform margin, delivery profitability,
    or whether a menu item covers costs after platform commission.

    Args:
        gross_revenue: Menu selling price in THB (e.g. 150.0).
        gp_pct: Platform commission as a fraction (e.g. 0.30 for 30%).
        fuel_surcharge: Fuel surcharge amount in THB (e.g. 8.0).
        promo_discount: Promotion discount amount in THB (e.g. 10.0).

    Returns:
        Status label (HEALTHY/WATCH/WARNING/CRITICAL), platform floor %, and action.
    """
    # Step 4a: Guard against invalid input
    if gross_revenue <= 0:
        return "Error: gross_revenue must be greater than 0."
    if not (0.0 <= gp_pct < 1.0):
        return "Error: gp_pct must be a fraction between 0 and 1 (e.g. 0.30 for 30%)."

    # Step 4b: Apply L1 formulas (docs/business_rules.md — Rule L1, Formula)
    gp_commission = gross_revenue * gp_pct
    platform_floor = gross_revenue - gp_commission - fuel_surcharge - promo_discount
    platform_floor_pct = platform_floor / gross_revenue * 100

    # Step 4c: Classify by threshold and map to recommended action
    # (docs/business_rules.md — Rule L1, Decision thresholds + Recommended action)
    if platform_floor_pct > 65:
        status = "HEALTHY"
        action = "Keep current strategy."
    elif platform_floor_pct >= 60:
        status = "WATCH"
        action = "Monitor trend closely."
    elif platform_floor_pct >= 50:
        status = "WARNING"
        action = "Recommend a price increase or pause promotion."
    else:
        status = "CRITICAL"
        action = "Recommend temporary suspension of this menu from the platform."

    # Step 4d: Return emoji-prefixed decision format
    status_icons = {"HEALTHY": "✅", "WATCH": "⚠️", "WARNING": "🔶", "CRITICAL": "❌"}
    icon = status_icons[status]
    return (
        f"{icon} Platform Floor: {status}\n\n"
        f"📊 Floor Usage: {platform_floor_pct:.1f}% of gross revenue\n\n"
        f"What to do:\n"
        f"• {action}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Tool — Promo Profitability Guard (Rule L3, simplified)
# Source: docs/business_rules.md — Rule L3
# ─────────────────────────────────────────────────────────────────────────────
@tool
def promo_profitability_tool(
    gross_revenue: float,
    cogs: float,
    fuel: float,
    packaging: float,
    fixed_alloc: float,
    gp_pct: float,
    target_margin: float,
    promo_discount: float,
) -> str:
    """Check whether a planned promotion is financially viable (Rule L3).

    Use this tool before the user launches a promotion, flash sale, or discount
    campaign. All monetary values in THB; gp_pct and target_margin are fractions.

    Args:
        gross_revenue: Menu selling price before discount in THB.
        cogs: Ingredient cost for this item in THB.
        fuel: Fuel/logistics cost allocated to this item in THB.
        packaging: Packaging cost in THB.
        fixed_alloc: Fixed cost allocation per item in THB.
        gp_pct: Platform commission as a fraction (e.g. 0.30).
        target_margin: Desired net margin as a fraction (e.g. 0.20).
        promo_discount: Discount amount in THB.

    Returns:
        Whether the promo is viable, suggested price, and required action.
    """
    # Step 5a: Guard against invalid denominators
    if gross_revenue <= 0:
        return "Error: gross_revenue must be greater than 0."
    if not (0.0 <= gp_pct < 1.0):
        return "Error: gp_pct must be a fraction between 0 and 1."
    if not (0.0 <= target_margin < 1.0):
        return "Error: target_margin must be a fraction between 0 and 1."

    denom = 1 - gp_pct - target_margin
    if denom <= 0:
        return "Error: gp_pct + target_margin must be less than 1.0."

    # Step 5b: Compute total cost and minimum viable price
    # (docs/business_rules.md — Rule L3, Formula: min_price)
    total_cost = cogs + fuel + packaging + fixed_alloc
    min_price = total_cost / denom

    # Step 5c: Round up to nearest magic number for psychological pricing
    # (docs/business_rules.md — Rule L3, Pricing rule)
    suggested_price = _round_to_magic_number(min_price)

    # Step 5d: Check if the post-discount revenue covers min_price
    # MVP assumption: promo_viable = revenue after discount >= min_price
    effective_revenue = gross_revenue - promo_discount
    promo_viable = effective_revenue >= min_price

    # Step 5e: Build reason and action bullets for emoji-prefixed decision format
    viable_icon = "✅" if promo_viable else "❌"
    if not promo_viable:
        reason = (
            f"Post-discount revenue ({effective_revenue:.2f} THB) "
            f"is below minimum viable price ({min_price:.2f} THB)."
        )
        what_to_do = "• Avoid this promotion.\n• Use a bundle strategy instead."
    else:
        reason = (
            f"Post-discount revenue ({effective_revenue:.2f} THB) "
            "covers the minimum viable price."
        )
        what_to_do = f"• Proceed with the promotion.\n• Set selling price at {suggested_price} THB."

    # Step 5f: Return emoji-prefixed decision format
    return (
        f"{viable_icon} Promo Viable: {'YES' if promo_viable else 'NO'}\n\n"
        f"💰 Recommended Price: {suggested_price} THB\n\n"
        f"Reason:\n"
        f"• {reason}\n\n"
        f"What to do:\n"
        f"{what_to_do}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Tool — Raw Material COGS Alert + Bundle Strategy (Rule L4)
# Source: docs/business_rules.md — Rule L4
# ─────────────────────────────────────────────────────────────────────────────
# MVP assumption: default target_margin = 20% if not provided by user
@tool
def cogs_alert_tool(
    cuisine_group: str,
    market_price_increase_pct: float,
    cogs_baseline_30d: float,
    target_margin: float = 0.20,
) -> str:
    """Monitor raw material COGS changes and recommend substitute or bundle strategy (Rule L4).

    cuisine_group must be one of: lpg_intensive, freshness_pkg, high_cogs_import, high_energy_ops.
    Use this tool when ingredient market prices change or when the user asks about
    raw material cost impact. market_price_increase_pct is a fraction (e.g. 0.20 for 20%).
    cogs_baseline_30d is the 30-day baseline COGS as a fraction (e.g. 0.38 for 38%).

    Args:
        cuisine_group: Restaurant cuisine category (see valid values above).
        market_price_increase_pct: Ingredient market price increase as a fraction.
        cogs_baseline_30d: 30-day COGS baseline as a fraction.
        target_margin: Target net margin as a fraction (e.g. 0.20).

    Returns:
        COGS impact %, alert level, and actionable recommendation.
    """
    # Step 6a: Validate cuisine_group
    valid_groups = list(_COGS_BASE.keys())
    if cuisine_group not in valid_groups:
        return (
            f"Error: Unknown cuisine_group '{cuisine_group}'. "
            f"Valid values: {', '.join(valid_groups)}"
        )

    if market_price_increase_pct > 1.5:
        return (
            "Error: market_price_increase_pct looks like a whole-number percentage. "
            "Please provide a fraction (e.g. 0.20 for 20%)."
        )

    # Step 6b: Get COGS base for this cuisine group
    # (docs/business_rules.md — Rule L4, COGS Base per Cuisine Group)
    cogs_base = _COGS_BASE[cuisine_group]

    # Step 6c: Inventory lag logic
    # MVP assumption: inventory_fill_ratio defaults to 0.5 when stock data is unavailable
    # (docs/business_rules.md — Rule L4, Fallback rule)
    inventory_fill_ratio = 0.5  # MVP assumption: no stock input in simplified tool

    # Step 6d: Effective price increase and COGS calculation
    # (docs/business_rules.md — Rule L4, Inventory Lag Logic)
    effective_price_increase_pct = market_price_increase_pct * (1 - inventory_fill_ratio)
    effective_cogs_pct = cogs_base * (1 + effective_price_increase_pct)
    cogs_delta = effective_cogs_pct - cogs_baseline_30d

    # Step 6e: Classify alert level
    # (docs/business_rules.md — Rule L4, Decision thresholds)
    if cogs_delta > 0.20:
        alert = "URGENT"
        alert_action = "Hide menu item or raise price immediately."
    elif cogs_delta > 0.10:
        alert = "ALERT"
        alert_action = "Suggest substitute ingredient."
    elif cogs_delta > 0.05:
        alert = "MONITOR"
        alert_action = "Flag in weekly digest."
    else:
        alert = "OK"
        alert_action = "Within normal range — no action needed."

    # Step 6f: Substitute recommendation when market increase > 15%
    # (docs/business_rules.md — Rule L4, Substitute map)
    substitute_bullet = ""
    if market_price_increase_pct > 0.15:
        substitute = _SUBSTITUTE_MAP.get(cuisine_group, "")
        if substitute:
            substitute_bullet = f"\n• {substitute}"

    # Step 6g: Return emoji-prefixed decision format
    alert_icons = {"OK": "✅", "MONITOR": "✅", "ALERT": "⚠️", "URGENT": "❌"}
    alert_icon = alert_icons.get(alert, "")
    impact_pct = cogs_delta * 100
    return (
        f"{alert_icon} COGS Alert: {alert}\n\n"
        f"📈 Cost Impact: +{impact_pct:.1f}% increase\n\n"
        f"What to do:\n"
        f"• {alert_action}"
        f"{substitute_bullet}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 7: Tool — Scenario Classifier (Scenarios 1 / 2 / 3)
# Source: docs/scenarios.md — Scenario Selection Logic
# ─────────────────────────────────────────────────────────────────────────────
@tool
def scenario_classifier_tool(
    net_margin_pct: float,
    fuel_cost_pct_of_total: float,
    gp_exceeds_breakeven: bool,
) -> str:
    """Classify the current business situation into Scenario 1, 2, or 3 (docs/scenarios.md).

    Use this tool when the user asks which strategy to apply or how to respond to
    rising costs. All percentage inputs must be fractions (e.g. 0.18 for 18%).
    Priority: check net_margin first, then check fuel/GP override for Scenario 3.

    Args:
        net_margin_pct: Current net margin as a fraction (e.g. 0.18 for 18%).
        fuel_cost_pct_of_total: Fuel cost as fraction of total cost (e.g. 0.22 for 22%).
        gp_exceeds_breakeven: True if platform GP commission exceeds break-even point.

    Returns:
        Scenario number, strategy name, and action plan.
    """
    # Step 7a: Guard against implausible inputs
    if net_margin_pct > 1.5 or fuel_cost_pct_of_total > 1.5:
        return (
            "Error: net_margin_pct and fuel_cost_pct_of_total must be fractions "
            "(e.g. 0.18 for 18%), not whole-number percentages."
        )

    # Step 7b: Scenario selection logic
    # (docs/scenarios.md — Scenario Selection Logic)
    # Priority: check net_margin first, then apply Scenario 3 modifier if triggered
    if net_margin_pct < 0.15:
        # Below 15% — operational optimization required regardless of fuel
        scenario = 3
        strategy = "Operational Optimization"
        reason = f"Net margin ({net_margin_pct:.1%}) is below the 15% threshold."

    elif fuel_cost_pct_of_total > 0.20 or gp_exceeds_breakeven:
        # Fuel or GP trigger — even if margin is currently acceptable
        scenario = 3
        strategy = "Operational Optimization"
        if fuel_cost_pct_of_total > 0.20:
            reason = f"Fuel cost ({fuel_cost_pct_of_total:.1%}) exceeds 20% of total cost."
        else:
            reason = "Platform GP commission exceeds break-even point."

    elif net_margin_pct >= 0.20:
        # Safe margin — Defensive strategy
        scenario = 1
        strategy = "Defensive — Maintain Price"
        reason = f"Net margin ({net_margin_pct:.1%}) is above 20% — safe zone."

    else:
        # 15–20% range — Balanced targeted adjustment
        scenario = 2
        strategy = "Balanced — Targeted Price Adjustment"
        reason = f"Net margin ({net_margin_pct:.1%}) is between 15% and 20%."

    # Step 7c: Action plans per scenario
    # (docs/scenarios.md — Action Plan per scenario)
    if scenario == 1:
        actions = (
            "• Maintain current menu pricing.\n"
            "• Reduce non-critical expenses (marketing, miscellaneous ops).\n"
            "• Monitor margin trend — no immediate price adjustment needed."
        )
    elif scenario == 2:
        actions = (
            "• Identify menu items with high fuel or logistics impact.\n"
            "• Increase price by 5–10% on those high-impact items only.\n"
            "• Maintain price for unaffected menu items.\n"
            "• Recalculate overall Net Margin after adjustment."
        )
    else:  # scenario == 3
        actions = (
            "• Switch to ingredient suppliers closer to the restaurant to reduce transport cost.\n"
            "• Promote Self-Pickup / Store Pickup options to eliminate delivery and GP costs.\n"
            "• Adjust procurement cycle from daily → every other day to cut logistics surcharge."
        )

    # Step 7d: Return emoji-prefixed decision format
    return (
        f"📋 Scenario {scenario} — {strategy}\n\n"
        f"Situation:\n"
        f"• {reason}\n\n"
        f"What to do:\n"
        f"{actions}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 8: Standalone smoke test — run directly to verify all tools
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== L1: Platform Floor Guard ===")
    print(platform_floor_guard_tool.invoke({
        "gross_revenue": 100.0,
        "gp_pct": 0.30,
        "fuel_surcharge": 3.0,
        "promo_discount": 5.0,
    }))

    print("\n=== L3: Promo Profitability ===")
    print(promo_profitability_tool.invoke({
        "gross_revenue": 150.0,
        "cogs": 55.0,
        "fuel": 8.0,
        "packaging": 5.0,
        "fixed_alloc": 10.0,
        "gp_pct": 0.30,
        "target_margin": 0.20,
        "promo_discount": 30.0,
    }))

    print("\n=== L4: COGS Alert ===")
    print(cogs_alert_tool.invoke({
        "cuisine_group": "lpg_intensive",
        "market_price_increase_pct": 0.20,
        "cogs_baseline_30d": 0.38,
        "target_margin": 0.20,
    }))

    print("\n=== Scenario Classifier ===")
    print(scenario_classifier_tool.invoke({
        "net_margin_pct": 0.18,
        "fuel_cost_pct_of_total": 0.15,
        "gp_exceeds_breakeven": False,
    }))
