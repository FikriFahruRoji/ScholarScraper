"""Komponen UI bersama untuk halaman Streamlit."""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

CSS = """
<style>
    .block-container {padding-top: 2rem; padding-bottom: 4rem; max-width: 1280px;}
    .hero {
        border: 1px solid #EADFE2;
        border-radius: 22px;
        padding: 2.2rem 2.4rem;
        background:
            radial-gradient(circle at 92% 8%, rgba(125, 35, 54, .13), transparent 38%),
            linear-gradient(135deg, #FFFDFD 0%, #FBF4F6 100%);
        margin-bottom: 1.4rem;
    }
    .hero .eyebrow {
        color: #7D2336;
        font-size: .76rem;
        font-weight: 700;
        letter-spacing: .18em;
        text-transform: uppercase;
    }
    .hero h1 {
        color: #241A1D;
        font-size: clamp(2rem, 4vw, 3rem);
        line-height: 1.08;
        margin: .55rem 0 .7rem;
        letter-spacing: -.02em;
    }
    .hero p {color: #5B4B50; font-size: 1.02rem; max-width: 52rem; margin: 0;}
    .chip {
        display: inline-block;
        background: #F7EDF0;
        color: #6C2032;
        border: 1px solid #EBD8DE;
        border-radius: 999px;
        padding: .18rem .65rem;
        font-size: .78rem;
        margin: 0 .3rem .35rem 0;
    }
    .step-card {
        border: 1px solid #ECE3E5;
        border-radius: 16px;
        padding: 1.15rem 1.25rem;
        background: #FFFFFF;
        min-height: 148px;
    }
    .step-card .num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.75rem;
        height: 1.75rem;
        border-radius: 50%;
        background: #7D2336;
        color: #FFFFFF;
        font-size: .82rem;
        font-weight: 700;
        margin-bottom: .55rem;
    }
    .step-card h3 {font-size: 1rem; margin: 0 0 .35rem; color: #2A2023;}
    .step-card p {font-size: .88rem; color: #6B5C61; margin: 0; line-height: 1.45;}
    div[data-testid="stMetric"] {
        background: #FCF8F9;
        border: 1px solid #EFE4E7;
        border-radius: 14px;
        padding: .8rem 1rem;
    }
    .footer-note {color: #8A7B80; font-size: .78rem; line-height: 1.5;}
    .result-title {font-size: 1.02rem; font-weight: 700; color: #241A1D; margin: 0 0 .2rem;}
    .result-meta {color: #6B5C61; font-size: .83rem; margin: 0 0 .35rem;}
    .result-snippet {color: #5B4B50; font-size: .87rem; line-height: 1.45; margin: .3rem 0 0;}
    .result-links {font-size: .82rem; margin-top: .45rem;}
    .tag {
        display: inline-block;
        border-radius: 6px;
        padding: .05rem .4rem;
        font-size: .72rem;
        font-weight: 600;
        background: #F3EAEC;
        color: #7D2336;
        margin-right: .3rem;
    }
    @media (max-width: 700px) {
        .hero {padding: 1.4rem 1.2rem;}
        .step-card {min-height: auto;}
    }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def fmt_int(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", ".")


def local_time(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone().strftime("%d %b %Y, %H:%M")


def max_articles_label(value: int | str) -> str:
    if value == "Semua":
        return "Semua artikel (maks. 2.000)"
    return f"{value} artikel"


def render_chips(items: tuple[str, ...]) -> None:
    if not items:
        return
    chips = "".join(
        f'<span class="chip">{html.escape(item)}</span>' for item in items
    )
    st.markdown(chips, unsafe_allow_html=True)
