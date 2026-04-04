# Rubric Status Tracker

> Updated after every weekly milestone. IT Lead reference for grading self-check.

---

## Minimum Requirements

| Requirement | Status | Evidence | Week Done |
|---|---|---|---|
| LLM Core (at least 1 LLM) | ✅ Complete | Gemini 1.5 via `ChatVertexAI` in `agent/main.py` | W2 |
| Tool Use (2+ distinct tools, dynamic) | 🔄 In Progress | `BigQuerySQL` + `WebSearch` tools in `agent/tools/` | W2 |
| Data Integration (real/realistic dataset) | 🔄 In Progress | BigQuery `gcp-madt-ai.data_source` connected | W2 |
| User Interface (not just terminal) | ✅ Complete | Streamlit Chat UI in `app/main.py` | W2 |
| Reasoning Transparency (visible trace) | ✅ Complete | `StreamlitCallbackHandler` + `st.expander` in `app/main.py` | W2 |

---

## Optional Enhancements (extra marks)

| Enhancement | Status | Evidence | Week Done |
|---|---|---|---|
| Multi-agent pattern | ⬜ Pending | — | W4+ |
| RAG integration | ⬜ Pending | — | W4+ |
| Memory across sessions | ⬜ Pending | — | W4+ |
| Agentic loop (auto-retry) | ⬜ Pending | — | W4+ |

---

## IT Lead Grading Areas (100 pts)

| Area | Weight | Status | Notes |
|---|---|---|---|
| Agent Architecture & Technical Execution | 35% | 🔄 In Progress | LangChain ReAct + Gemini 1.5 + 2 tools wired in W2 |
| Data Integration | 20% | 🔄 In Progress | BigQuery `data_source` dataset connected via `bigquery_tool.py` |
| Technical Documentation & Git Practice | 20% | ✅ Started | README, architecture.md, .gitignore, .env.example done |
| AI / Vibe-Coding Tool Leverage | 15% | 🔄 In Progress | Claude Code used — documented in README |
| Team Technical Leadership | 10% | ⬜ Pending | Demo to mgmt team starts W2 |

---

## Weekly Checkpoint Status

| Week | Theme | Checkpoint | Status |
|---|---|---|---|
| **W1** | Discover & Align | Repo created, folder structure, problem statement committed | ✅ Complete |
| **W2** | Agent Skeleton | LangChain ReAct agent + Gemini 1.5 + BigQuery + WebSearch tools + Streamlit reasoning trace | ✅ Complete |
| **W3** | Tools & Data Sprint | Live demo with 2 tools + dataset connected | ⬜ Pending |
| **W4** | UI & Integration | Full agent via UI, reasoning steps visible | ⬜ Pending |
| **W5** | Harden & Document | README + architecture.md complete, code freeze | ⬜ Pending |
| **W6** | Final Demo & Submit | Tag v1.0, repo URL submitted | ⬜ Pending |

---

## Security Checklist

| Item | Status |
|---|---|
| `.gitignore` created before first commit | ✅ Done |
| `.env` is gitignored | ✅ Done |
| `.env.example` has placeholders only | ✅ Done |
| No API keys hardcoded in source files | ✅ Done |
| BigQuery tool: SELECT-only guardrail | ✅ Done |
| `data/raw/` files under 10MB | ✅ (no data files yet) |

---

*Legend: ✅ Complete | 🔄 In Progress | ⬜ Pending*
