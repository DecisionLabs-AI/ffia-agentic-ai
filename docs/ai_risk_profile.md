# AI Risk Profile Preview

## Purpose

AI Risk Profile Preview helps restaurant owners see early business risks after
completing Business Setup and before asking FFIA Advisor for deeper analysis.

This preview is designed to answer: "จากข้อมูล setup ตอนนี้ ร้านมีความเสี่ยง
หรือโอกาสตรงไหนที่ควรดูต่อ?" It gives a quick, understandable snapshot of
channel mix, estimated margin pressure, LPG/fuel sensitivity, and direct-sales
opportunity.

## Scope

AI Risk Profile Preview is:

- a rule-based preview
- generated from structured Business Setup data
- generated in the frontend UI
- not an LLM call
- not a LangGraph/ReAct agent analysis
- not the same as FFIA Advisor chat analysis
- intended for quick guidance, not accounting-grade net profit

The preview should stay separate from `docs/business_rules.md` because it is a
UI heuristic layer, not a deterministic business-rule tool.

## Input Data

The preview uses structured setup/profile data such as:

- `restaurant_profiles`
- `restaurant_channel_mix`
- `food_types`
- `store_type`
- `target_margin_pct`
- `warning_margin_pct`
- `risk_margin_pct`
- `platform_fee_pct`
- `revenue_share_pct`
- estimated food cost assumption
- estimated fixed cost assumption

In the current MVP, estimated food cost and estimated fixed cost are benchmark
assumptions derived from setup fields such as food type and store type. They are
not calculated from invoice-to-menu COGS.

## Estimated Blended Margin Formula

```text
AVG GP COST = Σ(revenue_share_pct × platform_fee_pct) / 100
EST. NET MARGIN = 100 - AVG GP COST - EST. FOOD COST - EST. FIXED COST
```

Notes:

- `AVG GP COST` is weighted by active revenue channels only.
- `EST. FOOD COST` is an MVP benchmark/assumption.
- `EST. FIXED COST` is an MVP benchmark/assumption.
- `EST. NET MARGIN` is a preview value, not final accounting net profit.

This means the preview can show directionally useful pressure, but it should not
be presented as audited net profit.

## Risk Card Rules

### A. Over-reliance on Delivery

Inputs:

- delivery revenue share
- platform GP / commission
- walk-in or self-pickup share

Business meaning:

High delivery dependency reduces margin before ingredient costs are counted. If
a large share of revenue flows through high-commission platforms, the restaurant
has less room left for food cost, packaging, labor, rent, utilities, and profit.

### B. LPG Cost Exposure

Inputs:

- fuel-sensitive food types
- estimated net margin

Business meaning:

Fuel-sensitive menus may be exposed to LPG/diesel-related cost pressure. Menus
such as stir-fry, soups, curries, and other energy-intensive cooking styles can
be more sensitive to energy price movement than lighter-prep menu types.

### C. Self-Pickup Opportunity

Inputs:

- low walk-in/self-pickup share
- high delivery share

Business meaning:

Self-pickup has 0% platform fee, so shifting some orders from delivery platforms
to direct channels can improve margin without changing ingredient cost.

## Status Thresholds

Current MVP thresholds are heuristic and implemented in the frontend preview.
They should align conceptually with:

- `target_margin_pct`
- `warning_margin_pct`
- `risk_margin_pct`

The current preview uses simplified status bands for estimated net margin, such
as healthy / warning / critical, and applies channel-share heuristics for alert
cards. These thresholds are not yet centralized as a shared config or
deterministic backend rule.

Future work should centralize these thresholds in `docs/business_rules.md`, a
shared config, or a deterministic calculation module if the preview becomes a
formal product rule.

## UI Copy Mapping

| Thai UI copy | Business meaning |
|---|---|
| `ประเมินเบื้องต้นจากข้อมูลร้าน...` | This is a quick setup-based preview before deeper FFIA Advisor analysis. |
| `พึ่งพาเดลิเวอรี่สูงเกินไป` | Delivery platform share is high enough to create commission pressure. |
| `ต้นทุน LPG กระทบกำไร` | The restaurant has fuel-sensitive food types and estimated margin may be vulnerable. |
| `เพิ่มช่องทางรับเอง` | Walk-in/self-pickup share is low, creating an opportunity to shift orders to 0% platform-fee channels. |
| `ลดความเสี่ยง LPG` | The menu mix includes LPG/fuel-sensitive cooking patterns. |
| `ปรับ GP/ช่องทางขาย` | Channel mix or platform commission may need optimization. |
| `ปรับสัดส่วนช่องทางขาย` | Revenue share across delivery and direct channels may need rebalancing. |

## What This Preview Does NOT Do

AI Risk Profile Preview does not:

- use web search prices
- calculate true net profit
- include exact rent, labor, utilities, or other operating costs unless modeled separately
- map invoice items to menu-level COGS
- perform fuzzy ingredient matching
- perform RAG over historical invoices
- replace FFIA Advisor chat analysis
- replace deterministic business-rule tools

## Future Improvements

Planned or possible improvements:

- connect preview with invoice history
- add an operating cost module for rent, labor, utilities, and packaging
- add a deterministic margin calculator for menu-level profitability
- add fuzzy/RAG ingredient matching
- centralize thresholds in `docs/business_rules.md` or shared config
- separate preview-only assumptions from production decision rules more formally

