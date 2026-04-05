# FFIA — Agent Architecture

> Status: **W2 Complete** — LangGraph ReAct agent with Gemini 2.5 Flash, BigQuery, and Web Search live. Dark sidebar UI shipped.

---

## High-Level Architecture

```
User (Streamlit Chat UI — dark sidebar)
        │
        ▼
┌─────────────────────────────────────────┐
│           app/main.py                   │
│  Streamlit Chat + st.expander trace     │
│  Dark navy sidebar (SVG nav icons)      │
└──────────────┬──────────────────────────┘
               │ run_agent(message, history)
               ▼
┌─────────────────────────────────────────┐
│           agent/main.py                 │
│  LangGraph ReAct Agent                  │
│  Model: Gemini 2.5 Flash (Vertex AI)    │
│  Thought → Action → Observation loop    │
└──────────┬──────────────────┬───────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐  ┌──────────────────┐
│  bigquery_tool   │  │   search_tool    │
│  (SELECT only)   │  │  (DuckDuckGo)    │
│  50-row cap      │  │  no API key      │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         ▼                     ▼
  Google BigQuery          DuckDuckGo
  gcp-madt-ai              (free, no key)
  dataset: data_source
```

---

## Components

### 1. LLM Core
- **Model**: Gemini 2.5 Flash via `ChatVertexAI` (`langchain-google-vertexai`)
- **Planned migration**: `ChatGoogleGenerativeAI` (`langchain-google-genai`) per CLAUDE.md standards
- **Framework**: LangGraph `create_react_agent` — ReAct (Reason + Act) loop
- **Location**: `agent/main.py`
- **Auth**: Google Application Default Credentials (`GOOGLE_APPLICATION_CREDENTIALS` in `.env`)
- **Region**: `us-central1`
- **Temperature**: 0.1 (near-deterministic for data analysis)

### 2. Tools
| Tool | File | Description |
|---|---|---|
| `bigquery_tool` | `agent/tools/bigquery_tool.py` | Executes SELECT queries against `gcp-madt-ai.data_source` in BigQuery |
| `search_tool` | `agent/tools/search_tool.py` | Web search via DuckDuckGo — no API key required |

**Security guardrails on BigQuery tool:**
- Only `SELECT` statements accepted — mutations rejected at tool level
- Results capped at 50 rows to control cost and LLM context size

### 3. Prompts
- **System prompt**: `agent/prompts/system_prompt.txt` — defines FFIA role, available tools, Bangkok/THB context, output format
- **Tool descriptions**: docstrings on each `@tool` function — LangGraph reads these to decide when to call each tool

### 4. Data Layer
- **BigQuery**: `gcp-madt-ai.data_source` (region: `asia-southeast3`) — primary data source
- `BIGQUERY_DATASET` and `BIGQUERY_LOCATION` configurable via `.env`

### 5. User Interface
- **Framework**: Streamlit (`app/main.py`)
- **Sidebar**: Dark navy (`#0f172a`) with SVG nav icons, active/inactive states, bottom-pinned account block
- **Nav items**: Dashboard (active), Data Upload (inactive — OCR upload entry point, W3+)
- **Reasoning Transparency**: `st.expander("Agent Reasoning Trace (click to expand)")` — collapsed by default; shows tool name + observation per step
- **Disclaimer**: CSS `::after` on `[data-testid="stBottom"]` — renders directly below the pinned chat input

---

## Key Files

| File | Purpose |
|---|---|
| `agent/main.py` | LangGraph agent setup, `run_agent()` public function, `_extract_text()` Gemini content normalizer |
| `agent/tools/bigquery_tool.py` | BigQuery SQL execution tool (`@tool` decorator) |
| `agent/tools/search_tool.py` | DuckDuckGo web search tool |
| `agent/prompts/system_prompt.txt` | Agent role, tool guidance, output format |
| `app/main.py` | Streamlit chat UI — dark sidebar, metric cards, chat loop, reasoning trace |
| `app/assets/ffia_logo_design.png` | Sidebar logo (base64-embedded in HTML) |
| `requirements.txt` | Python dependencies |
| `.env` | Secrets — never committed (see `.env.example`) |

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes | Path to GCP service account JSON key |
| `GOOGLE_CLOUD_PROJECT` | Yes | GCP project ID (`gcp-madt-ai`) |
| `BIGQUERY_DATASET` | Yes | BigQuery dataset (`data_source`) |
| `BIGQUERY_LOCATION` | Yes | Dataset region (`asia-southeast3`) |
| `TAVILY_API_KEY` | No | Upgrades web search from DuckDuckGo to Tavily automatically |

---

## run_agent() Contract

```python
run_agent(user_message: str, chat_history: list = None) -> dict
```

Returns:
```python
{
    "output": str,                          # Final answer — plain string
    "intermediate_steps": [                 # Tool calls made during reasoning
        ("tool_name", "observation_text"),  # One tuple per tool invocation
        ...
    ]
}
```

`_extract_text()` normalizes Gemini 2.5 Flash's content block format (`[{'type':'text','text':'...'}]`) to a plain string before returning.

---

## Security Boundaries
- All secrets loaded from `.env` via `python-dotenv` — never hardcoded
- GCP service account JSON key excluded from git via `.gitignore` patterns
- BigQuery tool rejects any non-SELECT SQL at the tool level
- BigQuery results capped at 50 rows before passing to LLM

---

## Planned W3+ Enhancements
- [ ] `calculate_margin` tool — compute true margin per menu item using BigQuery data
- [ ] `simulate_scenario` tool — what-if oil price sensitivity analysis
- [ ] Data Upload page — OCR invoice ingestion (Claude Vision) into BigQuery
- [ ] Migrate LLM from `ChatVertexAI` to `ChatGoogleGenerativeAI` per CLAUDE.md standards
- [ ] Multi-agent: Planner → Data Agent + Margin Agent + Recommendation Agent
- [ ] RAG: Menu cost history as vector store for trend queries
- [ ] Memory: Remember restaurant profile across conversation sessions

---

*Last updated: W2 — LangGraph ReAct agent, Gemini 2.5 Flash, BigQuery + WebSearch tools, dark sidebar UI.*
