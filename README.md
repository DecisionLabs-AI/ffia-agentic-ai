# FFIA — Fuel & Food Impact Analyzer

> **MADT 7204 Vibe Coding Project** | Team 2 | Bangkok Oil Price Crisis

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

## Current State (W3)

- **Agent**: LangGraph ReAct agent powered by Gemini 2.5 Flash (Google AI API)
- **Tools**: PostgreSQL SQL tool, Bangchak oil price API tool, 4 business-rule tools (platform floor guard, promo profitability, COGS alert, scenario classifier), DuckDuckGo web search
- **UI**: Streamlit chat interface with dark sidebar, reasoning trace expander; pages for Dashboard, Data Upload (OCR), and Business Profile Settings
- **Data**: PostgreSQL connected via `DATABASE_URL` — invoices, invoice items, and restaurant profiles stored with Row-Level Security

---

## Agent Design

> Full details in [`docs/architecture.md`](docs/architecture.md)

FFIA is an **agentic AI system** — the AI agent is the product, not a feature bolted onto a dashboard.

### What the agent does
1. Fetches today's oil price live from the Bangchak Oil Price API
2. Queries restaurant cost and invoice data from PostgreSQL (RLS-enforced per user)
3. Calculates the real gross margin per menu item (including hidden fuel/platform costs)
4. Evaluates delivery platform profitability (platform floor guard — Rule L1)
5. Checks whether a planned promotion is financially viable (promo profitability — Rule L3)
6. Monitors raw material COGS changes and recommends substitutes (COGS alert — Rule L4)
7. Classifies the business situation into Scenario 1/2/3 and provides an action plan
8. Explains its reasoning step by step (transparent ReAct loop)

### Tools the agent uses
| Tool | File | Purpose |
|---|---|---|
| `oil_price_tool` | `agent/tools/oil_price_tool.py` | Live diesel/gasohol prices from Bangchak API (Thai & English aliases) |
| `postgres_tool` | `agent/tools/postgres_tool.py` | SELECT queries against PostgreSQL with RLS + 50-row cap |
| `platform_floor_guard_tool` | `agent/tools/business_rules_tool.py` | Platform cost floor check — HEALTHY/WATCH/WARNING/CRITICAL (Rule L1) |
| `promo_profitability_tool` | `agent/tools/business_rules_tool.py` | Promo viability + psychological pricing recommendation (Rule L3) |
| `cogs_alert_tool` | `agent/tools/business_rules_tool.py` | COGS impact alert + substitute ingredient map (Rule L4) |
| `scenario_classifier_tool` | `agent/tools/business_rules_tool.py` | Classify situation into Scenario 1/2/3 with action plan |
| `search_tool` | `agent/tools/search_tool.py` | Web search via DuckDuckGo (fallback for general queries) |

### LLM
Gemini 2.5 Flash via Google AI API (`langchain-google-genai`) — powers the agent's ReAct reasoning loop.

---

## Repository Structure

```
agentic-ai-mcp/
├── agent/
│   ├── main.py                      # LangGraph ReAct agent + run_agent() function
│   ├── tools/
│   │   ├── oil_price_tool.py        # Live oil price from Bangchak API
│   │   ├── business_rules_tool.py   # L1 platform guard, L3 promo, L4 COGS, scenario classifier
│   │   ├── postgres_tool.py         # PostgreSQL SELECT tool (RLS-enforced, 50-row cap)
│   │   └── search_tool.py           # DuckDuckGo web search tool
│   └── prompts/
│       └── system_prompt.txt        # Agent role, tool guidance, Bangkok/THB context, output format
├── app/
│   ├── main.py                      # Streamlit UI — Dashboard, Data Upload, Business Profile Settings
│   ├── utils/
│   │   ├── auth.py                  # PBKDF2 password verification, session helpers
│   │   └── ocr.py                   # Claude Vision invoice OCR and JSON cleanup
│   └── assets/
│       ├── ffia_logo_design.png     # Sidebar logo
│       ├── grab.png                 # Grab delivery platform icon
│       ├── lineman.png              # LINE MAN delivery platform icon
│       ├── shopeefood.png           # Shopee Food delivery platform icon
│       └── walkin.png               # Walk-in channel icon
├── data/
│   └── db.py                        # PostgreSQL helpers — invoice CRUD, restaurant profile upsert, RLS
├── docs/
│   ├── architecture.md              # Agent architecture documentation
│   ├── business_rules.md            # Margin formulas, cost thresholds, pricing rules
│   ├── scenarios.md                 # What-if scenario definitions (Scenario 1/2/3)
│   ├── data_definition.md           # Schema definitions and field meanings
│   ├── demo_script.md               # Guided demo flow and expected agent responses
│   └── rubric-status.md             # Weekly milestone & grading tracker
├── notebooks/                       # Exploratory notebooks
├── .env.example                     # Environment variable template (safe to commit)
├── .gitignore                       # Excludes .env, credentials, __pycache__
├── CLAUDE.md                        # Claude Code instructions for this project
├── requirements.txt                 # Python dependencies
└── README.md
```

---

## Data Sources

| Source | Type | How Used |
|---|---|---|
| Bangchak Oil Price API | Public/Industry | Live diesel and gasohol prices fetched by `oil_price_tool` |
| PostgreSQL (Supabase) | Cloud Database | Restaurant cost, invoice, and profile data — RLS per user tenant |
| DuckDuckGo Web Search | Free API | Real-time news and general price lookups (fallback) |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Google AI API key for Gemini (`GOOGLE_API_KEY`)
- GCP service account with Vertex AI access (`GCP_SERVICE_ACCOUNT_JSON`, `GCP_PROJECT_ID`) — for invoice OCR
- PostgreSQL database accessible via connection URL (`DATABASE_URL`)

### Steps

```bash
# Step 1: Clone the repository
git clone <repo-url>
cd agentic-ai-mcp

# Step 2: Create your environment file from the template
# SECURITY: Never commit the real .env file
cp .env.example .env

# Step 3: Fill in your runtime credentials in .env
# Required:
#   GOOGLE_API_KEY=your_gemini_api_key_here
#   DATABASE_URL=postgresql://user:password@host:5432/dbname
#   FFIA_AUTH_USERS_JSON=[{"username":"...","password_hash":"pbkdf2_sha256$...","display_name":"..."}]
#   GCP_PROJECT_ID=your-gcp-project-id
#   GCP_SERVICE_ACCOUNT_JSON=<contents of gcp-key.json as a single-line string>

# Step 4: Create and activate a Python virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Step 5: Install dependencies
pip install -r requirements.txt

# Step 6: Run the Streamlit UI
streamlit run app/main.py

# Optional: Test the agent via CLI only
python agent/main.py
```

---

## Vibe-Coding Tools Used

| Tool | What it was used for |
|---|---|
| Claude Code (Anthropic) | Repo scaffolding, agent implementation, UI design, code review |
| Codex (OpenAI) | Project review, debugging, reliability fixes, and optimization |
| Gemini 2.5 Flash (Google) | LLM powering the ReAct agent reasoning loop |
| LangChain / LangGraph | Agent framework, tool orchestration |
| Streamlit | Chat UI and reasoning trace dashboard |
| PostgreSQL | Restaurant cost and invoice data storage/querying |

---

## Known Limitations & Next Steps

- Ingredient price tool (`ingredient_price_tool`) planned for W4 — will pull MOC/Makro reference prices from PostgreSQL.
- `calculate_margin` tool — compute true net margin per menu item using invoice and profile data — planned for W4.
- `simulate_scenario` tool — what-if oil price sensitivity analysis — planned for W4.
- Multi-agent pattern (Planner → Data Agent + Margin Agent + Recommendation Agent) planned for W4+.
- RAG: menu cost history as vector store for trend queries planned for W5+.

---

*Last updated: W3 — Bangchak oil price tool, 4 business-rule tools (L1/L3/L4/Scenario Classifier), OCR invoice upload, Data Upload page, Business Profile Settings page, platform channel assets.*
