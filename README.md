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

## Current State (W2)

- **Agent**: LangGraph ReAct agent powered by Gemini 2.5 Flash (Google AI API)
- **Tools**: PostgreSQL SQL tool + DuckDuckGo web search tool — both live
- **UI**: Streamlit chat interface with dark sidebar, reasoning trace expander (collapsed by default)
- **Data**: PostgreSQL connected via `DATABASE_URL`, including saved invoice records

---

## Agent Design

> Full details in [`docs/architecture.md`](docs/architecture.md)

FFIA is an **agentic AI system** — the AI agent is the product, not a feature bolted onto a dashboard.

### What the agent does
1. Fetches today's oil price via web search (DuckDuckGo → EPPO data)
2. Queries restaurant cost and oil-price data from PostgreSQL
3. Calculates the real gross margin per menu item (including hidden fuel costs)
4. Simulates "what if oil goes up 5 baht?" scenarios
5. Recommends prioritised pricing or ingredient adjustments
6. Can use the latest saved invoice from PostgreSQL when the user asks about an invoice
7. Explains its reasoning step by step (transparent ReAct loop)

### Tools the agent uses
| Tool | File | Purpose |
|---|---|---|
| `postgres_tool` | `agent/tools/postgres_tool.py` | Execute SELECT queries against PostgreSQL with read-only guardrails |
| `search_tool` | `agent/tools/search_tool.py` | Web search via DuckDuckGo (no API key needed) |

### LLM
Gemini 2.5 Flash via Google AI API (`langchain-google-genai`) — powers the agent's ReAct reasoning loop.

---

## Repository Structure

```
agentic-ai-mcp/
├── agent/
│   ├── main.py                  # LangGraph ReAct agent + run_agent() function
│   ├── tools/
│   │   ├── postgres_tool.py     # PostgreSQL SQL tool (SELECT only)
│   │   └── search_tool.py       # DuckDuckGo web search tool
│   └── prompts/
│       └── system_prompt.txt    # Agent role, tool guidance, output format
├── app/
│   ├── main.py                  # Streamlit chat UI (dark sidebar + reasoning trace)
│   ├── utils/
│   │   └── ocr.py               # OCR extraction and JSON cleanup for invoice uploads
│   └── assets/
│       └── ffia_logo_design.png # Sidebar logo
├── data/
│   └── db.py                    # PostgreSQL connection helpers and invoice CRUD
├── docs/
│   ├── architecture.md          # Agent architecture documentation
│   └── rubric-status.md         # Weekly milestone & grading tracker
├── notebooks/                   # Exploratory notebooks
├── .env.example                 # Environment variable template (safe to commit)
├── .gitignore                   # Excludes .env, credentials, __pycache__
├── CLAUDE.md                    # Claude Code instructions for this project
├── requirements.txt             # Python dependencies
└── README.md
```

---

## Data Sources

| Source | Type | How Used |
|---|---|---|
| EPPO Fuel Prices | Public/Government | Daily oil price fetched via web search |
| PostgreSQL | Cloud Database | Restaurant cost, oil-price, and saved invoice data queried by the app and agent |
| DuckDuckGo Web Search | Free API | Real-time news and price lookups |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Google AI API key for Gemini
- PostgreSQL database accessible via connection URL

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

- Oil price data from EPPO is fetched via web search — direct API integration planned for W3.
- Some restaurant cost data is still seeded/synthetic — broader real-data integration is planned for W3+.
- Margin calculation and scenario simulation tools planned for W3.
- Multi-agent pattern (Planner + specialist agents) planned for W4+.

---

*Last updated: W2 — LangGraph ReAct agent, Gemini 2.5 Flash, dark sidebar UI, PostgreSQL + WebSearch live.*
