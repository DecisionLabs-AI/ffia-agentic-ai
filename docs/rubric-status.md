# Rubric Status Tracker

> Updated after every weekly milestone. IT Lead reference for grading self-check.

---

## Minimum Requirements

| Requirement | Status | Evidence | Week Done |
|---|---|---|---|
| LLM Core (at least 1 LLM) | ✅ Complete | Gemini 2.5 Flash via `ChatGoogleGenerativeAI` + `GOOGLE_API_KEY` in `agent/main.py` | W2 |
| Tool Use (2+ distinct tools, dynamic) | ✅ Complete | `postgres_tool` + `search_tool` in `agent/tools/` — both wired and live | W2 |
| Data Integration (real/realistic dataset) | ✅ Complete | Cloud PostgreSQL via `DATABASE_URL`; SELECT queries working | W2 |
| User Interface (not just terminal) | ✅ Complete | Streamlit Chat UI with dark sidebar, metric cards, reasoning trace | W2 |
| Reasoning Transparency (visible trace) | ✅ Complete | `st.expander("Agent Reasoning Trace")` shows tool calls + observations per turn | W2 |

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
| Agent Architecture & Technical Execution | 35% | ✅ Strong | LangGraph ReAct + Gemini 2.5 Flash (Google AI API) + 2 live tools; reasoning trace visible in UI |
| Data Integration | 20% | ✅ Complete | Cloud PostgreSQL connected via `DATABASE_URL`; SELECT guardrail enforced |
| Technical Documentation & Git Practice | 20% | ✅ Complete | README, architecture.md, rubric-status.md, CLAUDE.md all updated; .gitignore + .env.example in place |
| AI / Vibe-Coding Tool Leverage | 15% | ✅ Complete | Claude Code used for scaffolding, agent implementation, UI design; documented in README |
| Team Technical Leadership | 10% | 🔄 In Progress | W2 agent demo available for mgmt team; dark sidebar UI shipped |

---

## Weekly Checkpoint Status

| Week | Theme | Checkpoint | Status |
|---|---|---|---|
| **W1** | Discover & Align | Repo created, folder structure, problem statement committed | ✅ Complete |
| **W2** | Agent Skeleton | LangGraph ReAct agent + Gemini 2.5 Flash (Google AI API) + PostgreSQL + WebSearch + Streamlit UI with dark sidebar | ✅ Complete |
| **W3** | Tools & Data Sprint | Live demo with 2+ tools + real dataset; `calculate_margin` + `simulate_scenario` tools | ⬜ Pending |
| **W4** | UI & Integration | Full agent via UI, all reasoning steps visible, multi-tool flows | ⬜ Pending |
| **W5** | Harden & Document | README + architecture.md complete, code freeze, end-to-end tested | ⬜ Pending |
| **W6** | Final Demo & Submit | Tag v1.0, repo URL submitted, team demo recorded | ⬜ Pending |

---

## W2 Deliverables Detail

| Item | Status | Notes |
|---|---|---|
| LangGraph ReAct agent | ✅ | `agent/main.py` — `create_react_agent` with Gemini 2.5 Flash (Google AI API) |
| PostgreSQL tool | ✅ | `agent/tools/postgres_tool.py` — SELECT-only, 50-row cap |
| Web search tool | ✅ | `agent/tools/search_tool.py` — DuckDuckGo via `ddgs` |
| System prompt | ✅ | `agent/prompts/system_prompt.txt` |
| Streamlit chat UI | ✅ | `app/main.py` — dark navy sidebar, metric cards, reasoning trace |
| Dark sidebar design | ✅ | SVG nav icons, active/inactive states, bottom-pinned account block |
| Agent reasoning trace | ✅ | `st.expander` collapsed by default; shows tool calls + observations |
| CLI test mode | ✅ | `python agent/main.py` interactive REPL |

---

## Security Checklist

| Item | Status |
|---|---|
| `.gitignore` created before first commit | ✅ Done |
| `.env` is gitignored | ✅ Done |
| `.env.example` has placeholders only | ✅ Done |
| No API keys hardcoded in source files | ✅ Done |
| No service account JSON key needed — auth via `GOOGLE_API_KEY` only | ✅ Done |
| PostgreSQL tool: SELECT-only guardrail | ✅ Done |
| PostgreSQL results capped at 50 rows | ✅ Done |
| `data/raw/` files under 10MB | ✅ (no raw files yet) |

---

*Legend: ✅ Complete | 🔄 In Progress | ⬜ Pending*

*Last updated: W2 (revised) — Migrated LLM to Google AI API key and database to PostgreSQL. All minimum requirements met.*
