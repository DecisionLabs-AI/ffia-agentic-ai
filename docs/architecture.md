# FFIA — Agent Architecture

> Status: **W1 Skeleton** — will be expanded each week as the agent is built.

---

## High-Level Architecture

```
User (Streamlit UI)
        │
        ▼
  ┌─────────────────────────────┐
  │     FFIA Agent (Claude)     │  ← LLM reasoning core
  │   ReAct loop: Think → Act   │
  └────────────┬────────────────┘
               │ calls tools dynamically
       ┌───────┼──────────────┐
       ▼       ▼              ▼
  get_oil_  calculate_    simulate_
   price     margin        scenario
       │       │              │
       ▼       ▼              ▼
  EPPO API  Menu Cost     Scenario
  (live)    Sheet CSV     Engine
```

---

## Components

### 1. LLM Core
- **Model**: Claude Sonnet (`claude-sonnet-4-6`)
- **Pattern**: ReAct (Reason + Act) — agent thinks, selects a tool, acts, observes result, repeats
- **Location**: `agent/main.py`

### 2. Tools
| Tool | File | Description |
|---|---|---|
| `get_oil_price` | `agent/tools/oil_price.py` | Fetches today's diesel/petrol price from EPPO |
| `calculate_margin` | `agent/tools/margin_calculator.py` | Computes true margin per menu item |
| `simulate_scenario` | `agent/tools/scenario_simulator.py` | What-if oil price sensitivity analysis |
| `load_menu_data` | `agent/tools/menu_loader.py` | Reads menu cost CSV |

### 3. Prompts
- **System prompt**: `agent/prompts/system_prompt.txt` — defines agent role, constraints, output format
- **Tool descriptions**: inline in each tool file — critical for agent to select the right tool

### 4. Data Layer
- `data/raw/menu_costs.csv` — restaurant menu with ingredient costs and delivery fees
- `data/raw/eppo_oil_prices.csv` — cached EPPO historical prices (fallback if API is down)
- `data/scripts/generate_scenarios.py` — generates synthetic scenario data

### 5. User Interface
- **Framework**: Streamlit (`app/main.py`)
- **Reasoning Transparency**: Agent thought trace displayed in an expandable panel in UI

---

## Security Boundaries
- All API keys loaded from `.env` via `python-dotenv` — never hardcoded
- Menu cost data treated as trusted internal input
- EPPO API response validated before use (no raw pass-through to LLM prompt)
- Delivery cost data from external APIs sanitized before agent consumption

---

## Optional Enhancements (planned)
- [ ] Multi-agent: Planner → Data Agent + Margin Agent + Recommendation Agent
- [ ] RAG: Menu cost history as vector store for trend queries
- [ ] Memory: Remember restaurant profile across conversation sessions
- [ ] Agentic loop: Auto-retry with cached EPPO data if live API fails

---

*Last updated: W1 — skeleton committed. Full diagram added in W2.*
