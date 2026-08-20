"""PCMS-HS theme v4 — modern healthcare SaaS: soft indigo/cyan gradients, glassy
rounded cards, refined chat bubbles. Injected once via apply_theme() in app.py.
No external CSS file — everything lives in this one Python string so there is no
file-path to break.

IMPORTANT: every class name from v3 (.ipcms-panel, .ipcms-hero-card, .ipcms-tile,
.ipcms-stat-card, etc.) is preserved exactly — views/components.py and every view
file that emits these classes needs ZERO changes for this redesign to apply.
"""
import streamlit as st

_CSS = """
<style>
:root {
    /* Primary brand gradient — soft indigo to cyan, modern SaaS feel */
    --ipcms-primary: #5B6EF5;
    --ipcms-primary-2: #22C1DC;
    --ipcms-primary-dark: #3B3FA8;
    --ipcms-gradient: linear-gradient(135deg, #5B6EF5 0%, #22C1DC 100%);
    --ipcms-gradient-soft: linear-gradient(135deg, #EEF1FF 0%, #E3FBFF 100%);

    /* Kept for backward compatibility with any inline references */
    --ipcms-teal-dark: #3B3FA8;
    --ipcms-teal: #5B6EF5;
    --ipcms-teal-light: #22C1DC;
    --ipcms-mint: #E3FBFF;
    --ipcms-mint-soft: #F4F6FF;

    --ipcms-page-bg-1: #E8F4FF;
    --ipcms-page-bg-2: #CFE9FF;
    --ipcms-card-bg: #ffffff;
    --ipcms-text-dark: #1B2350;
    --ipcms-text-muted: #7C86A8;

    --ipcms-radius-lg: 22px;
    --ipcms-radius-md: 16px;
    --ipcms-radius-sm: 12px;
    --ipcms-shadow-soft: 0 6px 24px rgba(60, 70, 160, 0.10);
    --ipcms-shadow-card: 0 4px 18px rgba(60, 70, 160, 0.08);
}

.stApp {
    position: relative;
    background: linear-gradient(180deg, var(--ipcms-page-bg-1) 0%, var(--ipcms-page-bg-2) 100%);
}
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='130'%3E%3Cpath d='M0 65 H70 L82 25 L94 105 L106 50 L118 65 H320' fill='none' stroke='%235B6EF5' stroke-width='2' stroke-opacity='0.07'/%3E%3C/svg%3E");
    background-repeat: repeat;
    pointer-events: none;
    z-index: 0;
}
[data-testid="stAppViewContainer"],
section[data-testid="stSidebar"],
[data-testid="stHeader"] {
    position: relative;
    z-index: 1;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(165deg, #1E4FA8 0%, #14336E 55%, #0E2450 100%);
    width: 255px !important;
    min-width: 255px !important;
    max-width: 255px !important;
}
section[data-testid="stSidebar"] > div {
    width: 255px !important;
}
section[data-testid="stSidebar"] * {
    color: #EAF0FF !important;
}
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4 {
    color: #ffffff !important;
}

section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255, 255, 255, 0.10);
    backdrop-filter: blur(6px);
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: #EAF0FF !important;
    border-radius: var(--ipcms-radius-sm);
    text-align: left;
    justify-content: flex-start;
    padding: 0.65rem 1rem;
    font-weight: 600;
    margin-bottom: 0.4rem;
    width: 100%;
    box-shadow: none;
    transition: background 0.15s ease, transform 0.15s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.22);
    transform: translateX(2px);
    box-shadow: none;
}

.ipcms-brand-box {
    background: rgba(255, 255, 255, 0.12);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: var(--ipcms-radius-md);
    padding: 0.9rem 1rem;
    margin-bottom: 1.2rem;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.ipcms-brand-box .icon {
    background: white;
    background-image: var(--ipcms-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    background-color: white;
    border-radius: 10px;
    width: 34px;
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    flex-shrink: 0;
}
.ipcms-brand-box .name {
    font-weight: 800;
    font-size: 0.95rem;
    color: white !important;
    line-height: 1.1;
}
.ipcms-brand-box .tagline {
    font-size: 0.68rem;
    color: #D6E0FF !important;
    line-height: 1.2;
}

.ipcms-user-box {
    background: rgba(255, 255, 255, 0.10);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: var(--ipcms-radius-sm);
    padding: 0.7rem 0.9rem;
    margin-bottom: 1.1rem;
}
.ipcms-user-box .name {
    font-weight: 700;
    color: white !important;
    font-size: 0.95rem;
}
.ipcms-user-box .role {
    font-size: 0.75rem;
    color: #D6E0FF !important;
}

/* ---------- Main content ---------- */
h1, h2, h3 {
    color: var(--ipcms-text-dark);
    letter-spacing: -0.01em;
}

/* Greeting header — "Good Morning, Mr. X" style */
.ipcms-greeting-card {
    background: var(--ipcms-card-bg);
    border-radius: var(--ipcms-radius-lg);
    padding: 1.4rem 1.7rem;
    box-shadow: var(--ipcms-shadow-soft);
    margin-bottom: 1.2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid rgba(91, 110, 245, 0.06);
}
.ipcms-greeting-card .greeting {
    font-size: 0.95rem;
    font-weight: 700;
    background: var(--ipcms-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    margin-bottom: 0.15rem;
}
.ipcms-greeting-card .name {
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--ipcms-text-dark);
}
.ipcms-greeting-card .sub {
    font-size: 0.9rem;
    color: var(--ipcms-primary-dark);
    font-weight: 600;
    margin-top: 0.2rem;
}
.ipcms-greeting-bell {
    background: var(--ipcms-gradient-soft);
    border-radius: 50%;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    flex-shrink: 0;
    box-shadow: var(--ipcms-shadow-card);
}

/* Old page-header card kept for admin/doctor portals */
.ipcms-header-card {
    background: var(--ipcms-card-bg);
    border-radius: var(--ipcms-radius-lg);
    padding: 1.4rem 1.7rem;
    box-shadow: var(--ipcms-shadow-soft);
    margin-bottom: 1.2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid rgba(91, 110, 245, 0.06);
}
.ipcms-header-card .title {
    font-size: 1.55rem;
    font-weight: 800;
    color: var(--ipcms-text-dark);
}
.ipcms-header-card .subtitle {
    color: var(--ipcms-text-muted);
    font-size: 0.9rem;
    margin-top: 0.15rem;
}
.ipcms-header-badge {
    background: var(--ipcms-gradient);
    color: white;
    border-radius: 12px;
    padding: 0.5rem 1rem;
    font-weight: 700;
    font-size: 0.85rem;
    box-shadow: 0 4px 14px rgba(91, 110, 245, 0.28);
}

/* Big hero action card — "Book an Appointment" */
.ipcms-hero-card {
    background: var(--ipcms-card-bg);
    border-radius: var(--ipcms-radius-lg);
    padding: 1.6rem 1.7rem;
    box-shadow: var(--ipcms-shadow-soft);
    margin-bottom: 1rem;
    border: 1px solid rgba(91, 110, 245, 0.06);
}
.ipcms-hero-card .hero-title {
    font-size: 1.18rem;
    font-weight: 800;
    color: var(--ipcms-text-dark);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.ipcms-hero-icon {
    background: var(--ipcms-gradient-soft);
    border-radius: 14px;
    width: 46px;
    height: 46px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.35rem;
    box-shadow: var(--ipcms-shadow-card);
}

/* Small tiles — "Book Lab Tests" / "Instant Consult" */
.ipcms-tile {
    background: var(--ipcms-card-bg);
    border-radius: var(--ipcms-radius-md);
    padding: 1.15rem 1.25rem;
    box-shadow: var(--ipcms-shadow-card);
    text-align: left;
    height: 100%;
    border: 1px solid rgba(91, 110, 245, 0.06);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.ipcms-tile:hover {
    transform: translateY(-2px);
    box-shadow: var(--ipcms-shadow-soft);
}
.ipcms-tile .tile-icon {
    background: var(--ipcms-gradient-soft);
    border-radius: 12px;
    width: 42px;
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    margin-bottom: 0.65rem;
}
.ipcms-tile .tile-label {
    font-weight: 800;
    color: var(--ipcms-text-dark);
    font-size: 0.95rem;
    line-height: 1.2;
}

/* Home healthcare services panel */
.ipcms-services-panel {
    background: var(--ipcms-gradient-soft);
    border-radius: var(--ipcms-radius-lg);
    padding: 1.3rem 1.5rem;
    margin-bottom: 1rem;
}
.ipcms-services-panel .panel-title {
    font-weight: 800;
    color: var(--ipcms-primary-dark);
    font-size: 1rem;
    margin-bottom: 0.9rem;
}
.ipcms-service-icon {
    background: white;
    border-radius: 16px;
    width: 58px;
    height: 58px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.55rem;
    margin: 0 auto 0.5rem auto;
    box-shadow: var(--ipcms-shadow-card);
    transition: transform 0.15s ease;
}
.ipcms-service-icon:hover {
    transform: scale(1.06);
}
.ipcms-service-label {
    text-align: center;
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--ipcms-primary-dark);
}

/* Doctor search result row */
.ipcms-doctor-row {
    background: var(--ipcms-gradient-soft);
    border-radius: var(--ipcms-radius-md);
    padding: 0.85rem 1.05rem;
    margin-top: 0.6rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.ipcms-doctor-row .dname {
    font-weight: 800;
    color: var(--ipcms-text-dark);
    font-size: 0.95rem;
}
.ipcms-doctor-row .dmeta {
    font-size: 0.8rem;
    color: var(--ipcms-text-muted);
}
.ipcms-doctor-row .dbadge {
    background: var(--ipcms-gradient);
    color: white;
    font-weight: 700;
    font-size: 0.75rem;
    border-radius: 9px;
    padding: 0.35rem 0.75rem;
    white-space: nowrap;
}

/* Generic white content panel */
.ipcms-panel {
    background: var(--ipcms-card-bg);
    border-radius: var(--ipcms-radius-md);
    padding: 1.25rem 1.45rem;
    box-shadow: var(--ipcms-shadow-card);
    margin-bottom: 1rem;
    border: 1px solid rgba(91, 110, 245, 0.06);
}
.ipcms-panel .panel-label {
    font-size: 0.85rem;
    color: var(--ipcms-text-muted);
    font-weight: 600;
    margin-bottom: 0.4rem;
}
.ipcms-panel .panel-empty {
    color: #A6AFCB;
    font-size: 0.9rem;
}
.ipcms-panel .panel-title {
    font-size: 1.28rem;
    font-weight: 800;
    color: var(--ipcms-text-dark);
    margin-top: 0.2rem;
}
.ipcms-panel .mini-stats {
    display: flex;
    gap: 2rem;
    margin-top: 1rem;
}
.ipcms-panel .mini-stats .k {
    font-size: 0.78rem;
    color: var(--ipcms-text-muted);
    font-weight: 600;
}
.ipcms-panel .mini-stats .v {
    font-size: 1.3rem;
    font-weight: 800;
    background: var(--ipcms-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

/* Buttons in main content */
.stButton > button {
    background: var(--ipcms-gradient);
    color: white;
    border: none;
    border-radius: var(--ipcms-radius-sm);
    padding: 0.55rem 1.3rem;
    font-weight: 600;
    box-shadow: 0 4px 14px rgba(91, 110, 245, 0.22);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.stButton > button:hover {
    box-shadow: 0 8px 22px rgba(91, 110, 245, 0.34);
    color: white;
    transform: translateY(-1px);
}
.stButton > button:disabled {
    background: #E2E6F5;
    color: #A6AFCB;
    box-shadow: none;
}

/* Text input styling (search boxes etc.) */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea textarea,
.stSelectbox > div > div {
    border-radius: var(--ipcms-radius-sm) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    color: var(--ipcms-text-dark);
}
.stTabs [aria-selected="true"] {
    color: var(--ipcms-primary) !important;
    border-bottom-color: var(--ipcms-primary) !important;
}

[data-testid="stMetric"] {
    background: white;
    border-radius: var(--ipcms-radius-md);
    padding: 1rem 1.2rem;
    box-shadow: var(--ipcms-shadow-card);
    border: 1px solid rgba(91, 110, 245, 0.06);
}

/* Gradient/light-fill stat card (views/components.py render_stat_card) */
.ipcms-stat-card {
    border-radius: var(--ipcms-radius-md);
    padding: 1.15rem 1.35rem;
    min-height: 100px;
    box-shadow: var(--ipcms-shadow-soft);
}
.ipcms-stat-card .label {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--ipcms-primary-dark);
}
.ipcms-stat-card .value {
    font-size: 2.15rem;
    font-weight: 800;
    margin-top: 0.2rem;
    color: var(--ipcms-text-dark);
}

/* Live vitals card */
.ipcms-vitals-wrap {
    background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='220' height='90'%3E%3Cpath d='M0 45 H50 L60 15 L70 80 L80 30 L90 45 H220' fill='none' stroke='%23FF6B81' stroke-width='2.5' stroke-opacity='0.4'/%3E%3C/svg%3E"),
        var(--ipcms-gradient-soft);
    background-repeat: repeat-x, no-repeat;
    background-position: bottom, center;
    background-size: 220px 90px, cover;
    border-radius: var(--ipcms-radius-lg);
    padding: 1.85rem;
    box-shadow: var(--ipcms-shadow-soft);
}
.ipcms-vitals-title {
    letter-spacing: 0.12em;
    font-size: 0.8rem;
    font-weight: 800;
    color: var(--ipcms-primary);
    margin-bottom: 0.8rem;
}
.ipcms-vitals-pill {
    background: white;
    border-radius: var(--ipcms-radius-sm);
    padding: 0.7rem 1rem;
    box-shadow: var(--ipcms-shadow-card);
    margin-bottom: 0.7rem;
}
.ipcms-vitals-pill .k {
    font-size: 0.75rem;
    color: var(--ipcms-text-muted);
    font-weight: 600;
}
.ipcms-vitals-pill .v {
    font-size: 1.25rem;
    font-weight: 800;
    color: var(--ipcms-text-dark);
}

/* ---------- Chat (SmartCare AI) ---------- */
[data-testid="stChatMessage"] {
    background: var(--ipcms-card-bg);
    border-radius: var(--ipcms-radius-md);
    box-shadow: var(--ipcms-shadow-card);
    border: 1px solid rgba(91, 110, 245, 0.06);
    padding: 0.3rem 0.5rem;
    margin-bottom: 0.6rem;
}

/* Compact file uploader for the chat's inline attach control — Streamlit's
   default is a full drag-and-drop box with verbose instructions, which doesn't
   fit in a narrow column beside the message input. Shrinks it down to roughly
   button-sized and hides the "Drag and drop files here / Limit 200MB..." text,
   keeping just the Browse button. */
[data-testid="stFileUploader"] {
    padding: 0 !important;
}
[data-testid="stFileUploaderDropzone"] {
    padding: 0.3rem !important;
    min-height: unset !important;
    flex-direction: column !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}
[data-testid="stFileUploaderDropzone"] small {
    display: none !important;
}
[data-testid="stFileUploaderDropzone"] button {
    padding: 0.55rem 0.4rem !important;
    font-size: 0.78rem !important;
    width: 100%;
}

/* ---------- Pharmacy: premium product cards, filter pills, cart ---------- */
.ipcms-med-card {
    background: var(--ipcms-card-bg);
    border-radius: var(--ipcms-radius-md);
    padding: 1.2rem 1.3rem 1rem;
    margin-bottom: 0.7rem;
    box-shadow: var(--ipcms-shadow-card);
    border: 1px solid rgba(91, 110, 245, 0.07);
    transition: transform 0.16s ease, box-shadow 0.16s ease;
    position: relative;
    overflow: hidden;
}
.ipcms-med-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--ipcms-shadow-soft);
}
.ipcms-med-card .med-visual-wrap {
    background: var(--ipcms-gradient-soft);
    border-radius: 14px;
    height: 96px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 0.75rem;
    overflow: hidden;
}
.ipcms-med-card .med-visual-wrap img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    padding: 0.4rem;
}
.ipcms-med-card .med-visual-wrap .med-emoji {
    font-size: 2.1rem;
}
.ipcms-med-card .med-price-badge {
    position: absolute;
    top: 0.9rem;
    right: 0.9rem;
    background: var(--ipcms-gradient);
    color: white;
    border-radius: 9px;
    padding: 0.28rem 0.65rem;
    font-weight: 800;
    font-size: 0.82rem;
    box-shadow: 0 3px 10px rgba(91, 110, 245, 0.30);
}
.ipcms-med-card .med-name {
    font-weight: 800;
    font-size: 1.02rem;
    color: var(--ipcms-text-dark);
    line-height: 1.25;
}
.ipcms-med-card .med-category-pill {
    display: inline-block;
    background: var(--ipcms-gradient-soft);
    color: var(--ipcms-primary-dark);
    font-weight: 700;
    font-size: 0.72rem;
    border-radius: 7px;
    padding: 0.18rem 0.5rem;
    margin-top: 0.35rem;
}
.ipcms-med-card .med-desc {
    color: var(--ipcms-text-muted);
    font-size: 0.82rem;
    margin-top: 0.4rem;
    min-height: 2.2em;
    line-height: 1.35;
}
.ipcms-med-card .med-stock-ok {
    color: #1FA37A;
    font-size: 0.78rem;
    font-weight: 700;
    margin-top: 0.45rem;
}
.ipcms-med-card .med-stock-low {
    color: #E08B1F;
    font-size: 0.78rem;
    font-weight: 700;
    margin-top: 0.45rem;
}
.ipcms-med-card .med-stock-out {
    color: #D14F5A;
    font-size: 0.78rem;
    font-weight: 700;
    margin-top: 0.45rem;
}


/* Cart line item */
.ipcms-cart-row {
    background: var(--ipcms-card-bg);
    border-radius: var(--ipcms-radius-sm);
    padding: 0.7rem 1rem;
    margin-bottom: 0.5rem;
    box-shadow: var(--ipcms-shadow-card);
    border: 1px solid rgba(91, 110, 245, 0.06);
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.ipcms-cart-row .cart-item-name {
    font-weight: 700;
    color: var(--ipcms-text-dark);
    font-size: 0.92rem;
}
.ipcms-cart-row .cart-item-meta {
    color: var(--ipcms-text-muted);
    font-size: 0.8rem;
}
.ipcms-cart-row .cart-item-total {
    font-weight: 800;
    color: var(--ipcms-primary-dark);
    font-size: 0.95rem;
    white-space: nowrap;
}

/* Cart summary / checkout bar */
.ipcms-cart-summary {
    background: var(--ipcms-gradient);
    border-radius: var(--ipcms-radius-md);
    padding: 1.1rem 1.4rem;
    margin-top: 0.6rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 8px 22px rgba(91, 110, 245, 0.28);
}
.ipcms-cart-summary .cart-total-label {
    color: #E6EAFF;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.04em;
}
.ipcms-cart-summary .cart-total-value {
    color: white;
    font-size: 1.6rem;
    font-weight: 900;
}

/* ---------- Clean alert messages ---------- */
[data-testid="stAlert"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0.15rem 0 !important;
}
[data-testid="stAlertContentSuccess"],
[data-testid="stAlertContentError"],
[data-testid="stAlertContentWarning"],
[data-testid="stAlertContentInfo"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
}
[data-testid="stAlertContentSuccess"] p,
[data-testid="stAlertContentError"] p,
[data-testid="stAlertContentWarning"] p,
[data-testid="stAlertContentInfo"] p {
    color: #FFFFFF !important;
    font-weight: 800 !important;
    font-size: 1.05rem !important;
    text-shadow: 0 2px 8px rgba(8, 14, 50, 0.45);
    margin: 0 !important;
}
[data-testid="stAlertContentSuccess"] svg,
[data-testid="stAlertContentError"] svg,
[data-testid="stAlertContentWarning"] svg,
[data-testid="stAlertContentInfo"] svg {
    color: #FFFFFF !important;
    fill: #FFFFFF !important;
}

/* Expanders */
.streamlit-expanderHeader, [data-testid="stExpander"] {
    border-radius: var(--ipcms-radius-sm) !important;
}
[data-testid="stExpander"] {
    box-shadow: var(--ipcms-shadow-card);
    border: 1px solid rgba(91, 110, 245, 0.06) !important;
}
</style>
"""


def apply_theme():
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Auth page (login / register) — call in ADDITION to apply_theme(), only from
# render_auth_view(). Premium abstract look: soft gradient-mesh background (CSS
# radial-gradients — no discrete shapes, so it stays crisp at any screen size,
# unlike a stretched illustration) plus a fine dot-grid texture and one thin
# ECG signature line. Streamlit's own st.form() wrapper becomes the white
# centered card, so no fragile "wrap a widget in a div" tricks are needed.
_AUTH_CSS = """
<style>
.stApp {
    background:
        radial-gradient(circle at 15% 15%, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0) 32%),
        radial-gradient(circle at 88% 12%, rgba(92,230,214,0.32) 0%, rgba(92,230,214,0) 38%),
        radial-gradient(circle at 82% 88%, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 32%),
        radial-gradient(circle at 8% 85%, rgba(59,63,168,0.55) 0%, rgba(59,63,168,0) 38%),
        linear-gradient(135deg, #2E3192 0%, #1BA9C7 100%) !important;
}
.stApp::before {
    display: none !important;
}

/* Fine dot-grid texture — a subtle premium-tech feel, no literal imagery */
.auth-hospital-bg {
    position: fixed;
    inset: 0;
    z-index: 0;
    background-image: radial-gradient(rgba(255, 255, 255, 0.16) 1px, transparent 1.6px);
    background-size: 26px 26px;
    pointer-events: none;
}
/* A few thin ECG lines at different heights/opacities as a tasteful signature
   accent — not one big illustration, several quiet "heartbeat monitor" traces. */
.auth-hospital-bg::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    bottom: 0;
    background-image:
        url("data:image/svg+xml,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20width%3D'300'%20height%3D'60'%3E%3Cpath%20d%3D'M0%2030%20H110%20L122%2010%20L134%2050%20L146%2025%20L158%2030%20H300'%20fill%3D'none'%20stroke%3D'%23FFFFFF'%20stroke-width%3D'2'%20stroke-opacity%3D'0.55'%2F%3E%3C%2Fsvg%3E"),
        url("data:image/svg+xml,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20width%3D'300'%20height%3D'60'%3E%3Cpath%20d%3D'M0%2030%20H110%20L122%2010%20L134%2050%20L146%2025%20L158%2030%20H300'%20fill%3D'none'%20stroke%3D'%23FFFFFF'%20stroke-width%3D'2'%20stroke-opacity%3D'0.32'%2F%3E%3C%2Fsvg%3E"),
        url("data:image/svg+xml,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20width%3D'300'%20height%3D'60'%3E%3Cpath%20d%3D'M0%2030%20H110%20L122%2010%20L134%2050%20L146%2025%20L158%2030%20H300'%20fill%3D'none'%20stroke%3D'%23FFFFFF'%20stroke-width%3D'2'%20stroke-opacity%3D'0.2'%2F%3E%3C%2Fsvg%3E");
    background-repeat: repeat-x, repeat-x, repeat-x;
    background-position: 0 91%, 30px 6%, 150px 47%;
    background-size: 300px 60px, 260px 52px, 340px 56px;
}

.auth-header-wrap {
    position: relative;
    z-index: 1;
    text-align: center;
    margin: 2.4rem auto 0.4rem;
}
.auth-logo-icon {
    width: 68px;
    height: 68px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.14);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.22);
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1rem;
    box-shadow: 0 12px 30px rgba(8, 14, 50, 0.30);
}
.auth-logo-icon img {
    width: 30px;
    height: 30px;
}
.auth-brand-title {
    color: white;
    font-size: 1.65rem;
    font-weight: 900;
    letter-spacing: -0.01em;
}
.auth-brand-subtitle {
    color: rgba(255, 255, 255, 0.85);
    font-size: 0.94rem;
    margin-top: 0.25rem;
    margin-bottom: 1.4rem;
}

/* Streamlit's real <div data-testid="stForm"> wrapper becomes the white card */
[data-testid="stForm"] {
    position: relative;
    z-index: 1;
    background: white;
    border-radius: 26px;
    padding: 2.1rem 2.3rem 1.7rem;
    max-width: 460px;
    margin: 0 auto 2.5rem;
    box-shadow: 0 30px 70px rgba(8, 14, 50, 0.35);
    border-top: 4px solid transparent;
    background-image: linear-gradient(white, white), linear-gradient(90deg, #5B6EF5, #22C1DC);
    background-origin: border-box;
    background-clip: padding-box, border-box;
}

/* Alert box sizing/centering specific to this page (color/contrast now handled
   globally in apply_theme() below, since success/error messages appear
   throughout the app, not just here). */
[data-testid="stAlert"] {
    max-width: 460px;
    margin: 0 auto 1rem auto !important;
}

/* Center + cap the width of the Login/Register tab row above the card.
   These override the global (dark-on-white) tab colors from apply_theme(),
   which were unreadable against the blue gradient here. */
.stTabs {
    position: relative;
    z-index: 1;
    max-width: 460px;
    margin: 0 auto 0.5rem;
}
.stTabs [data-baseweb="tab-list"] {
    justify-content: center;
    gap: 0.5rem;
    background: rgba(255, 255, 255, 0.14);
    backdrop-filter: blur(6px);
    border-radius: 999px;
    padding: 0.35rem;
    border: 1px solid rgba(255, 255, 255, 0.22);
}
.stTabs [data-baseweb="tab"] {
    color: rgba(255, 255, 255, 0.95) !important;
    font-weight: 800 !important;
    font-size: 1.02rem !important;
    border-radius: 999px !important;
    padding: 0.55rem 1.5rem !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: white !important;
    border-radius: 999px !important;
    box-shadow: 0 4px 14px rgba(8, 14, 50, 0.25);
}
.stTabs [aria-selected="true"] {
    color: var(--ipcms-primary-dark) !important;
    font-weight: 900 !important;
}
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}
</style>
"""


def apply_auth_theme():
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)