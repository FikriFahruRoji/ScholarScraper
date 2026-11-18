"""Google Scholar Scraper — Streamlit + Scrapling.

Dua halaman tersedia lewat navigasi sidebar:

* **Profil Scholar** — artikel dari satu profil publik.
* **Cari Kata Kunci** — hasil pencarian artikel berdasarkan kata kunci.

Jalankan dari folder ini:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from scholar_scraper.ui import inject_css

st.set_page_config(
    page_title="Google Scholar Scraper",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

pages = [
    st.Page(
        "views/profil.py",
        title="Profil Scholar",
        icon="👤",
        url_path="profil",
        default=True,
    ),
    st.Page(
        "views/kata_kunci.py",
        title="Cari Kata Kunci",
        icon="🔎",
        url_path="kata-kunci",
    ),
]

st.navigation(pages).run()
