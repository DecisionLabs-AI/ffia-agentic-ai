# =============================================================================
# FFIA — Shadow Test Runner
# Compare system_prompt.txt (stable) vs system_prompt_v3_draft.txt (v3)
# on 5 golden test cases using LLM-as-judge evaluation.
#
# Zero changes to production files.
# Run: python -m tests.shadow_runner
# Output: tests/shadow_test_report_YYYYMMDD.md
# =============================================================================

# Step 1: Path bootstrap — add project root BEFORE any agent imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Step 2: Standard library imports
import json
import os
import re
from datetime import date

# Step 3: Load .env at startup — must happen before any tool/credential reads
from dotenv import load_dotenv
load_dotenv()

# Step 4: GCP / LangChain imports
from google.oauth2 import service_account
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

# Step 5: Tool imports — all 8 production tools, same order as agent/main.py
from agent.tools.postgres_tool import (
    postgres_tool,
    set_postgres_tool_user_id,
    reset_postgres_tool_user_id,
)
from agent.tools.search_tool import search_tool
from agent.tools.oil_price_tool import oil_price_tool
from agent.tools.ingredient_price_tool import ingredient_price_tool
from agent.tools.business_rules_tool import (
    platform_floor_guard_tool,
    promo_profitability_tool,
    cogs_alert_tool,
    scenario_classifier_tool,
)

# Step 6: Reuse _extract_text from agent.main (pure function, no side effects)
from agent.main import _extract_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).parent.parent / "agent" / "prompts"
STABLE_PROMPT_PATH = PROMPTS_DIR / "system_prompt.txt"
V3_DRAFT_PROMPT_PATH = PROMPTS_DIR / "system_prompt_v3_draft.txt"

GOLDEN_TESTS = [
    {
        "id": "GT-01",
        "name": "Profile Risk",
        "query": "Based on my business profile, what is my biggest cost risk right now?",
    },
    {
        "id": "GT-02",
        "name": "Platform Viability",
        "query": "Is my Grab Food delivery still profitable? Check if I'm above or below the platform floor.",
    },
    {
        "id": "GT-03",
        "name": "Promotion Viability",
        "query": "I want to run a 20% discount on LINE MAN this weekend. Should I do it?",
    },
    {
        "id": "GT-04",
        "name": "COGS Alert",
        "query": "Chicken breast prices jumped 30% this week. How does that affect my cost structure?",
    },
    {
        "id": "GT-05",
        "name": "Scenario Strategy",
        "query": "Should I reduce reliance on delivery platforms and push more dine-in orders? What's the financial impact?",
    },
]

JUDGE_SYSTEM_PROMPT = """
You are a neutral evaluator comparing two AI system-prompt versions for FFIA,
a Bangkok restaurant cost-optimization AI assistant.

You will receive one golden test case query and two responses:
- STABLE: response from the current production prompt
- V3: response from the new condensed prompt draft

Evaluate V3 against STABLE on these 7 dimensions:

1. decision       — Same Go/No-Go, risk level, or conclusion?
2. key_number     — Same THB figure or directional financial impact?
3. actions        — At least 2 of 3 recommended actions overlap?
4. language       — English query answered in English? (language lock respected)
5. reasoning_depth— V3 maintains same analytical depth as STABLE (no shortcuts)?
6. tone           — Consultant-direct voice: decisive, not academic or hedging?
7. label_leakage  — Neither response contains leaked internal labels:
                    VERDICT, KEY NUMBER, WATCH, CRITICAL, HEALTHY,
                    COGS Alert, Platform:, Profile:, Cost:

Use exactly one of these verdict values per dimension:
  MATCH       — no meaningful difference
  MINOR_DIFF  — small wording/depth difference, same business conclusion preserved
  MAJOR_DIFF  — different conclusions, numbers, or recommended actions
  REGRESSION  — V3 is clearly worse: missing key content, wrong language,
                leaked labels, or hedging where STABLE was decisive

Return compact JSON only. No markdown fences. No line breaks inside string values. Keep reason field under 100 characters.
Exact schema:
{
  "gt_id": "<string>",
  "dimensions": {
    "decision":        "<MATCH|MINOR_DIFF|MAJOR_DIFF|REGRESSION>",
    "key_number":      "<MATCH|MINOR_DIFF|MAJOR_DIFF|REGRESSION>",
    "actions":         "<MATCH|MINOR_DIFF|MAJOR_DIFF|REGRESSION>",
    "language":        "<MATCH|MINOR_DIFF|MAJOR_DIFF|REGRESSION>",
    "reasoning_depth": "<MATCH|MINOR_DIFF|MAJOR_DIFF|REGRESSION>",
    "tone":            "<MATCH|MINOR_DIFF|MAJOR_DIFF|REGRESSION>",
    "label_leakage":   "<MATCH|MINOR_DIFF|MAJOR_DIFF|REGRESSION>"
  },
  "overall": "<MATCH|MINOR_DIFF|MAJOR_DIFF|REGRESSION>",
  "reason": "<one sentence summarizing the most important finding>"
}
"""

VERDICT_ORDER = ["MATCH", "MINOR_DIFF", "MAJOR_DIFF", "REGRESSION"]
VERDICT_EMOJI = {
    "MATCH":      "✅ MATCH",
    "MINOR_DIFF": "⚠️ MINOR",
    "MAJOR_DIFF": "❌ MAJOR",
    "REGRESSION": "❌ REGRESS",
}


def _worst_verdict(verdicts: list) -> str:
    for v in reversed(VERDICT_ORDER):
        if v in verdicts:
            return v
    return "MATCH"


# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------

def _resolve_credentials():
    # Step 7a: Replicate credential resolution from agent/main.py lines 84–91
    _creds_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if _creds_json:
        _creds_dict = json.loads(_creds_json)
        return service_account.Credentials.from_service_account_info(
            _creds_dict,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    return None  # Fall back to Application Default Credentials


def _build_fresh_agent(prompt_text: str):
    """
    Construct a fresh LangGraph ReAct agent.
    Bypasses agent/main._get_agent() singleton entirely.
    Mirrors construction block in agent/main.py lines 83–115.
    """
    credentials = _resolve_credentials()
    llm = ChatVertexAI(
        model="gemini-2.5-flash",
        project=os.getenv("GCP_PROJECT_ID"),
        location="asia-southeast1",
        credentials=credentials,
        temperature=0,
        max_output_tokens=4096,
    )
    return create_react_agent(
        model=llm,
        tools=[
            postgres_tool,
            search_tool,
            oil_price_tool,
            ingredient_price_tool,
            platform_floor_guard_tool,
            promo_profitability_tool,
            cogs_alert_tool,
            scenario_classifier_tool,
        ],
        prompt=prompt_text,
    )


def _build_judge_llm():
    """Bare ChatVertexAI for the LLM-as-judge — no tools, no agent graph."""
    credentials = _resolve_credentials()
    return ChatVertexAI(
        model="gemini-2.5-flash",
        project=os.getenv("GCP_PROJECT_ID"),
        location="asia-southeast1",
        credentials=credentials,
        temperature=0,
        max_output_tokens=4096,
    )


# ---------------------------------------------------------------------------
# Agent invocation
# ---------------------------------------------------------------------------

def _run_one_gt(agent, query: str, user_id: str) -> str:
    """
    Invoke a single agent for one golden test query.
    RLS token wraps the invoke to ensure tenant-scoped DB access.
    Returns the final text response string.
    """
    token = set_postgres_tool_user_id(user_id)
    try:
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
    except Exception as exc:
        reset_postgres_tool_user_id(token)
        return f"[AGENT ERROR: {exc}]"
    finally:
        reset_postgres_tool_user_id(token)

    # Extract final text: last AIMessage without tool_calls
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
            return _extract_text(msg.content)
    return "[NO OUTPUT]"


def _run_shadow_pair(stable_agent, v3_agent, gt: dict, user_id: str) -> dict:
    """Run one golden test against both agents and return combined result dict."""
    print(f"    [stable] invoking {gt['id']}...")
    stable_out = _run_one_gt(stable_agent, gt["query"], user_id)

    print(f"    [v3]     invoking {gt['id']}...")
    v3_out = _run_one_gt(v3_agent, gt["query"], user_id)

    return {
        "gt_id":        gt["id"],
        "gt_name":      gt["name"],
        "query":        gt["query"],
        "stable_output": stable_out,
        "v3_output":    v3_out,
    }


# ---------------------------------------------------------------------------
# LLM-as-judge
# ---------------------------------------------------------------------------

def _parse_judge_output(gt_id: str, raw_text: str) -> dict:
    """
    Parse judge JSON from raw response.
    Strips optional ```json fences before json.loads.
    Falls back to all-REGRESSION dict if parsing fails.
    """
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else raw_text.strip()

    try:
        parsed = json.loads(candidate)
        parsed["gt_id"] = gt_id
        return parsed
    except (json.JSONDecodeError, ValueError):
        dims = ["decision", "key_number", "actions", "language",
                "reasoning_depth", "tone", "label_leakage"]
        return {
            "gt_id": gt_id,
            "dimensions": {d: "REGRESSION" for d in dims},
            "overall": "REGRESSION",
            "reason": f"Judge parse error. Raw output (first 300 chars): {raw_text[:300]}",
        }


def _llm_judge(judge_llm, gt_id: str, query: str, stable_out: str, v3_out: str) -> dict:
    """
    Call the LLM judge for one GT pair.
    Returns a parsed verdict dict.
    """
    human_content = (
        f"GT ID: {gt_id}\n"
        f"Query: {query}\n\n"
        f"--- STABLE RESPONSE ---\n{stable_out}\n\n"
        f"--- V3 RESPONSE ---\n{v3_out}"
    )
    messages = [
        SystemMessage(content=JUDGE_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ]
    raw = judge_llm.invoke(messages)
    raw_text = _extract_text(raw.content)
    return _parse_judge_output(gt_id, raw_text)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

DIMS = ["decision", "key_number", "actions", "language",
        "reasoning_depth", "tone", "label_leakage"]


def _generate_report(all_results: list) -> tuple:
    """
    Build the full Markdown report.
    Returns (markdown_str, output_filepath).
    """
    today = date.today().strftime("%Y%m%d")
    report_path = str(Path(__file__).parent / f"shadow_test_report_{today}.md")

    lines = []
    lines.append(f"# FFIA Shadow Test Report — {today}\n")
    lines.append("**Comparison:** `system_prompt.txt` (stable) vs `system_prompt_v3_draft.txt` (v3)\n")
    lines.append(f"**Test cases:** {len(all_results)}\n")

    # --- Summary Table ---
    lines.append("\n## Summary Table\n")
    dim_headers = " | ".join(d.replace("_", " ").title() for d in DIMS)
    lines.append(f"| GT | Name | {dim_headers} | Overall |")
    lines.append("|" + "---|" * (len(DIMS) + 3))

    for r in all_results:
        judge = r.get("judge", {})
        dims_map = judge.get("dimensions", {})
        cells = []
        raw_verdicts = []
        for d in DIMS:
            v = dims_map.get(d, "REGRESSION")
            raw_verdicts.append(v)
            cells.append(VERDICT_EMOJI.get(v, v))
        overall = judge.get("overall", _worst_verdict(raw_verdicts))
        overall_cell = VERDICT_EMOJI.get(overall, overall)
        row = f"| {r['gt_id']} | {r['gt_name']} | " + " | ".join(cells) + f" | {overall_cell} |"
        lines.append(row)

    # --- Per-Case Sections ---
    lines.append("\n## Per-Case Details\n")
    for r in all_results:
        judge = r.get("judge", {})
        dims_map = judge.get("dimensions", {})

        lines.append(f"### {r['gt_id']} — {r['gt_name']}\n")
        lines.append(f"**Query:** `{r['query']}`\n")

        lines.append("**Stable Response (first 300 chars):**")
        lines.append("```")
        lines.append((r.get("stable_output") or "(no output)")[:300])
        lines.append("```\n")

        lines.append("**V3 Response (first 300 chars):**")
        lines.append("```")
        lines.append((r.get("v3_output") or "(no output)")[:300])
        lines.append("```\n")

        lines.append("**Dimension Verdicts:**\n")
        lines.append("| Dimension | Verdict | Overall Reason |")
        lines.append("|---|---|---|")
        for d in DIMS:
            v = dims_map.get(d, "REGRESSION")
            reason = judge.get("reason", "").replace("|", "/") if d == DIMS[0] else ""
            lines.append(f"| {d} | {VERDICT_EMOJI.get(v, v)} | {reason} |")

        overall = judge.get("overall", "?")
        overall_cell = VERDICT_EMOJI.get(overall, overall)
        lines.append(f"\n**Overall:** {overall_cell}")
        lines.append(f"\n**Judge reason:** {judge.get('reason', '')}\n")
        lines.append("---\n")

    # --- Final Verdict ---
    all_overall = [r.get("judge", {}).get("overall", "REGRESSION") for r in all_results]
    regression_count = all_overall.count("REGRESSION")
    major_count = all_overall.count("MAJOR_DIFF")

    lines.append("## Final Verdict\n")
    if regression_count == 0 and major_count == 0:
        lines.append("### ✅ v3 SAFE for controlled rollout\n")
        lines.append("All 5 golden tests pass with MATCH or MINOR_DIFF across all dimensions.\n")
    else:
        lines.append("### ❌ v3 NOT READY — minimum fixes required\n")
        lines.append("**Fix list (every non-MATCH item):**\n")
        for r in all_results:
            judge = r.get("judge", {})
            dims_map = judge.get("dimensions", {})
            for d in DIMS:
                v = dims_map.get(d, "REGRESSION")
                if v in ("MAJOR_DIFF", "REGRESSION"):
                    lines.append(
                        f"- **{r['gt_id']} / {d}** ({VERDICT_EMOJI.get(v, v)}): "
                        f"{judge.get('reason', 'see per-case section')}"
                    )
        lines.append("")

    report_text = "\n".join(lines)
    return report_text, report_path


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main():
    # Step 1: Validate required env vars
    user_id = os.getenv("SHADOW_TEST_USER_ID")
    if not user_id:
        print(
            "ERROR: SHADOW_TEST_USER_ID is not set.\n"
            "Add it to .env — it must be a real tenant user_id with data in restaurant_profiles.\n"
            "Example: SHADOW_TEST_USER_ID=admin"
        )
        sys.exit(1)

    gcp_project = os.getenv("GCP_PROJECT_ID")
    if not gcp_project:
        print("ERROR: GCP_PROJECT_ID is not set in .env")
        sys.exit(1)

    # Step 2: Load both prompt files
    if not STABLE_PROMPT_PATH.exists():
        print(f"ERROR: Stable prompt not found at {STABLE_PROMPT_PATH}")
        sys.exit(1)
    if not V3_DRAFT_PROMPT_PATH.exists():
        print(f"ERROR: v3 draft prompt not found at {V3_DRAFT_PROMPT_PATH}")
        sys.exit(1)

    stable_prompt = STABLE_PROMPT_PATH.read_text(encoding="utf-8").strip()
    v3_prompt = V3_DRAFT_PROMPT_PATH.read_text(encoding="utf-8").strip()
    print(f"Stable prompt: {len(stable_prompt.splitlines())} lines")
    print(f"v3 draft prompt: {len(v3_prompt.splitlines())} lines")

    # Step 3: Build two independent agent instances + one bare judge LLM
    print("\nBuilding stable agent...")
    stable_agent = _build_fresh_agent(stable_prompt)
    print("Building v3 agent...")
    v3_agent = _build_fresh_agent(v3_prompt)
    print("Building judge LLM...")
    judge_llm = _build_judge_llm()

    # Step 4: Run all 5 golden tests
    all_results = []
    for gt in GOLDEN_TESTS:
        print(f"\n[{gt['id']}] {gt['name']}")
        pair = _run_shadow_pair(stable_agent, v3_agent, gt, user_id)
        print(f"    [judge] evaluating {gt['id']}...")
        pair["judge"] = _llm_judge(
            judge_llm,
            pair["gt_id"],
            pair["query"],
            pair["stable_output"],
            pair["v3_output"],
        )
        overall = pair["judge"].get("overall", "?")
        print(f"    [result] {gt['id']}: {overall}")
        all_results.append(pair)

    # Step 5: Generate and write report
    report_text, report_path = _generate_report(all_results)
    Path(report_path).write_text(report_text, encoding="utf-8")
    print(f"\nReport written: {report_path}")

    # Step 6: Print console summary
    print("\n" + "=" * 50)
    print("SHADOW TEST SUMMARY")
    print("=" * 50)
    for r in all_results:
        overall = r.get("judge", {}).get("overall", "?")
        emoji = VERDICT_EMOJI.get(overall, overall)
        print(f"  {r['gt_id']} {r['gt_name']:<22} {emoji}")

    all_overall = [r.get("judge", {}).get("overall", "REGRESSION") for r in all_results]
    if not any(v in ("MAJOR_DIFF", "REGRESSION") for v in all_overall):
        print("\n✅ v3 SAFE for controlled rollout")
    else:
        print("\n❌ v3 NOT READY — see fix list in report")
    print("=" * 50)


if __name__ == "__main__":
    main()
