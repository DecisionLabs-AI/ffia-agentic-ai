def _get_main_css() -> str:
    return """
<style>
:root {
    --ffia-bg: #fffdfa;
    --ffia-bg-soft: #fff7f2;
    --ffia-surface: rgba(255, 255, 255, 0.96);
    --ffia-surface-strong: #ffffff;
    --ffia-surface-tint: #fff8f3;
    --ffia-sidebar: #ffffff;
    --ffia-sidebar-strong: #f8fafc;
    --ffia-border: #e7e5e4;
    --ffia-border-strong: #d6d3d1;
    --ffia-text: #111827;
    --ffia-text-muted: #6b7280;
    --ffia-text-soft: #9ca3af;
    --ffia-accent: #f97316;
    --ffia-accent-strong: #ea580c;
    --ffia-accent-soft: #fff7ed;
    --ffia-green: #5aaf84;
    --ffia-amber: #d97706;
    --ffia-red: #dc2626;
    --ffia-shadow: 0 24px 48px -36px rgba(17, 24, 39, 0.22);
    --ffia-shadow-soft: 0 14px 28px -24px rgba(17, 24, 39, 0.16);
    --ffia-radius-lg: 24px;
    --ffia-radius-md: 18px;
    --ffia-radius-sm: 14px;
}

[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #fffdfa 0%, #ffffff 100%) !important;
}

[data-testid="stMain"] {
    background: #f6f6f7 !important;
}

[data-testid="stMainBlockContainer"] {
    background: transparent !important;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 1.7rem !important;
    padding-bottom: 6rem !important;
    max-width: 1360px !important;
}

html, body, [class*="css"] {
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--ffia-text);
    letter-spacing: -0.02em;
    font-weight: 700;
}

p, li, label, .stCaption, .stMarkdown, .stText, .st-emotion-cache-10trblm {
    color: var(--ffia-text-muted);
}

[data-testid="stMarkdownContainer"] p {
    color: var(--ffia-text-muted);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: inherit;
}

[data-testid="stHeadingWithActionElements"] h1,
[data-testid="stHeadingWithActionElements"] h2,
[data-testid="stHeadingWithActionElements"] h3 {
    color: var(--ffia-text);
    font-weight: 760;
}

[data-testid="stDivider"] {
    margin: 1.4rem 0 !important;
}

[data-testid="stDivider"] hr {
    border-color: var(--ffia-border) !important;
}

/* ── Reusable page hero ── */
.page-hero {
    position: relative;
    overflow: hidden;
    padding: 1.6rem 1.75rem 1.7rem 1.75rem;
    border-radius: 28px;
    border: 1px solid #e4dfdb;
    background: linear-gradient(180deg, #ffffff 0%, #fff9f4 100%);
    box-shadow: 0 26px 44px -36px rgba(17, 24, 39, 0.24);
    margin-bottom: 1.05rem;
}

.page-hero::after {
    content: "";
    position: absolute;
    top: -48px;
    right: -26px;
    width: 150px;
    height: 150px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(249, 115, 22, 0.1) 0%, rgba(249, 115, 22, 0) 74%);
    pointer-events: none;
}

.page-hero__eyebrow {
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.8rem;
    margin-bottom: 0.9rem;
    border-radius: 999px;
    background: var(--ffia-accent-soft);
    border: 1px solid rgba(251, 146, 60, 0.35);
    color: var(--ffia-accent-strong);
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.page-hero h1 {
    margin: 0;
    font-size: 2.15rem;
    line-height: 1.08;
    font-weight: 750;
    color: var(--ffia-text);
}

.page-hero p {
    margin: 0.7rem 0 0;
    max-width: 760px;
    color: var(--ffia-text-muted);
    font-size: 1rem;
    line-height: 1.62;
}

.page-hero--compact {
    padding: 1.18rem 1.35rem 1.22rem 1.35rem;
    border-radius: 24px;
    margin-bottom: 0.75rem;
}

.page-hero--compact::after {
    top: -72px;
    right: -42px;
    width: 148px;
    height: 148px;
    opacity: 0.88;
}

.page-hero--login {
    box-shadow: 0 18px 34px -30px rgba(70, 101, 135, 0.34);
}

.page-hero--login h1 {
    font-size: 1.82rem;
    line-height: 1.08;
}

.page-hero--login p {
    max-width: 560px;
    margin-top: 0.55rem;
    font-size: 0.96rem;
    line-height: 1.56;
}

.page-hero--login .page-hero__eyebrow {
    margin-bottom: 0.7rem;
    padding: 0.32rem 0.72rem;
    font-size: 0.69rem;
}

.section-heading {
    margin-bottom: 0.95rem;
}

.section-heading h2 {
    margin: 0;
    color: var(--ffia-text);
    font-size: 1.16rem;
    line-height: 1.2;
    font-weight: 760;
    letter-spacing: -0.01em;
}

.section-heading p {
    margin: 0.35rem 0 0;
    color: var(--ffia-text-soft);
    font-size: 0.92rem;
    line-height: 1.55;
}

.step-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.42rem 0.86rem;
    border-radius: 999px;
    background: var(--ffia-accent-soft);
    border: 1px solid rgba(251, 146, 60, 0.35);
    color: var(--ffia-accent-strong);
    font-size: 0.79rem;
    font-weight: 700;
    margin-bottom: 0.85rem;
}

/* ── Business Setup outer stepper ── */
.setup-stepper {
    display: flex;
    align-items: center;
    gap: 0;
    margin-bottom: 1.4rem;
}
.setup-stepper-label {
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.36rem 0.9rem;
    border-radius: 999px;
    color: #94a3b8;
    background: transparent;
    white-space: nowrap;
}
.setup-stepper-label.active {
    background: var(--ffia-accent-soft);
    border: 1px solid rgba(251, 146, 60, 0.35);
    color: var(--ffia-accent-strong);
}
.setup-stepper-label.done {
    color: #64748b;
}
.setup-stepper-connector {
    flex: 1;
    height: 1px;
    background: #e2e8f0;
    margin: 0 0.4rem;
}

/* ── Sidebar shell ── */
section[data-testid="stSidebar"] {
    min-width: 280px;
    max-width: 280px;
    background: #ffffff !important;
    border-right: 1px solid #eceff3;
}
section[data-testid="stSidebar"] > div:first-child {
    background: transparent !important;
}
[data-testid="stSidebarContent"] {
    background: transparent !important;
    padding: 1.1rem 0.82rem 0.9rem 0.82rem !important;
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 0.12rem;
}

section[data-testid="stSidebar"] .stMarkdown {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

.sb-brand {
    display: flex;
    align-items: center;
    gap: 0.72rem;
    padding: 0.1rem 0.2rem 0.9rem 0.2rem;
    margin-bottom: 0.42rem;
    border-bottom: 1px solid #eff2f5;
}

.sb-brand-logo {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    overflow: hidden;
    flex-shrink: 0;
    background: #ffffff;
    border: 1px solid #eef2f6;
    box-shadow: 0 12px 24px -24px rgba(15, 23, 42, 0.35);
}

.sb-brand-copy {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
}

.sb-brand-name {
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.01em;
    color: #111827;
}

.sb-brand-subtitle {
    font-size: 0.67rem;
    line-height: 1.25;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 600;
    color: #9aa4b2;
}

.sb-brand-fallback {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(180deg, #fff7ed 0%, #ffedd5 100%);
    color: #ea580c;
    font-size: 1.05rem;
    font-weight: 800;
}

.sb-nav-item {
    margin-bottom: 0.12rem;
}

.sb-account {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.92rem 0.24rem 0.08rem 0.24rem;
    border-top: 1px solid #eef2f5;
    margin-top: auto;
}

.sb-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(180deg, #fff7ed 0%, #ffedd5 100%);
    border: 1px solid #fed7aa;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 10px 20px -22px rgba(194, 89, 24, 0.5);
}

.sb-avatar span {
    font-size: 0.74rem;
    font-weight: 700;
    color: #c2410c;
    letter-spacing: 0.03em;
}

.sb-acc-name {
    font-size: 0.84rem;
    font-weight: 700;
    color: #1f2937;
    line-height: 1.25;
}

.sb-acc-role {
    font-size: 0.74rem;
    color: #9ca3af;
    line-height: 1.2;
}

/* ── Sidebar nav buttons ── */
section[data-testid="stSidebar"] .stButton > button {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    width: 100% !important;
    min-height: 44px !important;
    padding: 0.66rem 0.9rem !important;
    border-radius: 12px !important;
    border: 1px solid transparent !important;
    background: transparent !important;
    font-size: 0.89rem !important;
    font-weight: 600 !important;
    color: #374151 !important;
    letter-spacing: 0.01em !important;
    cursor: pointer !important;
    box-shadow: none !important;
    margin-bottom: 0.1rem !important;
    text-align: left !important;
    transition: background 0.18s, border-color 0.18s, color 0.18s, transform 0.18s, box-shadow 0.18s !important;
}

section[data-testid="stSidebar"] .stButton > button p {
    text-align: left !important;
    margin: 0 !important;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    background: #fafafa !important;
    color: #111827 !important;
    border-color: #eceff3 !important;
    transform: none !important;
    box-shadow: none !important;
}

section[data-testid="stSidebar"] .stButton > button:focus {
    box-shadow: none !important;
    border-color: transparent !important;
    outline: none !important;
}

section[data-testid="stSidebar"] .stButton > button:focus-visible {
    box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.14) !important;
    border-color: rgba(251, 146, 60, 0.5) !important;
    outline: none !important;
}

/* ── Active sidebar nav item ────────────────────────────────────────────────────
   Each nav button is preceded by an empty marker div (.sb-nav-marker / .is-active).
   Streamlit renders each st.markdown() and st.button() call as adjacent sibling divs,
   so :has() bridges from the marker to the following sibling that contains the button.
   active_page parameter → is_active bool → .is-active class → CSS. No data-testid hacks.
   ────────────────────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] div:has(.sb-nav-marker.is-active) + div button {
    background: #ffedd5 !important;
    color: #c2410c !important;
    font-weight: 750 !important;
    border-color: #fdba74 !important;
    box-shadow: inset -4px 0 0 #ea580c !important;
    transform: none !important;
}

/* ── Sidebar section labels ── */
.sb-section-label {
    font-size: 0.62rem;
    font-weight: 600;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 0.8rem 0.86rem 0.36rem 0.86rem;
    margin-top: 0.15rem;
    border-top: 1px solid #eff2f5;
}

.sb-nav-disabled {
    display: flex;
    align-items: center;
    min-height: 38px;
    padding: 0.3rem 0.9rem;
    font-size: 0.84rem;
    font-weight: 500;
    color: #9ca3af;
    margin-bottom: 0.08rem;
    line-height: 1.3;
    user-select: none;
    border-radius: 14px;
}

section[data-testid="stSidebar"] [data-testid*="nav_logout"] > button {
    color: #6b7280 !important;
    font-size: 0.84rem !important;
    margin-top: 0.35rem !important;
}

section[data-testid="stSidebar"] [data-testid*="nav_logout"] {
    padding-top: 0.5rem !important;
    border-top: 1px solid #eff2f5;
}

section[data-testid="stSidebar"] [data-testid*="nav_logout"] > button:hover {
    color: #b91c1c !important;
    background: #fff5f5 !important;
    border-color: #fecaca !important;
}

/* ── Surface cards / bordered containers ── */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stForm"] {
    border-radius: var(--ffia-radius-lg) !important;
    border: 1px solid var(--ffia-border) !important;
    background: #ffffff !important;
    box-shadow: var(--ffia-shadow-soft) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    padding: 0.35rem 0.45rem !important;
}

[data-testid="stForm"] {
    padding: 0.2rem 0.2rem 0.05rem !important;
}

[data-testid="stFormSubmitButton"] {
    margin-top: 0.35rem !important;
}

/* ── Inputs / form controls ── */
div[data-baseweb="input"] > div,
div[data-baseweb="base-input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div,
[data-testid="stDateInput"] > div > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stTextInput"] > div > div {
    border-radius: 16px !important;
    border: 1px solid var(--ffia-border) !important;
    background: #ffffff !important;
    box-shadow: none !important;
}

div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea,
div[data-baseweb="select"] input {
    color: var(--ffia-text) !important;
}

div[data-baseweb="input"] > div:hover,
div[data-baseweb="base-input"] > div:hover,
div[data-baseweb="select"] > div:hover,
div[data-baseweb="textarea"] > div:hover {
    border-color: var(--ffia-border-strong) !important;
}

div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="base-input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within {
    border-color: var(--ffia-accent) !important;
    box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.16) !important;
}

[data-testid="stFileUploaderDropzone"] {
    border-radius: 22px !important;
    border: 1.5px dashed #d6d3d1 !important;
    background: linear-gradient(180deg, #ffffff 0%, #fffaf6 100%) !important;
    padding: 1.4rem !important;
}

[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--ffia-accent) !important;
    background: var(--ffia-accent-soft) !important;
}

/* ── Buttons ── */
.stButton > button,
[data-testid="stFormSubmitButton"] > button {
    min-height: 44px !important;
    border-radius: 16px !important;
    border: 1px solid var(--ffia-border) !important;
    background: #ffffff !important;
    color: var(--ffia-text) !important;
    font-weight: 650 !important;
    letter-spacing: -0.01em !important;
    box-shadow: none !important;
    transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s, background 0.18s, color 0.18s !important;
}

.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
    transform: none;
    border-color: var(--ffia-border-strong) !important;
    background: #fafafa !important;
    box-shadow: none !important;
}

.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button[kind="primary"] {
    border-color: var(--ffia-accent-strong) !important;
    background: linear-gradient(180deg, #fb923c 0%, #ea580c 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 14px 26px -18px rgba(234, 88, 12, 0.45) !important;
}

.stButton > button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
    border-color: #c2410c !important;
    background: linear-gradient(180deg, #f97316 0%, #c2410c 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 18px 30px -20px rgba(194, 65, 12, 0.52) !important;
}

.stButton > button[kind="primary"]:focus,
.stButton > button[kind="primary"]:focus-visible,
.stButton > button[kind="primary"]:active,
[data-testid="stFormSubmitButton"] > button[kind="primary"]:focus,
[data-testid="stFormSubmitButton"] > button[kind="primary"]:active {
    border-color: #c2410c !important;
    background: linear-gradient(180deg, #f97316 0%, #c2410c 100%) !important;
    color: #ffffff !important;
}

.stButton > button[kind="primary"] p,
.stButton > button[kind="primary"]:hover p,
.stButton > button[kind="primary"]:focus p,
.stButton > button[kind="primary"]:focus-visible p,
.stButton > button[kind="primary"]:active p,
[data-testid="stFormSubmitButton"] > button[kind="primary"] p,
[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover p {
    color: #ffffff !important;
}

/* ── Alerts / metrics / progress ── */
[data-testid="stAlert"] {
    border-radius: 18px !important;
    border: 1px solid var(--ffia-border) !important;
    background: #fffdfa !important;
    box-shadow: none !important;
}

[data-testid="stMetric"] {
    background: linear-gradient(180deg, #ffffff 0%, #fffaf6 100%);
    border: 1px solid var(--ffia-border);
    border-radius: 22px;
    padding: 1rem 1.2rem !important;
    box-shadow: var(--ffia-shadow-soft);
}

[data-testid="stMetricLabel"] {
    color: var(--ffia-text-muted) !important;
}

[data-testid="stMetricValue"] {
    color: var(--ffia-text) !important;
    font-weight: 780 !important;
    letter-spacing: -0.02em;
}

[data-testid="stProgressBar"] {
    height: 0.52rem !important;
    border-radius: 999px !important;
    background: #f3f4f6 !important;
}

[data-testid="stProgressBar"] > div {
    background: linear-gradient(90deg, #fb923c 0%, #ea580c 100%) !important;
    border-radius: 999px !important;
}

/* ── Tables / expanders / media ── */
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    border-radius: 20px !important;
    overflow: hidden !important;
    border: 1px solid var(--ffia-border) !important;
    box-shadow: var(--ffia-shadow-soft) !important;
    background: #ffffff !important;
}

[data-testid="stExpander"] {
    border-radius: 18px !important;
    border: 1px solid var(--ffia-border) !important;
    background: #ffffff !important;
    overflow: hidden !important;
}

[data-testid="stImage"] img {
    border-radius: 22px !important;
    border: 1px solid var(--ffia-border) !important;
    box-shadow: var(--ffia-shadow-soft) !important;
}

/* ── Chat workspace ── */
[data-testid="stChatMessage"] {
    border-radius: 20px !important;
    border: 1px solid var(--ffia-border) !important;
    background: #ffffff !important;
    box-shadow: var(--ffia-shadow-soft) !important;
    padding: 1rem 1.2rem !important;
    margin-bottom: 1.2rem !important;
    min-height: 3rem;
}

[data-testid="stBottom"] {
    background: linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,253,250,0.95) 28%, rgba(255,253,250,1) 100%) !important;
    padding: 0.85rem 0 0.65rem !important;
}

[data-testid="stChatInput"] {
    border-radius: 22px !important;
    border: 1px solid var(--ffia-border) !important;
    background: #ffffff !important;
    box-shadow: var(--ffia-shadow) !important;
}

[data-testid="stChatInput"] textarea {
    color: var(--ffia-text) !important;
}

[data-testid="stBottom"]::after {
    content: "FFIA can make mistakes. Always validate critical insights with domain experts before making decisions.";
    display: block;
    font-size: 0.72rem;
    color: #8ca0b4;
    text-align: center;
    padding: 0.45rem 1rem 0 1rem;
    line-height: 1.45;
}

/* ── Status pills ── */
.status-pills-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.7rem;
    margin: 0 0 1.2rem 0;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.48rem 0.88rem;
    border-radius: 999px;
    font-size: 0.79rem;
    font-weight: 600;
    background: rgba(241, 251, 245, 0.98);
    color: #4d9a73;
    border: 1px solid rgba(186, 225, 204, 0.94);
}

.status-pill.warn {
    background: rgba(255, 248, 239, 0.98);
    color: #c28747;
    border-color: rgba(236, 208, 169, 0.94);
}

.status-pill.info {
    background: var(--ffia-accent-soft);
    color: var(--ffia-accent-strong);
    border-color: rgba(251, 146, 60, 0.34);
}

.status-pill.error {
    background: rgba(255, 244, 244, 0.98);
    color: #c16f6f;
    border-color: rgba(237, 197, 197, 0.94);
}

.pill-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
    flex-shrink: 0;
}

/* ── Decision cards ── */
.decision-card {
    --decision-accent: rgba(249, 115, 22, 0.92);
    position: relative;
    overflow: hidden;
    height: 100%;
    background: linear-gradient(180deg, #ffffff 0%, #fffaf6 100%);
    border: 1px solid var(--ffia-border);
    border-radius: 24px;
    padding: 1.22rem 1.3rem 1.12rem 1.3rem;
    box-shadow: 0 16px 30px -26px rgba(17, 24, 39, 0.18);
    height: 100%;
}

.decision-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--decision-accent) 0%, rgba(255,255,255,0) 85%);
}

.decision-card::after {
    display: none;
}

.decision-card.warn  { --decision-accent: rgba(215, 160, 90, 0.95); }
.decision-card.risk  { --decision-accent: rgba(215, 119, 119, 0.95); }
.decision-card.ok    { --decision-accent: rgba(90, 175, 132, 0.95); }
.decision-card.muted { --decision-accent: rgba(184, 199, 214, 0.92); }

.dc-label {
    font-size: 0.72rem;
    color: #9ca3af;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.62rem;
}

.dc-value {
    font-size: 2.06rem;
    font-weight: 790;
    color: var(--ffia-text);
    line-height: 1.05;
    letter-spacing: -0.03em;
}

.dc-sub {
    font-size: 0.82rem;
    color: var(--ffia-text-soft);
    margin-top: 0.42rem;
    line-height: 1.45;
}

.dc-hint {
    display: inline-flex;
    align-items: center;
    margin-top: 0.8rem;
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    background: rgba(255, 248, 239, 0.95);
    border: 1px solid rgba(236, 208, 169, 0.86);
    font-size: 0.76rem;
    color: #c28747;
    font-weight: 700;
}

.dc-hint.ok {
    background: rgba(241, 251, 245, 0.95);
    border-color: rgba(186, 225, 204, 0.86);
    color: #4f9c74;
}

.dc-hint.info {
    background: rgba(236, 245, 255, 0.95);
    border-color: rgba(189, 210, 236, 0.86);
    color: #5a87c9;
}

.dc-hint.muted {
    background: rgba(247, 250, 253, 0.96);
    border-color: rgba(212, 222, 233, 0.92);
    color: #8ea2b6;
}

/* ── Quick action buttons ── */
.action-card > div > button {
    height: 92px !important;
    border-radius: 20px !important;
    border: 1px solid var(--ffia-border) !important;
    background: #ffffff !important;
    font-size: 0.9rem !important;
    font-weight: 650 !important;
    color: #1e293b !important;
    white-space: normal !important;
    line-height: 1.45 !important;
    box-shadow: none !important;
}

.action-card > div > button:hover {
    background: var(--ffia-accent-soft) !important;
    border-color: rgba(251, 146, 60, 0.45) !important;
    color: var(--ffia-accent-strong) !important;
    box-shadow: var(--ffia-shadow-soft) !important;
}

/* ── Prompt chips ── */
.prompt-chip > div > button {
    border-radius: 999px !important;
    border: 1px solid var(--ffia-border) !important;
    background: #ffffff !important;
    font-size: 0.81rem !important;
    font-weight: 600 !important;
    color: #6b7280 !important;
    padding: 0.38rem 0.92rem !important;
    height: auto !important;
    min-height: 36px !important;
    box-shadow: none !important;
}

.prompt-chip > div > button:hover {
    background: var(--ffia-accent-soft) !important;
    border-color: rgba(251, 146, 60, 0.45) !important;
    color: var(--ffia-accent-strong) !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0.25rem;
    border-bottom: 1px solid var(--ffia-border);
}

[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 10px 10px 0 0;
    color: var(--ffia-text-muted);
    font-weight: 600;
    border: 1px solid transparent;
}

[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: var(--ffia-text);
    background: #fafafa;
}

[data-testid="stTabs"] [aria-selected="true"] {
    color: var(--ffia-accent-strong) !important;
    border-color: var(--ffia-border) var(--ffia-border) #ffffff var(--ffia-border) !important;
    background: #ffffff !important;
}

@media (max-width: 992px) {
    .page-hero {
        padding: 1.3rem 1.2rem 1.35rem 1.2rem;
        border-radius: 24px;
    }

    .page-hero h1 {
        font-size: 1.8rem;
    }

    .page-hero--login h1 {
        font-size: 1.68rem;
    }
}

@media (max-width: 768px) {
    [data-testid="stMainBlockContainer"] {
        padding-top: 1.2rem !important;
    }

    .page-hero h1 {
        font-size: 1.55rem;
    }

    .page-hero--compact {
        padding: 1rem 1rem 1.05rem 1rem;
        margin-bottom: 0.65rem;
    }

    .page-hero--login h1 {
        font-size: 1.48rem;
    }

    .page-hero--login p {
        font-size: 0.93rem;
    }
}

/* ── FFIA AI Answer Card ────────────────────────────────────────────────────
   Scoped under .ffia-answer-card so none of these rules leak to other
   parts of the app. Each rule overrides the global p/li muted color.     */
.ffia-answer-card {
    padding: 2px 0 6px 0;
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
}

/* ── Fallback flat-card elements (non-structured answers) ── */
.ffia-answer-card .ffia-h {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: var(--ffia-accent-strong);
    margin: 22px 0 8px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--ffia-border);
    line-height: 1.4;
}
.ffia-answer-card .ffia-h:first-child { margin-top: 2px; }

.ffia-answer-card .ffia-p {
    font-size: 14.5px !important;
    line-height: 1.74 !important;
    color: var(--ffia-text) !important;
    margin: 5px 0 0 0 !important;
    padding: 0 !important;
}

.ffia-answer-card .ffia-ul {
    margin: 5px 0 0 0;
    padding-left: 0;
    list-style: none;
}

.ffia-answer-card .ffia-li {
    font-size: 14px !important;
    line-height: 1.70 !important;
    color: var(--ffia-text) !important;
    margin: 5px 0 !important;
    padding-left: 1.35em;
    position: relative;
}
.ffia-answer-card .ffia-li::before {
    content: "›";
    position: absolute;
    left: 0.15em;
    color: var(--ffia-accent-strong);
    font-weight: 800;
    font-size: 15px;
    line-height: 1.65;
}

.ffia-answer-card strong { color: var(--ffia-text) !important; font-weight: 600; }

.ffia-answer-card code {
    font-size: 13px;
    background: rgba(79, 143, 239, 0.09);
    color: var(--ffia-accent-strong);
    border-radius: 4px;
    padding: 1px 5px;
    font-family: "SF Mono", "Fira Code", monospace;
}

.ffia-answer-card .ffia-meta {
    font-size: 11.5px !important;
    color: var(--ffia-text-soft) !important;
    font-style: italic;
    margin-top: 20px;
    padding-top: 10px;
    border-top: 1px solid var(--ffia-border);
    line-height: 1.5;
}

/* ── Structured insight layout (profile / risk analysis answers) ── */

/* Main Risk hero — prominent, calm, no color noise */
.ffia-risk-hero {
    padding: 6px 0 6px 16px;
    border-left: 3px solid var(--ffia-accent-strong);
    margin-bottom: 22px;
}
.ffia-risk-hero-eyebrow {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--ffia-text-muted);
    margin-bottom: 7px;
    line-height: 1.4;
}
.ffia-risk-hero-body {
    font-size: 18px !important;
    font-weight: 700;
    color: var(--ffia-text) !important;
    line-height: 1.5 !important;
    margin: 0 !important;
    padding: 0 !important;
}
.ffia-risk-hero-body strong { color: var(--ffia-text) !important; font-weight: 800; }

/* Section — separated by space and a hairline, no background boxes */
.ffia-section {
    margin-top: 20px;
    padding-top: 18px;
    border-top: 1px solid var(--ffia-border);
}

/* Actions section — same spacing, accent title to signal "do this" */
.ffia-section--actions {
    background: none;
    border: none;
    border-top: 1px solid var(--ffia-border);
    border-radius: 0;
    padding: 18px 0 0 0;
    margin-top: 20px;
}

/* Section label — small caps only, no icon */
.ffia-section-head { margin-bottom: 10px; }
.ffia-section-title {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--ffia-text-muted);
}

/* Bullet list — used for why, evidence, and generic sections */
.ffia-blist {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 7px;
}
.ffia-bitem {
    font-size: 13.5px !important;
    color: var(--ffia-text) !important;
    line-height: 1.64 !important;
    padding-left: 1.1em;
    position: relative;
    margin: 0 !important;
}
.ffia-bitem::before {
    content: "·";
    position: absolute;
    left: 0;
    color: var(--ffia-text-muted);
    font-weight: 700;
    font-size: 17px;
    line-height: 1.38;
}
.ffia-bitem strong        { color: var(--ffia-text) !important; font-weight: 600; }
/* Inline evidence label — slightly muted, same size */
.ffia-ev-inline           { color: var(--ffia-text-muted) !important; font-weight: 600; }

/* Numbered action list — clean numbers, no boxes */
.ffia-alist {
    list-style: none;
    padding: 0;
    margin: 0;
    counter-reset: ffia-action;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.ffia-aitem {
    counter-increment: ffia-action;
    position: relative;
    padding: 0 0 0 26px;
    font-size: 13.5px !important;
    color: var(--ffia-text) !important;
    line-height: 1.60 !important;
    margin: 0 !important;
    background: none;
    border: none;
    border-radius: 0;
}
.ffia-aitem::before {
    content: counter(ffia-action);
    position: absolute;
    left: 0;
    top: 0;
    font-size: 11px;
    font-weight: 700;
    color: var(--ffia-accent-strong);
    line-height: 1.85;
    width: 16px;
    text-align: left;
}
.ffia-aitem strong { color: var(--ffia-text) !important; font-weight: 600; }
</style>
"""
