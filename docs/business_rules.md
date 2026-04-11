# Business Rules & Decision Logic

This document defines the core business rules used by FFIA (Fuel & Food Impact Analyzer) to protect restaurant margin and support pricing, promotion, ingredient, and delivery decisions.

The rules below are based on five logic groups:

1. Platform cost floor protection
2. Cross-platform margin comparison
3. Promotion profitability check
4. Raw material COGS alert and bundle strategy
5. Dynamic delivery radius control

---

## Rule L1: Platform Cost Floor Guard

### Purpose

Check whether each delivery order still has enough money left before ingredient cost is deducted.

### Applies when

* Order comes from Grab, LINE MAN, or Shopee
* Source can be:

  * `csv` with confidence = 1.0
  * `ocr` with confidence between 0 and 1

### Validation rule

* If OCR confidence < 0.85, the system must ask for confirmation before showing an alert

### Formula

* `platform_floor = gross_revenue - gp_commission - fuel_surcharge - promo_discount`
* `platform_floor_pct = platform_floor / gross_revenue * 100`

### Decision thresholds

* `platform_floor_pct > 65%` → **HEALTHY**
* `platform_floor_pct 60–65%` → **WATCH**
* `platform_floor_pct 50–60%` → **WARNING**
* `platform_floor_pct < 50%` → **CRITICAL**

### Recommended action

* HEALTHY → keep current strategy
* WATCH → monitor trend closely
* WARNING → recommend price increase or pause promotion
* CRITICAL → recommend temporary suspension of this menu from the platform

### Business meaning

This rule helps the restaurant understand how much revenue remains after commission, surcharge, and promo cost, before ingredient cost is deducted.

---

## Rule L2: Cross-Platform Margin Arbitrage

### Purpose

Compare the same menu item across multiple delivery platforms and rebalance effort toward the platform with better margin.

### Applies when

* The restaurant uses more than one platform
* The system compares `platform_floor_pct` daily across platforms for the same menu

### Trigger rule

Trigger rebalancing when:

* `margin_gap > 5%`
* for at least 3 consecutive days
* and `volume_capacity_ok = true`

### Formula

* `margin_gap = platform_A_floor_pct - platform_B_floor_pct`
* `rebalance_trigger = margin_gap > 5 AND consecutive_days >= 3 AND volume_capacity_ok = true`
* `monthly_gain_est = margin_gap * avg_order_value * avg_daily_orders * 30`

### Decision thresholds

* `gap > 5%` for 3 consecutive days → move promo budget to the better-margin platform
* `gap > 10%` for 5 consecutive days → pause promo on the worse-margin platform
* If dine-in is profitable but delivery is loss-making → hide the menu from delivery platforms

### Business meaning

This rule prevents restaurants from looking only at total sales and ignoring margin differences between platforms.

---

## Rule L3: Promo Profitability Guard + Safe-to-Play Simulator

### Purpose

Check whether a promotion or campaign is financially viable before the restaurant launches it.

### Applies when

* The restaurant is about to run a promotion on a platform
* Especially for large campaigns such as Flash Sale 50%

### Formula

* `promo_net_floor = platform_floor - promo_discount`
* `promo_viable = promo_net_floor > cogs_estimate_min`
* `break_even_volume = fixed_cost / (promo_net_floor - cogs_estimate_avg)`
* `required_volume_increase = (break_even_volume / avg_daily_orders_30d) - 1`
* `campaign_viable = required_volume_increase <= 0.30`
* `min_price = (cogs + fuel + packaging + fixed_alloc) / (1 - gp_pct - target_margin)`

### Pricing rule

Suggested price should be rounded up to the nearest acceptable psychological price:

`magic_numbers = [49,59,69,79,89,99,109,119,129,149,169,189,199,249,299]`

### Examples

* `min_price = 102` → suggested price = `109`
* `min_price = 87` → suggested price = `89`

### Decision thresholds

* `promo_viable = false` → block the promotion and suggest bundle instead
* viable but required volume increase is too high → show break-even volume clearly
* if first 2-hour volume pace is below expectation → recommend stopping or adjusting the promo
* `campaign_viable = false` → recommend passing the campaign and explain why with numbers

### Business meaning

This rule prevents restaurants from joining campaigns that appear attractive but destroy margin.

---

## Rule L4: Raw Material COGS Alert + Bundle Strategy

### Purpose

Monitor ingredient market prices daily and recalibrate menu COGS based on cuisine group and inventory lag.

### Applies when

* Market ingredient prices change
* COGS must be recalculated by cuisine group
* Inventory lag must be considered before alerting

### COGS Base per Cuisine Group

* `lpg_intensive` → base `35–40%`
* `freshness_pkg` → base `33–38%`
* `high_cogs_import` → base `42–52% × (1 + thb_depreciation_7d)`
* `high_energy_ops` → base `25–35%`

### Inventory Lag Logic

* `inventory_fill_ratio = stock_remaining / inventory_turnover_days`
* `effective_price_increase_pct = market_price_increase_pct * (1 - inventory_fill_ratio)`
* `effective_cogs_pct = cogs_base * (1 + effective_price_increase_pct)`

### Example

If pork market price increases 20%, but 60% of old stock remains:

* effective increase = `20% × 0.4 = 8%`

### Fallback rule

* If stock data is missing, assume `inventory_fill_ratio = 0.5`

### COGS delta

* `cogs_delta = effective_cogs_pct - cogs_baseline_30d`

### Bundle logic

* `bundle_price = suggested_price(high_cogs_cost + low_cogs_cost / (1 - target_margin))`
* `blended_margin = (high_cogs_menu_margin + pairing_menu_margin) / 2`

### Pairing criteria

Use pairing menu when:

* `cogs_pct < 0.25`
* `margin_pct > 0.50`

Examples:

* drinks
* fried side dishes

### Decision thresholds

* `cogs_delta 5–10%` → monitor in weekly digest
* `cogs_delta 10–20%` → alert and suggest substitute ingredient
* `cogs_delta > 20%` → urgent alert, hide menu or raise price immediately
* `market_price_increase > 15%` → suggest cross-category bundle instead of direct price increase

### Substitute map

When `market_price_increase > 15%`:

* `lpg_intensive` → pork → chicken, portion_rice +10%
* `high_cogs_import` → salmon → local shrimp, imported beef → local beef
* `freshness_pkg` → reduce lime per dish by 20%, reduce packaging size
* `high_energy_ops` → espresso_shot -0.5, blend_ratio +10%

### Business meaning

This rule prevents the restaurant from reacting too early to market price changes when old stock still remains, and encourages bundle strategy to improve blended margin.

---

## Rule L5: Dynamic Delivery Radius Control

### Purpose

Adjust delivery radius based on real-time margin pressure from diesel price, traffic, and rain conditions.

### Applies when

* Real-time delivery operations are active
* Net margin per order is evaluated together with traffic index and diesel price

### Formula

* `fuel_cost_per_km = diesel_price × 0.06`
* `traffic_multiplier = 1 + (traffic_index × 0.5)`
* `effective_cost_per_km = fuel_cost_per_km × traffic_multiplier`
* `break_even_km = (platform_floor - cogs_estimate_avg) / effective_cost_per_km`
* `compound_trigger = traffic_index > 0.70 AND diesel_price > diesel_baseline × 1.15`
* `rain_surge_pct = round(fuel_surcharge_delta / (1 - gp_pct) / 0.05) × 5`

### Example

If surcharge increases by ฿8 and GP = 28%:

* needed surge = `11.1%`
* suggested rain surge = `10%`

### Decision thresholds

* `net_margin > 10%` → keep current radius or expand if demand is high
* `net_margin 7–10%` → monitor, no change
* `net_margin 5–7%` → recommend reducing radius by 1 km
* `net_margin 2–5%` → recommend reducing radius by 2 km, with confirmation
* `net_margin < 2%` → reduce radius automatically to break-even km, pending approval
* `compound_trigger = true` → temporarily shrink radius during peak hours
* `rain_probability > 70%` → recommend Rain Surge Pricing

### Business meaning

This rule helps restaurants protect margin on delivery orders when fuel and traffic costs rise together.

---

## Rule Priority

When multiple rules are triggered at the same time, the system should prioritize them in this order:

1. **L3 Promo Profitability Guard**
   because a bad promotion can accelerate losses immediately

2. **L5 Dynamic Delivery Radius Control**
   because real-time operational losses require fast action

3. **L1 Platform Cost Floor Guard**
   because platform floor is the base protection layer per order

4. **L4 Raw Material COGS Alert + Bundle Strategy**
   because ingredient inflation affects mid-term menu profitability

5. **L2 Cross-Platform Margin Arbitrage**
   because this is mainly an optimization layer after margin protection is secured

---

## Core Output Labels Used by the System

The system may classify results using the following labels:

* HEALTHY
* WATCH
* WARNING
* CRITICAL

These labels should be shown with clear business explanations, not only raw numbers.

---

## Business Rule Summary

FFIA uses these rules to answer questions such as:

* Is this order still profitable after platform deductions?
* Should the restaurant keep or stop a promotion?
* Which platform gives better margin for the same menu?
* When should the restaurant substitute ingredients or use bundle strategy?
* When should the restaurant reduce delivery radius to protect net margin?

These rules form the business logic layer behind the AI recommendations.
