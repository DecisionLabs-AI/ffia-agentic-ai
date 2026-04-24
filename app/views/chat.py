from collections.abc import Callable
import re
import time
from concurrent.futures import ThreadPoolExecutor
from html import escape

import streamlit as st
from langgraph.errors import GraphRecursionError

from app.components.layout import _render_page_hero, _render_section_header


# Step 7a: Render AI answer as a structured insight panel.
# Profile/risk analysis answers → 4-section visual layout (hero + sections).
# All other answers (oil price, invoice queries, etc.) → fallback flat card.
def _render_ai_answer(reply: str, response_language: str | None = None) -> None:
    """Render FFIA agent answer: structured insight card or flat fallback."""

    _lang = response_language if response_language in {"en", "th"} else (
        "th" if re.search(r"[ก-๙]", reply or "") else "en"
    )
    _labels = {
        "main_risk": "ความเสี่ยงหลัก" if _lang == "th" else "Main Risk",
        "why": "ทำไมถึงเสี่ยง" if _lang == "th" else "Why This Is Risky",
        "evidence": "หลักฐานจากข้อมูลของคุณ" if _lang == "th" else "Evidence From Your Data",
        "actions": "แนวทางแก้ไข" if _lang == "th" else "Recommended Actions",
    }

    # ── Inline helpers ──────────────────────────────────────────────────────
    def _esc(t: str) -> str:
        return escape(t)

    def _inline(t: str) -> str:
        """Convert **bold** and `code` in already HTML-escaped text."""
        t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
        t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
        return t

    def _p(t: str) -> str:
        return _inline(_esc(t))

    def _is_meta(s: str) -> bool:
        sl = s.lower()
        return sl.startswith('data from:') or sl.startswith('ข้อมูลจาก:')

    def _strip_bullet(s: str) -> str:
        return s[2:] if (s.startswith('- ') or s.startswith('* ')) else s

    def _is_internal_scaffold_label(h: str | None) -> bool:
        if not h:
            return False
        _norm = re.sub(r'[^a-z0-9 ]+', '', h.lower()).strip()
        return _norm in {"verdict", "key number", "what to do"}

    # ── Parse ## headings into sections ────────────────────────────────────
    sections: list[tuple[str | None, list[str]]] = []
    cur_h: str | None = None
    cur_ls: list[str] = []

    for raw in reply.split('\n'):
        line = raw.rstrip()
        if line.startswith('## '):
            sections.append((cur_h, cur_ls))
            cur_h = line[3:].strip()
            cur_ls = []
        else:
            cur_ls.append(line)
    sections.append((cur_h, cur_ls))

    # ── Classify each section ───────────────────────────────────────────────
    def _classify(h: str | None) -> str:
        if not h:
            return 'preamble'
        hl = h.lower()
        if any(k in hl for k in ('เสี่ยงหลัก', 'main risk', 'biggest')):
            return 'main_risk'
        if any(k in hl for k in ('ทำไม', 'why', 'risky')):
            return 'why'
        if any(k in hl for k in ('หลักฐาน', 'evidence')):
            return 'evidence'
        if any(k in hl for k in ('แนวทาง', 'action', 'recommend')):
            return 'actions'
        return 'generic'

    typed = [(h, ls, _classify(h)) for h, ls in sections]
    types_found = {t for _, _, t in typed}
    is_structured = bool(types_found & {'main_risk', 'why', 'actions'})

    # ── FALLBACK: flat card for non-profile answers ─────────────────────────
    if not is_structured:
        parts = ['<div class="ffia-answer-card">']
        in_ul = False
        for heading, ls, _ in typed:
            if heading and not _is_internal_scaffold_label(heading):
                if in_ul:
                    parts.append('</ul>')
                    in_ul = False
                parts.append(f'<div class="ffia-h">{_p(heading)}</div>')
            for line in ls:
                s = line.strip()
                if not s:
                    if in_ul:
                        parts.append('</ul>')
                        in_ul = False
                    continue
                if _is_meta(s):
                    if in_ul:
                        parts.append('</ul>')
                        in_ul = False
                    parts.append(f'<div class="ffia-meta">{_esc(s)}</div>')
                elif s.startswith('- ') or s.startswith('* '):
                    if not in_ul:
                        parts.append('<ul class="ffia-ul">')
                        in_ul = True
                    parts.append(f'<li class="ffia-li">{_p(s[2:])}</li>')
                else:
                    if in_ul:
                        parts.append('</ul>')
                        in_ul = False
                    parts.append(f'<p class="ffia-p">{_p(s)}</p>')
        if in_ul:
            parts.append('</ul>')
        parts.append('</div>')
        st.markdown('\n'.join(parts), unsafe_allow_html=True)
        return

    # ── STRUCTURED layout: profile / risk analysis answers ─────────────────
    html: list[str] = ['<div class="ffia-answer-card">']
    meta_line = ''

    # Step A: pre-process — strip blank lines and extract meta from all sections
    processed: list[tuple[str | None, list[str], str]] = []
    for heading, lines, stype in typed:
        content = []
        for raw_l in lines:
            s = raw_l.strip()
            if not s:
                continue
            if _is_meta(s):
                if not meta_line:
                    meta_line = s
            else:
                content.append(s)
        processed.append((heading, content, stype))

    # Step B: sort into original display order
    # Main Risk → Why → Evidence → Recommended Actions → generic → preamble
    _DISPLAY_ORDER = {'main_risk': 0, 'why': 1, 'evidence': 2, 'actions': 3, 'generic': 4, 'preamble': 5}
    processed.sort(key=lambda x: _DISPLAY_ORDER.get(x[2], 6))

    for heading, content, stype in processed:
        if not content and stype not in ('main_risk',):
            continue

        if stype == 'main_risk':
            # Join all content lines into the hero body
            body_text = ' '.join(content)
            html.append(
                f'<div class="ffia-risk-hero">'
                f'<div class="ffia-risk-hero-eyebrow">⚠ {_labels["main_risk"]}</div>'
                f'<p class="ffia-risk-hero-body">{_p(body_text)}</p>'
                f'</div>'
            )

        elif stype == 'why':
            items = ''.join(
                f'<li class="ffia-bitem">{_p(_strip_bullet(s))}</li>'
                for s in content
            )
            title = _esc(heading) if (heading and not _is_internal_scaffold_label(heading)) else _labels["why"]
            html.append(
                f'<div class="ffia-section">'
                f'<div class="ffia-section-head"><span class="ffia-section-title">{title}</span></div>'
                f'<ul class="ffia-blist">{items}</ul>'
                f'</div>'
            )

        elif stype == 'evidence':
            # Render as annotated bullets: "Label: value" → bold inline label + text
            items = []
            for s in content:
                s = _strip_bullet(s)
                if ':' in s:
                    label, _, value = s.partition(':')
                    items.append(
                        f'<li class="ffia-bitem">'
                        f'<span class="ffia-ev-inline">{_esc(label.strip())}:</span>'
                        f' {_p(value.strip())}'
                        f'</li>'
                    )
                else:
                    items.append(f'<li class="ffia-bitem">{_p(s)}</li>')
            title = _esc(heading) if (heading and not _is_internal_scaffold_label(heading)) else _labels["evidence"]
            html.append(
                f'<div class="ffia-section">'
                f'<div class="ffia-section-head"><span class="ffia-section-title">{title}</span></div>'
                f'<ul class="ffia-blist">{"".join(items)}</ul>'
                f'</div>'
            )

        elif stype == 'actions':
            items = ''.join(
                f'<li class="ffia-aitem">{_p(_strip_bullet(s))}</li>'
                for s in content
            )
            title = _esc(heading) if (heading and not _is_internal_scaffold_label(heading)) else _labels["actions"]
            html.append(
                f'<div class="ffia-section ffia-section--actions">'
                f'<div class="ffia-section-head"><span class="ffia-section-title">{title}</span></div>'
                f'<ol class="ffia-alist">{items}</ol>'
                f'</div>'
            )

        elif stype == 'generic' and content:
            items = ''.join(
                f'<li class="ffia-bitem">{_p(_strip_bullet(s))}</li>'
                for s in content
            )
            title = _esc(heading) if (heading and not _is_internal_scaffold_label(heading)) else ''
            html.append(
                f'<div class="ffia-section">'
                + (f'<div class="ffia-section-head"><span class="ffia-section-title">{title}</span></div>' if title else '')
                + f'<ul class="ffia-blist">{items}</ul>'
                f'</div>'
            )

        elif stype == 'preamble' and content:
            for s in content:
                html.append(f'<p class="ffia-p">{_p(s)}</p>')

    if meta_line:
        html.append(f'<div class="ffia-meta">{_esc(meta_line)}</div>')

    html.append('</div>')
    st.markdown('\n'.join(html), unsafe_allow_html=True)


# Step 7b: Helper — run agent and append result to session messages
def _run_agent_turn(
    prompt: str,
    current_user: dict,
    msg_container,
    get_run_agent: Callable[[], Callable],
) -> None:
    """Append user msg, run agent, append assistant msg.
    Does NOT render st.chat_message() — all chat bubble rendering lives in the message loop.
    """
    # Step 7b-1: Append user message — the loop renders it on the next rerun
    _response_language = "th" if re.search(r"[ก-๙]", prompt or "") else "en"
    _agent_prompt = (
        "Language lock: respond entirely in English. Determine output language from the latest user message only. "
        "Ignore language in examples, tool observations, database values, prior turns, and prompt headers.\n\n"
        f"User question:\n{prompt}"
        if _response_language == "en"
        else
        "Language lock: ตอบเป็นภาษาไทยทั้งหมด โดยกำหนดภาษาจากข้อความล่าสุดของผู้ใช้เท่านั้น "
        "ให้เพิกเฉยต่อภาษาจากตัวอย่าง ผลลัพธ์เครื่องมือ ค่าจากฐานข้อมูล บทสนทนาก่อนหน้า และหัวข้อในพรอมป์ต์\n\n"
        f"คำถามผู้ใช้:\n{prompt}"
    )
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Step 7b-2: Build history (exclude the just-appended user message)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
    ]
    _language_guard = (
        "Language lock: respond entirely in English. Determine language from the latest user message only. "
        "Ignore language in examples, tool observations, database values, prior turns, and prompt headers."
        if _response_language == "en"
        else
        "Language lock: ตอบเป็นภาษาไทยทั้งหมด โดยกำหนดภาษาจากข้อความล่าสุดของผู้ใช้เท่านั้น "
        "ให้เพิกเฉยต่อภาษาจากตัวอย่าง ผลลัพธ์เครื่องมือ ค่าจากฐานข้อมูล บทสนทนาก่อนหน้า และหัวข้อในพรอมป์ต์"
    )
    history.insert(0, {"role": "system", "content": _language_guard})

    # Step 7b-3: Run agent with a temporary staged status block inside the chat workspace.
    # The final answer still renders only through the normal rerun-driven message loop.
    _loading_steps = (
        "Checking your data...",
        "Calculating cost impact...",
        "Preparing recommendation...",
    )
    _step_interval_sec = 0.9
    _poll_interval_sec = 0.1
    _run_agent = get_run_agent()

    with msg_container:
        with st.status(_loading_steps[0], expanded=True) as _status:
            _status.write(_loading_steps[0])
            _shown_steps = 1
            _next_step_at = time.monotonic() + _step_interval_sec

            with ThreadPoolExecutor(max_workers=1) as _executor:
                _future = _executor.submit(
                    _run_agent,
                    _agent_prompt,
                    history,
                    current_user_id=current_user["user_id"],
                )

                while not _future.done():
                    _now = time.monotonic()
                    if _shown_steps < len(_loading_steps) and _now >= _next_step_at:
                        _step_text = _loading_steps[_shown_steps]
                        _status.update(label=_step_text, state="running")
                        _status.write(_step_text)
                        _shown_steps += 1
                        _next_step_at = _now + _step_interval_sec
                    time.sleep(_poll_interval_sec)

                # Step 7b-3b: Catch recursion limit — return a user-friendly Thai message
                # instead of surfacing a raw traceback when the agent loops too many times.
                try:
                    result = _future.result()
                except GraphRecursionError:
                    _status.update(label="⚠️ Analysis limit reached", state="error")
                    result = {
                        "output": (
                            "ขออภัย — AI ไม่สามารถสรุปคำตอบได้ในรอบนี้ (เกินขีดจำกัดการวิเคราะห์)\n\n"
                            "ลองถามคำถามที่เจาะจงขึ้น เช่น ระบุชื่อเมนู ช่วงเวลา หรือหัวข้อที่ต้องการวิเคราะห์"
                        ),
                        "intermediate_steps": [],
                    }

    # Step 7b-4: Store steps alongside the reply so the loop can render the trace expander
    steps = result.get("intermediate_steps", [])
    reply = result.get("output", "Sorry, I could not produce an answer.")
    import logging as _logging
    _logging.getLogger(__name__).debug("[UI STORED ANSWER]\n%s", reply)
    st.session_state.messages.append({
        "role": "assistant",
        "content": reply,
        "steps": steps,
        "response_language": _response_language,
    })


# Step 8b: AI Assistant page renderer — chat-only workspace
def _render_ai_assistant_page(
    current_user: dict,
    get_run_agent: Callable[[], Callable],
):
    """Render the dedicated AI Assistant page: shortcuts, chat, and analysis history."""
    _render_page_hero(
        "AI Assistant",
        "Ask FFIA about fuel impact, invoice costs, margin risk, and pricing decisions.",
        eyebrow="AI Assistant",
    )

    # Step A: Initialize chat state before rendering prompt shortcuts/workspace.
    if "messages" not in st.session_state:
        st.session_state.messages = []
    _chat_is_active = bool(st.session_state.messages) or bool(st.session_state.get("pending_prompt"))

    st.write("")
    # Step B: Show the shortcut prompt block only before the chat becomes active.
    # This prevents an extra empty bordered card from appearing when the user
    # arrives here from a Dashboard quick action with a pending prompt.
    if not _chat_is_active:
        with st.container(border=True):
            _render_section_header(
                "Ask FFIA Agent",
                "Get cost impact analysis, pricing suggestions, and fuel-risk insights in plain language.",
            )

            _CHIPS = [
                ("⛽ ดีเซลขึ้น 5 บาท กระทบฉันแค่ไหน",    "ดีเซลขึ้น 5 บาท กระทบต้นทุนและกำไรของฉันแค่ไหน"),
                ("🛵 ช่องทางเดลิเวอรี่ยังทำกำไรไหม",       "ช่องทางเดลิเวอรี่ของฉันยังทำกำไรอยู่ไหม"),
                ("💸 โปรนี้ยังคุ้มไหม",                     "โปรโมชั่นที่ฉันจะทำยังคุ้มอยู่ไหม"),
                ("📊 ต้นทุนฉันแพงตรงไหน",                  "ต้นทุนของฉันแพงที่สุดตรงไหน"),
                ("📉 กำไรหายไปตรงไหน",                     "กำไรของฉันหายไปตรงไหน"),
                ("🧺 วัตถุดิบไหนแพงที่สุด",                 "วัตถุดิบไหนที่แพงที่สุดในเดือนนี้"),
            ]
            _chip_row1, _chip_row2 = st.columns(3), st.columns(3)
            for _ci, (_chip_label, _chip_prompt) in enumerate(_CHIPS):
                _col = _chip_row1[_ci] if _ci < 3 else _chip_row2[_ci - 3]
                with _col:
                    st.markdown('<div class="prompt-chip">', unsafe_allow_html=True)
                    if st.button(_chip_label, key=f"chip_{_ci}", use_container_width=True):
                        st.session_state["pending_prompt"] = _chip_prompt
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")

    # Step D3: Render the chat container only when the chat is active so the
    # dashboard opens at the top with no large empty workspace reserving space.
    # pending_prompt counts as active, which keeps the spinner inside the same
    # bordered chat workspace during loading.
    if _chat_is_active:
        _msg_container = st.container(height=640, border=True)
        with _msg_container:
            for _msg in st.session_state.messages:
                with st.chat_message(_msg["role"]):
                    if _msg["role"] == "assistant":
                        _steps = _msg.get("steps", [])
                        if _steps:
                            with st.expander("Agent Reasoning Trace (click to expand)", expanded=False):
                                for _i, (_tool_name, _obs) in enumerate(_steps, 1):
                                    st.markdown(f"**Step {_i} — Action:** `{_tool_name}`")
                                    if _obs:
                                        st.markdown(f"**Observation:** {str(_obs)[:500]}")
                                    st.divider()
                                st.markdown(f"**Final Answer:** {_msg['content']}")
                        _render_ai_answer(_msg["content"], _msg.get("response_language"))
                    else:
                        st.markdown(_msg["content"])
    else:
        _msg_container = st.container()

    # Step D4: Process pending prompt (from quick actions / chips)
    _pending = st.session_state.pop("pending_prompt", None)
    if _pending:
        _run_agent_turn(_pending, current_user, _msg_container, get_run_agent)
        st.rerun()

    # Step D5: Chat input
    _user_input = st.chat_input("Ask about diesel price, invoice costs, margin risk...")
    if _user_input:
        _run_agent_turn(_user_input, current_user, _msg_container, get_run_agent)
        st.rerun()

    # ── Section E: Analysis History ────────────────────────────────────────────
    _past_assistant = [
        m["content"] for m in st.session_state.messages if m["role"] == "assistant"
    ]
    if _past_assistant:
        with st.expander(f"Analysis History ({len(_past_assistant)} responses)", expanded=False):
            for _idx, _answer in enumerate(reversed(_past_assistant[-10:]), 1):
                st.markdown(f"**{_idx}.** {_answer[:300]}{'...' if len(_answer) > 300 else ''}")
                if _idx < len(_past_assistant):
                    st.divider()
