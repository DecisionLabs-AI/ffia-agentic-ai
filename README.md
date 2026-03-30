# FFIA — Fuel & Food Impact Analyzer for Restaurants

> **MADT 7204 Agentic-AI Project** | Team x | FFIS Optimization for Restaurants

---

## Team

| Role | Name |
|---|---|
| **IT Lead** | Kanpirom Suksawat |
| Mgmt Member | Pornphrom Rujiwatchara-oran |
| Mgmt Member | Anantaporn Lapsakkarn |
| Mgmt Member | Jantana Pattarapronpisit |
| Mgmt Member | Rapeepat Rattanapachai |

---

## Problem Statement

Oil prices in Thailand are at historic highs. For Bangkok restaurants, this crisis is not just
about cooking fuel — it silently raises costs throughout the entire supply chain:

- **Invisible Cost Transmission**: Fuel surcharges are embedded inside delivery and logistics
  fees, but restaurant owners only calculate profit based on ingredient costs. The true margin
  is always lower than they think.
- **Reactive Pricing Risk**: Without data, owners guess at menu prices. This leads to
  "selling well but losing money" — or pricing so high they lose customers.
- **Operational Blindspot**: There is no tool today that shows, in real time, how a 1 baht
  change in diesel price affects the gross margin of a specific menu item.

**FFIA solves this** by combining live EPPO oil price data with the restaurant's own menu cost
sheet, then using an AI agent to calculate true margins, simulate price scenarios, and recommend
concrete actions — with full reasoning transparency so owners can trust the output.

---

## Agent Design

> Full details in [`docs/architecture.md`](docs/architecture.md)

FFIA is an **agentic AI system** — the AI agent is the product, not a feature bolted onto a dashboard.

### What the agent does
1. Fetches today's oil price from the EPPO data source
2. Reads the restaurant's menu cost sheet (ingredients + delivery fees)
3. Calculates the real gross margin per menu item (including hidden fuel costs)
4. Simulates "what if oil goes up 5 baht?" scenarios
5. Recommends prioritised pricing or ingredient adjustments
6. Explains its reasoning step by step (transparent reasoning loop)

### Tools the agent uses
| Tool | Purpose |
|---|---|
| `get_oil_price` | Fetch latest diesel/petrol price from EPPO |
| `calculate_margin` | Compute gross margin per menu item with fuel-cost adjustment |
| `simulate_scenario` | Run what-if oil price sensitivity analysis |
| `load_menu_data` | Read and parse restaurant menu cost sheet |

### LLM
Claude Sonnet (Anthropic) — powers the agent's reasoning and recommendation loop.

---

## Data Sources

| Source | Type | URL / Endpoint | How Used |
|---|---|---|---|
| EPPO Fuel Prices | Public/Government | https://www.eppo.go.th | Daily oil price fetched by agent |
| Menu Cost Sheet | Team-Sourced / Synthetic | `/data/raw/menu_costs.csv` | Agent reads per-item ingredient + delivery costs |
| Scenario Simulation | Synthetic | `/data/scripts/generate_scenarios.py` | Sensitivity analysis for oil price changes |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- An Anthropic API key ([get one here](https://console.anthropic.com/))

### Steps

```bash
# Step 1: Clone the repository
git clone <repo-url>
cd agentic-ai-mcp

# Step 2: Create your environment file from the template
# SECURITY: Never commit the real .env file
cp .env.example .env

# Step 3: Fill in your real API keys in .env
# (open .env in your editor and replace placeholder values)

# Step 4: Create and activate a Python virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Step 5: Install dependencies
pip install -r requirements.txt

# Step 6: Run the agent UI
streamlit run app/main.py
```

---

## Vibe-Coding Tools Used

| Tool | What it was used for |
|---|---|
| Claude Code (Anthropic) | Scaffolding repo structure, writing agent tools, code review |
| [Add others as used] | |

---

## Known Limitations & Future Improvements

- **W1 (current)**: Repo structure only — agent not yet built.
- Oil price data from EPPO is updated daily, not real-time minute-by-minute.
- Menu cost sheet is currently manually entered — future: integrate with POS system.
- Delivery fee fuel surcharge is estimated (not pulled from platform API directly).

---

*Last updated: W1 — Repo structure & problem statement committed.*
