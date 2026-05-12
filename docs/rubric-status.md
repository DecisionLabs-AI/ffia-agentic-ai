# Rubric Status Tracker

> Submission update: this tracker reflects the active Next.js + FastAPI +
> LangGraph MVP, not older Streamlit-only or planned RAG claims.

---

## Implementation Status by Rubric Area

| Rubric area | Current status | Evidence | Risk | Next step |
|---|---|---|---|---|
| Problem framing | Complete | README problem statement; `docs/business_rules.md`; `docs/scenarios.md` | None for demo | Keep demo focused on Bangkok restaurant cost decisions |
| Data source integration | Complete | PostgreSQL/Supabase via `DATABASE_URL`; `data/db.py`; dashboard/invoice/profile APIs | DB schema must exist and env vars must be configured | Verify production DB before demo |
| Agentic AI behavior | Complete | `agent/main.py` uses LangGraph ReAct + `ChatVertexAI`; `/chat` calls `run_agent()` | Broad prompts may timeout or require more data | Use prepared demo prompts |
| Tool use | Complete for active tools | Registered tools in `agent/main.py`: `postgres_tool`, `search_tool`, `oil_price_tool`, `ingredient_price_tool`, L1/L3/L4/scenario tools | Some existing tools are not registered | Demo only active registered tools |
| Business rule reasoning | Partial | `agent/tools/business_rules_tool.py` implements partial L1, L3, L4, scenario classifier | L2/L5 missing; L1/L3/L4 depend on supplied/derived inputs | Present as MVP decision-support logic |
| User interface | Complete | Next.js pages: login, dashboard, setup, cost-data, chat; OCR review/edit/save | Requires backend URL and user config | Demo via Next.js app |
| Transparency/auditability | Partial | `frontend/app/chat/page.tsx` shows lightweight tool observations in details | Not durable audit log; not hidden chain-of-thought | Present as lightweight trace |
| Deployment readiness | Partial | Target is Vercel frontend + Cloud Run backend; env docs present | No checked-in `Dockerfile` / `cloudbuild.yaml`; timeouts must be configured | Add deploy artifacts after submission if needed |
| Limitations | Complete documentation | README and architecture mark RAG/fuzzy/L2/L5 as future work | Overclaiming would confuse graders | Keep warnings visible |
| Future work | Planned | RAG, fuzzy matching, deterministic margin calculator, L2, L5 listed | Not demoable now | Move to post-MVP backlog |

---

## Minimum Requirements

| Requirement | Status | Evidence |
|---|---|---|
| LLM core | Complete | Vertex AI `ChatVertexAI` in `agent/main.py`; model configured by `FFIA_AGENT_MODEL` |
| Tool use, 2+ tools | Complete | Active agent registers 8 tools in `agent/main.py` |
| Real/realistic data integration | Complete | PostgreSQL/Supabase invoice/profile/channel data; Bangchak oil API; ingredient reference table |
| User interface | Complete | Next.js frontend in `frontend/` |
| Reasoning transparency | Partial | Chat UI shows tool observations; no persisted audit trail |
| Deployment path | Partial | Vercel + Cloud Run target documented; deploy artifacts still need hardening |

---

## Active Demo-Ready Features

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Login sandbox flow | Complete | `frontend/app/login/page.tsx`, `api/routes/login.py` | Uses localStorage user context |
| Dashboard summary | Complete | `frontend/app/dashboard/page.tsx`, `api/services/dashboard_service.py` | Uses `/dashboard-summary` |
| Business setup save/load | Complete | `frontend/app/setup/page.tsx`, `api/routes/business_setup.py` | Profile + channel mix |
| OCR invoice preview | Complete | `api/routes/invoices.py::ocr_invoice_preview`, `app/utils/ocr.py` | Requires Vertex AI config |
| OCR review/edit/save | Complete | `frontend/components/setup/InvoiceUploadStep.tsx`, `api/routes/invoices.py::save_invoice_endpoint` | Edited values are saved |
| Invoice listing / top spend | Complete | Dashboard and cost-data pages; `data/db.py` invoice helpers | Excludes flagged rows where used |
| Exclude item from analysis | Complete | `frontend/app/cost-data/page.tsx`, `data/db.py::toggle_item_exclusion` | Soft exclusion |
| AI Assistant chat endpoint | Complete | `api/routes/chat.py`, `api/services/agent_service.py`, `agent/main.py` | Uses LangGraph ReAct |
| Markdown assistant messages | Complete | `frontend/app/chat/page.tsx` with `ReactMarkdown` | Demo-ready |
| Loading animation / auto-scroll | Complete | `frontend/app/chat/page.tsx` | Demo-ready |
| Reasoning trace/details | Partial | `frontend/app/chat/page.tsx` renders returned trace | Lightweight only |

---

## Active Agent Tools

| Tool | Status | Evidence | Demo guidance |
|---|---|---|---|
| `postgres_tool` | Complete | `agent/tools/postgres_tool.py`; registered in `agent/main.py` | Demo profile/invoice questions |
| `search_tool` | Complete | `agent/tools/search_tool.py`; registered in `agent/main.py` | Use only as fallback |
| `oil_price_tool` | Complete | `agent/tools/oil_price_tool.py`; registered in `agent/main.py` | Demo oil price impact |
| `ingredient_price_tool` | Complete | `agent/tools/ingredient_price_tool.py`; registered in `agent/main.py` | Demo ingredient reference lookup if DB seeded |
| `platform_floor_guard_tool` | Partial | `agent/tools/business_rules_tool.py`; registered in `agent/main.py` | Demo with complete platform/order inputs |
| `promo_profitability_tool` | Partial | `agent/tools/business_rules_tool.py`; registered in `agent/main.py` | Demo with complete numeric promo input |
| `cogs_alert_tool` | Partial | `agent/tools/business_rules_tool.py`; registered in `agent/main.py` | Demo as simplified COGS alert |
| `scenario_classifier_tool` | Partial | `agent/tools/business_rules_tool.py`; registered in `agent/main.py` | Demo as scenario helper |

---

## Do Not Demo Yet

| Capability | Status | Why not demo |
|---|---|---|
| RAG / semantic retrieval | Planned / not wired | `rag_cost_history_tool` is not registered in the active agent |
| `invoice_embeddings` product flow | Planned / not wired | Schema helper exists, but invoices are not indexed on save |
| Fuzzy ingredient search | Planned | Product lookup uses simple `ILIKE`, not aliases or trigram matching |
| `ingredient_matching_template.csv` usage | Planned | Seed script exists, but active lookup does not use aliases |
| `pg_trgm` matching | Planned | No implementation found in active flow |
| L2 Cross-Platform Margin Arbitrage | Planned | Documented only, no active tool/API/UI |
| L5 Dynamic Delivery Radius Control | Planned | Documented only, no active tool/API/UI |
| Deterministic menu margin calculator tool | Planned | Current menu margin math is prompt-guided from user-provided numbers |

---

## Business Rules Status

| Rule | Current status | Evidence | Demo note |
|---|---|---|---|
| L1 Platform Cost Floor Guard | Partial | `platform_floor_guard_tool` in `agent/tools/business_rules_tool.py` | Demo as MVP platform floor check |
| L2 Cross-Platform Margin Arbitrage | Planned | `docs/business_rules.md` only | Do not demo yet |
| L3 Promo Profitability Guard | Partial | `promo_profitability_tool` in `agent/tools/business_rules_tool.py` | Use complete numeric input |
| L4 Raw Material COGS Alert | Partial | `cogs_alert_tool` in `agent/tools/business_rules_tool.py` | Simplified assumptions |
| L5 Dynamic Delivery Radius Control | Planned | `docs/business_rules.md` only | Do not demo yet |
| Scenario selection | Partial | `scenario_classifier_tool` | Useful helper, not full simulation engine |

---

## Recommended Demo Script

Use only stable features:

1. Login with a configured demo user.
2. Open Business Setup and confirm profile/channel mix.
3. Upload an invoice image.
4. Review/edit extracted OCR header and line items.
5. Save the reviewed invoice.
6. Open Dashboard and show invoice count, top spend, oil price, and channel/profile snapshot.
7. Open Cost Data and exclude one non-business invoice item from analysis.
8. Ask AI profile risk question, for example: "Based on my profile, what is my biggest cost risk?"
9. Ask AI platform/delivery risk question, for example: "Is my delivery channel still profitable?"
10. Ask AI promo profitability with complete numeric input, for example: "Menu price 120, cost 55, packaging 5, fuel 8, fixed cost 10, platform fee 30%, target margin 20%, discount 20 baht. Is this promo viable?"
11. Ask oil price impact question, for example: "If diesel increases by 5 baht per liter, what should I watch first?"
12. Open the chat details panel to show lightweight tool-observation trace.

---

## Stable Demo Claims

It is safe to say:

- FFIA is an MVP/prototype with a stable Next.js + FastAPI product path.
- PostgreSQL/Supabase is the source of truth for invoice/profile/channel data.
- The AI Assistant is a LangGraph ReAct agent with registered tools.
- OCR preview/edit/save works through the invoice flow.
- Dashboard and cost-data views use saved invoice data.
- Business rules L1/L3/L4 exist as partial decision-support tools.
- Trace visibility is lightweight tool observation, not hidden chain-of-thought.

Do not say:

- RAG is active in the product flow.
- Fuzzy ingredient search is implemented.
- L2 and L5 are implemented.
- FFIA has a complete deterministic menu margin engine.

---

## Next Steps After Submission

| Future work | Suggested next action |
|---|---|
| RAG | Register `rag_cost_history_tool`, index invoices after save, verify tenant filtering |
| Fuzzy matching | Use ingredient aliases and/or `pg_trgm`; update ingredient lookup flow |
| Platform GP lookup | Register or merge deterministic platform fee resolution into active tool flow |
| Menu margin calculator | Add deterministic calculator tool for user-provided menu price/cost/channel data |
| L2 | Implement cross-platform margin comparison and persistence of historical platform margin signals |
| L5 | Implement delivery radius calculation with diesel, traffic, and rain inputs |
| Deployment | Add checked-in Cloud Run deployment artifacts and deployment runbook |
| Auditability | Persist structured traces and source tags |

---

*Legend: Complete = working code wired into the user/API/agent flow; Partial = usable MVP behavior with missing deterministic coverage; Planned = documented or file exists but not active in product flow.*
