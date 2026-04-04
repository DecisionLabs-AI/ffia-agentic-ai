# FFIA — Agent Architecture

> Status: **W2 Complete** — LangGraph ReAct agent with Gemini 2.5 Flash, BigQuery, and Web Search live.

---

## High-Level Architecture

```
User (Streamlit Chat UI)
        │
        ▼
┌─────────────────────────────────────────┐
│           app/main.py                   │
│  Streamlit Chat + st.expander trace     │
│  StreamlitCallbackHandler (live trace)  │
└──────────────┬──────────────────────────┘
               │ run_agent(message, callbacks)
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
│  BigQuerySQL     │  │   WebSearch      │
│  bigquery_tool   │  │   search_tool    │
│  (SELECT only)   │  │  (DuckDuckGo)    │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         ▼                     ▼
  Google BigQuery          DuckDuckGo
  gcp-madt-ai              (free, no key)
  dataset: data_source     or Tavily
                           (if key set)
```

---

## Components

### 1. LLM Core
- **Model**: Gemini 2.5 Flash via `ChatVertexAI` (`langchain-google-vertexai`)
- **Framework**: LangGraph `create_react_agent` — ReAct (Reason + Act) loop
- **Location**: `agent/main.py`
- **Auth**: Google Application Default Credentials (`GOOGLE_APPLICATION_CREDENTIALS` in `.env`)
- **Region**: `us-central1`

### 2. Tools
| Tool | File | Description |
|---|---|---|
| `bigquery_tool` | `agent/tools/bigquery_tool.py` | Executes SELECT queries against `gcp-madt-ai.data_source` in BigQuery |
| `search_tool` | `agent/tools/search_tool.py` | Web search via DuckDuckGo (upgrades to Tavily if `TAVILY_API_KEY` is set) |

**Security guardrails on BigQuery tool:**
- Only `SELECT` statements accepted — mutations rejected
- Results capped at 50 rows to control cost and output size

### 3. Prompts
- **System prompt**: `agent/prompts/system_prompt.txt` — defines FFIA role, available tools, Bangkok/THB context, output format
- **Tool descriptions**: docstrings on each `@tool` function — LangGraph reads these to decide when to call each tool

### 4. Data Layer
- **BigQuery**: `gcp-madt-ai.data_source` (region: `asia-southeast3`) — primary data source
- `BIGQUERY_DATASET` and `BIGQUERY_LOCATION` configurable via `.env`

### 5. User Interface
- **Framework**: Streamlit (`app/main.py`)
- **Reasoning Transparency**: `StreamlitCallbackHandler` writes Thought/Action/Observation steps live into `st.expander("Agent Reasoning Trace")` — visible to user during each query
- **Fallback**: Static rendering of `intermediate_steps` from `run_agent()` result if live handler misses steps

---

## Key Files

| File | Purpose |
|---|---|
| `agent/main.py` | LangGraph agent setup and `run_agent()` public function |
| `agent/tools/bigquery_tool.py` | BigQuery SQL execution tool (`@tool` decorator) |
| `agent/tools/search_tool.py` | DuckDuckGo / Tavily web search tool |
| `agent/prompts/system_prompt.txt` | Agent role, tool guidance, output format |
| `app/main.py` | Streamlit chat UI with live reasoning trace |
| `requirements.txt` | All dependencies (LangChain 1.x, LangGraph, Vertex AI, BigQuery) |
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

## Security Boundaries
- All secrets loaded from `.env` via `python-dotenv` — never hardcoded
- GCP service account JSON key excluded from git via `.gitignore` patterns (`*-key.json`, etc.)
- BigQuery tool rejects any non-SELECT SQL — no mutations possible
- BigQuery results capped at 50 rows before passing to LLM

---

## Optional Enhancements (planned W3+)
- [ ] Add `calculate_margin` tool — compute true margin per menu item using BigQuery data
- [ ] Add `simulate_scenario` tool — what-if oil price sensitivity analysis
- [ ] Multi-agent: Planner → Data Agent + Margin Agent + Recommendation Agent
- [ ] RAG: Menu cost history as vector store for trend queries
- [ ] Memory: Remember restaurant profile across conversation sessions

---

*Last updated: W2 — LangGraph ReAct agent, Gemini 2.5 Flash, BigQuery + WebSearch tools live.*
