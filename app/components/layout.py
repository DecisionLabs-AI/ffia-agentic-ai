from html import escape

import streamlit as st


def _render_page_hero(
    title: str,
    subtitle: str,
    eyebrow: str | None = None,
    extra_class: str = "",
) -> None:
    """Render a premium page hero without affecting page logic."""
    _eyebrow_html = (
        f'<span class="page-hero__eyebrow">{escape(eyebrow)}</span>'
        if eyebrow else ""
    )
    _class_attr = f"page-hero {extra_class}".strip()
    st.markdown(
        f"""
<div class="{_class_attr}">
  {_eyebrow_html}
  <h1>{escape(title)}</h1>
  <p>{escape(subtitle)}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_section_header(title: str, subtitle: str | None = None) -> None:
    """Render a softer section heading used across pages."""
    _subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f"""
<div class="section-heading">
  <h2>{escape(title)}</h2>
  {_subtitle_html}
</div>
""",
        unsafe_allow_html=True,
    )
