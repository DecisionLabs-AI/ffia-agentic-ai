# Scenario-Based Decision Strategies

This document defines scenario-based strategies used by FFIA (Fuel & Food Impact Analyzer) to recommend actions based on cost pressure, fuel price impact, and restaurant profitability.

Each scenario represents a different business condition and provides:

* trigger condition
* recommended strategy
* reasoning
* actionable steps

---

## Scenario 1: Defensive Strategy (Maintain Customer Base)

### Condition

* Fuel price increases slightly
* Net Margin remains at an acceptable level
* `Net Margin > 20%`

### Recommended Strategy

**Maintain Price**

### Reasoning

The restaurant is still operating within a safe margin range.
Maintaining current prices helps preserve customer satisfaction and market share, especially when competitors may increase prices.

### Action Plan

* Maintain current menu pricing
* Reduce non-critical expenses such as:

  * marketing spend
  * miscellaneous operational costs
* Monitor margin trend without immediate price adjustment

### Expected Outcome

* Stable customer demand
* Controlled margin reduction without customer churn

---

## Scenario 2: Balanced Strategy (Recommended)

### Condition

* Hidden costs from fuel begin to pressure profitability
* Net Margin approaches critical level
* `Net Margin between 15% – 20%`

### Recommended Strategy

**Targeted Price Adjustment**

### Reasoning

Not all menu items are affected equally by fuel-related costs.
Some items have higher exposure to:

* transportation cost
* fuel-sensitive ingredients

Adjusting only selected items allows margin recovery without impacting the entire menu.

### Action Plan

* Identify menu items with high fuel or logistics impact
* Increase price by **5–10%** only for those items
* Maintain price for unaffected menu items
* Recalculate overall Net Margin after adjustment

### Expected Outcome

* Restore overall Net Margin to a safe level
* Minimize customer resistance by avoiding full menu price increase

---

## Scenario 3: Operational Optimization Strategy

### Condition

* Fuel cost becomes a significant portion of total cost
* `Fuel cost > 20% of total cost`
  OR
* Platform GP (commission fee) exceeds break-even point

### Recommended Strategy

**Maintain Price but Optimize Operations**

### Reasoning

Increasing price in this situation may lead to permanent customer loss.
Improving operational efficiency is a more sustainable approach to protect margin.

### Action Plan

* Change ingredient suppliers to those located closer to the restaurant
  → reduce transportation cost
* Promote **Self-Pickup / Store Pickup** options
  → eliminate delivery and GP costs
* Adjust procurement cycle:

  * from daily purchasing → every other day
    → reduce logistics surcharge

### Expected Outcome

* Reduced operating cost without increasing menu price
* Improved margin through efficiency rather than pricing

---

## Scenario Selection Logic (High-Level)

The system should select the appropriate scenario based on margin and cost signals:

* If `Net Margin > 20%` → Scenario 1 (Defensive)
* If `Net Margin 15–20%` → Scenario 2 (Balanced)
* If fuel cost or GP exceeds threshold → Scenario 3 (Operational Optimization)

---

## Role of Scenarios in FFIA

These scenarios are used by the system to:

* guide AI recommendations
* simulate decision outcomes
* provide structured and explainable business advice

Each recommendation shown to the user should clearly reference:

* which scenario is triggered
* why the recommendation is given
* what action the user should take
