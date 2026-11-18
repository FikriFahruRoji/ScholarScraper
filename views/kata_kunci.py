"""Halaman Cari Kata Kunci: hasil pencarian artikel Google Scholar."""
from __future__ import annotations

import html
import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from scholar_scraper import (
    AccessBlockedError,
    BrowserUnavailableError,
    ScholarSearch,
    ScholarSearcher,
    ScraperError,
    SearchOptions,
)
from scholar_scraper.export import (
    search_frame,
    search_info_frame,
    search_to_csv_bytes,
    search_to_excel_bytes,
    search_to_json_bytes,
)
from scholar_scraper.search import MAX_RESULTS_CAP
from scholar_scraper.ui import fmt_int, local_time

EXAMPLE_QUERY = '"machine learning" education'
EXAMPLE_URL = "https://scholar.google.com/scholar?hl=en&q=machine+learning+education"

LANGUAGES = {"en": "English", "id": "Bahasa Indonesia"}
SEARCH_SORTS = {
    "relevance": "Relevansi",
    "date": "Tanggal terbaru",
}
SEARCH_ENGINES = {
    "browser": "Browser stealth (disarankan)",
    "auto": "Otomatis (HTTP → browser)",
    "http": "HTTP saja (sering diblokir)",
}
MAX_RESULTS = [10, 20, 30, 50, 100, "Semua", "Tidak dibatasi"]
DELAY_MODES = {
    "safe": "Aman (acak 5–12 detik)",
    "very_safe": "Sangat aman (acak 12–25 detik)",
    "fixed": "Atur manual",
}
FILTER_SORTS = [
    "Sitasi (terbanyak)",
    "Tahun (terbaru)",
    "Judul (A–Z)",
    "Urutan Google Scholar",
]
FILTER_KEYS = (
    "kw_filter_query",
    "kw_filter_citations",
    "kw_filter_sort",
    "kw_filter_years",
    "kw_filter_pdf",
    "kw_detail_no",
)


def max_results_label(value: int | str) -> str:
    if value == "Semua":
        return f"Semua halaman (maks. {fmt_int(MAX_RESULTS_CAP)} hasil)"
    if value == "Tidak dibatasi":
        return "Tidak dibatasi (sampai hasil habis)"
    count = int(value)
    pages = max(1, count // 10)
    return f"{count} hasil ({pages} halaman)"


def fill_example() -> None:
    st.session_state["kw_query"] = EXAMPLE_QUERY


def clear_result() -> None:
    st.session_state.pop("scholar_search", None)
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return slug[:40] or "pencarian"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
stored_search: ScholarSearch | None = st.session_state.get("scholar_search")
current_year = datetime.now().year

st.sidebar.markdown("## 🔎 Cari Kata Kunci")
st.sidebar.caption("Cari artikel Scholar berdasarkan topik atau frasa.")
st.sidebar.button(
    "Gunakan contoh kata kunci",
    on_click=fill_example,
    width="stretch",
)

query_input = st.sidebar.text_area(
    "Kata kunci",
    key="kw_query",
    height=100,
    placeholder='"machine learning" education',
    help=(
        "Mendukung operator Scholar: tanda kutip untuk frasa persis, "
        "author:, source:, dan OR."
    ),
)

with st.sidebar.expander("Opsi pencarian", expanded=True):
    language_label = st.selectbox(
        "Bahasa halaman Scholar",
        options=list(LANGUAGES.values()),
        index=0,
        key="kw_language",
    )
    sort_label = st.selectbox(
        "Urutan hasil",
        options=list(SEARCH_SORTS.values()),
        index=0,
        key="kw_sort",
    )
    max_choice = st.selectbox(
        "Jumlah hasil",
        options=MAX_RESULTS,
        index=1,
        format_func=max_results_label,
        key="kw_max",
        help=(
            "Pilih “Semua” untuk berhenti di batas pengaman 1.000 hasil, atau "
            "“Tidak dibatasi” untuk terus mengambil halaman sampai hasil habis."
        ),
    )
    engine_label = st.selectbox(
        "Metode pengambilan",
        options=list(SEARCH_ENGINES.values()),
        index=0,
        key="kw_engine",
        help=(
            "Permintaan HTTP biasa hampir selalu dialihkan ke halaman "
            "verifikasi Google. Browser stealth adalah mode yang didukung."
        ),
    )
    year_filter = st.checkbox(
        "Batasi rentang tahun",
        value=False,
        key="kw_year_filter",
    )
    year_from: int | None = None
    year_to: int | None = None
    if year_filter:
        year_col_a, year_col_b = st.columns(2)
        year_from = int(
            year_col_a.number_input(
                "Dari tahun",
                min_value=1900,
                max_value=current_year,
                value=max(1900, current_year - 5),
                step=1,
                key="kw_year_from",
            )
        )
        year_to = int(
            year_col_b.number_input(
                "Sampai tahun",
                min_value=1900,
                max_value=current_year,
                value=current_year,
                step=1,
                key="kw_year_to",
            )
        )
    delay_mode_label = st.selectbox(
        "Jeda aman antar halaman",
        options=list(DELAY_MODES.values()),
        index=0,
        key="kw_delay_mode",
        help=(
            "Mode aman memilih jeda acak untuk setiap halaman agar pola "
            "permintaan tidak terlalu seragam. Pilih “Atur manual” untuk "
            "menentukan sendiri."
        ),
    )
    delay = st.slider(
        "Jeda manual (detik)",
        min_value=1.0,
        max_value=10.0,
        value=2.0,
        step=0.5,
        key="kw_delay",
        disabled=delay_mode_label != DELAY_MODES["fixed"],
    )
    timeout = st.slider(
        "Batas waktu per halaman (detik)",
        min_value=30,
        max_value=180,
        value=60,
        step=15,
        key="kw_timeout",
        help=(
            "Batas waktu memuat satu halaman. Naikkan jika koneksi lambat; "
            "turunkan jika ingin berhenti lebih cepat saat halaman menggantung."
        ),
    )

if max_choice == "Semua":
    st.sidebar.info(
        "Semua halaman dapat memakan waktu lama. Pengambilan berhenti saat "
        f"hasil habis atau mencapai batas pengaman "
        f"{fmt_int(MAX_RESULTS_CAP)} hasil."
    )
elif max_choice == "Tidak dibatasi":
    st.sidebar.warning(
        "Tidak ada batas hasil. Pengambilan berhenti hanya saat halaman "
        "berikutnya tidak tersedia atau tidak ada hasil baru. Gunakan jeda aman "
        "dan siapkan waktu yang cukup."
    )

st.sidebar.warning(
    "`robots.txt` Google Scholar melarang seluruh path `/scholar`, termasuk "
    "pencarian kata kunci. Permintaan otomatis dapat memicu CAPTCHA."
)
consent = st.sidebar.checkbox(
    "Saya memahami risiko dan tetap melanjutkan",
    value=False,
    key="kw_consent",
)
run = st.sidebar.button(
    "Cari artikel",
    type="primary",
    width="stretch",
    disabled=not consent,
)
if not consent:
    st.sidebar.caption("Centang persetujuan untuk mengaktifkan tombol.")

if stored_search is not None:
    st.sidebar.divider()
    st.sidebar.caption(
        f"Hasil tersimpan: **{stored_search.query}** · "
        f"{len(stored_search.results)} hasil"
    )
    if st.sidebar.button("Bersihkan hasil", width="stretch"):
        clear_result()
        st.rerun()

st.sidebar.divider()
st.sidebar.markdown(
    '<div class="footer-note">Dibangun dengan <b>Scrapling</b> + '
    "<b>Streamlit</b>. Gunakan secara wajar dan patuhi ketentuan situs sumber."
    "</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
if run:
    if not query_input.strip():
        st.error("Masukkan kata kunci pencarian terlebih dahulu.")
    elif not consent:
        st.error("Centang persetujuan di sidebar untuk melanjutkan.")
    elif year_from is not None and year_to is not None and year_from > year_to:
        st.error("Tahun awal tidak boleh lebih besar dari tahun akhir.")
    else:
        st.session_state.pop("scholar_search", None)
        language = next(
            code for code, label in LANGUAGES.items() if label == language_label
        )
        sort = next(
            code for code, label in SEARCH_SORTS.items() if label == sort_label
        )
        engine = next(
            code for code, label in SEARCH_ENGINES.items() if label == engine_label
        )
        delay_mode = next(
            code for code, label in DELAY_MODES.items() if label == delay_mode_label
        )
        if max_choice == "Tidak dibatasi":
            max_results = None
            safety_cap = None
        elif max_choice == "Semua":
            max_results = None
            safety_cap = MAX_RESULTS_CAP
        else:
            max_results = int(max_choice)
            safety_cap = MAX_RESULTS_CAP

        with st.status("Menghubungi Google Scholar...", expanded=True) as status:
            progress = st.progress(0.0) if max_results is not None else None

            def on_progress(message: str, fraction: float | None) -> None:
                status.write(message)
                if progress is not None and fraction is not None:
                    progress.progress(min(1.0, max(0.0, fraction)))

            try:
                options = SearchOptions(
                    hl=language,
                    max_results=max_results,
                    safety_cap=safety_cap,
                    engine=engine,
                    delay_mode=delay_mode,
                    delay=delay,
                    timeout=timeout,
                    year_from=year_from,
                    year_to=year_to,
                    sort=sort,
                )
                with st.spinner("Mengambil dan menyusun hasil pencarian..."):
                    search = ScholarSearcher(options).search(
                        query_input, on_progress=on_progress
                    )
                if progress is not None:
                    progress.progress(1.0)
                status.update(
                    label=(
                        f"Berhasil: {len(search.results)} hasil dari "
                        f"{search.pages_fetched} halaman"
                    ),
                    state="complete",
                    expanded=False,
                )
                st.session_state["scholar_search"] = search
                reset_filters()
            except (ScraperError, ValueError) as exc:
                status.update(label="Gagal mencari artikel", state="error", expanded=True)
                st.error(str(exc))
                if isinstance(exc, AccessBlockedError):
                    st.info(
                        "Pencarian Scholar lebih ketat daripada halaman profil. "
                        "Tunggu beberapa menit, coba mode **Browser stealth**, atau "
                        "ganti jaringan. Jangan menekan tombol berulang kali."
                    )
                elif isinstance(exc, BrowserUnavailableError):
                    st.info(
                        "Pasang browser Scrapling di environment yang sama: "
                        '`pip install "scrapling[fetchers]"` lalu `scrapling install`.'
                    )
            except Exception as exc:  # pragma: no cover - jaring pengaman UI
                status.update(label="Gagal tak terduga", state="error", expanded=True)
                st.error(
                    "Terjadi kesalahan tak terduga. Periksa koneksi internet dan "
                    "environment Python."
                )
                with st.expander("Detail teknis"):
                    st.exception(exc)

search: ScholarSearch | None = st.session_state.get("scholar_search")

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------
if search is None:
    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">Google Scholar · Pencarian kata kunci</div>
            <h1>Cari artikel Scholar dengan<br>kata kunci yang Anda pilih.</h1>
            <p>
                Masukkan topik, frasa persis, atau nama penulis. Aplikasi membaca
                hasil pencarian, menyaringnya, lalu menyediakan tabel, grafik,
                CSV, Excel, dan JSON.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown(
            """
            <div class="step-card">
                <span class="num">1</span>
                <h3>Tulis kata kunci</h3>
                <p>Gunakan tanda kutip untuk frasa persis, misalnya
                <code>"machine learning" education</code>. Operator
                <code>author:</code> dan <code>source:</code> juga didukung.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="step-card">
                <span class="num">2</span>
                <h3>Pilih cakupan</h3>
                <p>Ambil 10–100 hasil atau semua halaman, batasi rentang tahun,
                dan pilih urutan relevansi atau tanggal terbaru. Jeda aman acak
                dipakai per halaman.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class="step-card">
                <span class="num">3</span>
                <h3>Filter & unduh</h3>
                <p>Filter judul, penulis, venue, dan sitasi. Lihat ringkasan tiap
                hasil, lalu unduh CSV, Excel, atau JSON.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.write("")
    left, right = st.columns([1, 1.4])
    with left:
        st.link_button("Lihat contoh pencarian ↗", EXAMPLE_URL, width="stretch")
    with right:
        st.caption(
            "Pencarian `/scholar` dilarang oleh robots.txt Google Scholar. "
            "Gunakan hanya untuk keperluan wajar dan dalam jumlah terbatas."
        )
    st.stop()

# ---------------------------------------------------------------------------
# Result header
# ---------------------------------------------------------------------------
head_left, head_right = st.columns([3, 1.2], vertical_alignment="center")
with head_left:
    st.header(f"Hasil untuk “{search.query}”")
    total_text = search.total_label or "Jumlah total tidak tersedia"
    st.markdown(f"**{html.escape(total_text)}**")
with head_right:
    st.link_button("Buka pencarian di Scholar ↗", search.source_url, width="stretch")
    st.caption(
        f"Diambil {local_time(search.fetched_at)} · "
        f"{'browser stealth' if search.engine == 'browser' else 'HTTP'} · "
        f"{search.pages_fetched} halaman"
    )

metric_cols = st.columns(4)
metric_cols[0].metric(
    "Hasil terbaca",
    f"{len(search.results):,}".replace(",", "."),
    help="Jumlah hasil yang berhasil dibaca pada pencarian ini.",
)
metric_cols[1].metric(
    "Perkiraan total",
    fmt_int(search.total_estimate),
    help="Angka perkiraan yang ditampilkan Google Scholar, bukan jumlah pasti.",
)
citations = [result.citations or 0 for result in search.results]
metric_cols[2].metric(
    "Total sitasi hasil",
    fmt_int(sum(citations)),
    help="Jumlah sitasi dari hasil yang terbaca saja.",
)
metric_cols[3].metric(
    "Tersedia PDF",
    f"{sum(1 for result in search.results if result.pdf_url):,}".replace(",", "."),
    help="Hasil yang menyertakan tautan PDF langsung.",
)

if search.has_more:
    if search.max_results is None and search.safety_cap is not None:
        st.warning(
            f"Batas pengaman {fmt_int(search.safety_cap)} hasil tercapai dan "
            "masih ada hasil lain. Pilih “Tidak dibatasi” jika ingin melanjutkan "
            "tanpa batas, atau persempit kata kunci/filter tahun."
        )
    elif search.max_results is None:
        st.info(
            "Masih ada tautan halaman berikutnya, tetapi pengambilan berhenti "
            "karena halaman tersebut tidak memuat hasil baru. Coba longgarkan "
            "kata kunci atau filter."
        )
    else:
        st.info(
            f"Masih ada hasil lain di halaman berikutnya. Pencarian ini dibatasi "
            f"{len(search.results)} hasil. Pilih jumlah lebih besar, "
            "“Semua halaman”, atau “Tidak dibatasi” di sidebar."
        )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_results, tab_analytics, tab_info = st.tabs(
    ["📄 Hasil", "📊 Analitik", "ℹ️ Info & Catatan"]
)

with tab_results:
    frame = search_frame(search)
    if frame.empty:
        st.warning(
            "Tidak ada hasil yang terbaca. Coba kata kunci lain, longgarkan "
            "rentang tahun, atau periksa apakah halaman diblokir."
        )
    else:
        download_left, download_mid, download_right = st.columns([1, 1, 1])
        file_stem = slugify(search.query)
        download_left.download_button(
            "⬇️ CSV hasil",
            data=search_to_csv_bytes(search),
            file_name=f"scholar_{file_stem}_hasil.csv",
            mime="text/csv",
            width="stretch",
        )
        download_mid.download_button(
            "⬇️ Excel lengkap",
            data=search_to_excel_bytes(search),
            file_name=f"scholar_{file_stem}_lengkap.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        download_right.download_button(
            "⬇️ JSON lengkap",
            data=search_to_json_bytes(search),
            file_name=f"scholar_{file_stem}.json",
            mime="application/json",
            width="stretch",
        )
        st.caption(
            "Unduhan memuat seluruh hasil pencarian, bukan hanya hasil filter."
        )

        filter_query_col, filter_citation_col, filter_sort_col, filter_pdf_col = (
            st.columns([2.4, 1, 1.3, 1])
        )
        query_filter = filter_query_col.text_input(
            "Cari dalam hasil",
            placeholder="Judul, penulis, venue, penerbit, atau ringkasan",
            key="kw_filter_query",
        )
        min_citations = filter_citation_col.number_input(
            "Sitasi minimal",
            min_value=0,
            value=0,
            step=10,
            key="kw_filter_citations",
        )
        sort_display = filter_sort_col.selectbox(
            "Urutkan tampilan",
            options=FILTER_SORTS,
            key="kw_filter_sort",
        )
        only_pdf = filter_pdf_col.checkbox(
            "Hanya PDF",
            value=False,
            key="kw_filter_pdf",
        )

        years = sorted(
            int(year) for year in frame["Tahun"].dropna().unique().tolist()
        )
        year_range: tuple[int, int] | None = None
        if len(years) > 1:
            year_range = st.slider(
                "Rentang tahun hasil",
                min_value=years[0],
                max_value=years[-1],
                value=(years[0], years[-1]),
                key="kw_filter_years",
            )

        filtered = frame.copy()
        if query_filter.strip():
            mask = pd.Series(False, index=filtered.index)
            for column in ("Judul", "Penulis", "Venue", "Penerbit", "Ringkasan"):
                mask |= (
                    filtered[column]
                    .fillna("")
                    .astype(str)
                    .str.contains(query_filter.strip(), case=False, regex=False)
                )
            filtered = filtered[mask]
        if min_citations > 0:
            filtered = filtered[filtered["Sitasi"].fillna(0) >= min_citations]
        if only_pdf:
            filtered = filtered[filtered["Tautan PDF"].fillna("") != ""]
        if year_range is not None:
            in_range = filtered["Tahun"].between(year_range[0], year_range[1])
            filtered = filtered[in_range | filtered["Tahun"].isna()]

        if sort_display == "Sitasi (terbanyak)":
            filtered = filtered.sort_values(
                ["Sitasi", "Tahun"], ascending=[False, False], na_position="last"
            )
        elif sort_display == "Tahun (terbaru)":
            filtered = filtered.sort_values(
                ["Tahun", "Sitasi"], ascending=[False, False], na_position="last"
            )
        elif sort_display == "Judul (A–Z)":
            filtered = filtered.assign(
                _judul=filtered["Judul"].fillna("").astype(str).str.casefold()
            ).sort_values("_judul")
            filtered = filtered.drop(columns="_judul")
        else:
            filtered = filtered.sort_values("No")

        st.caption(f"Menampilkan {len(filtered)} dari {len(frame)} hasil.")
        if filtered.empty:
            st.info("Tidak ada hasil yang cocok dengan filter. Longgarkan filter.")
        else:
            display = filtered[
                [
                    "No",
                    "Judul",
                    "Penulis",
                    "Venue",
                    "Tahun",
                    "Sitasi",
                    "Tautan PDF",
                    "Tautan Artikel",
                ]
            ].rename(columns={"Tautan PDF": "PDF", "Tautan Artikel": "Artikel"})
            st.dataframe(
                display,
                hide_index=True,
                width="stretch",
                height=min(620, max(140, 40 + 35 * len(display))),
                column_config={
                    "No": st.column_config.NumberColumn("No", width="small"),
                    "Judul": st.column_config.TextColumn("Judul", width="large"),
                    "Penulis": st.column_config.TextColumn("Penulis", width="medium"),
                    "Venue": st.column_config.TextColumn("Venue", width="medium"),
                    "Tahun": st.column_config.NumberColumn(
                        "Tahun", format="%d", width="small"
                    ),
                    "Sitasi": st.column_config.NumberColumn(
                        "Sitasi", format="%d", width="small"
                    ),
                    "PDF": st.column_config.LinkColumn(
                        "PDF", display_text="Buka", width="small"
                    ),
                    "Artikel": st.column_config.LinkColumn(
                        "Artikel", display_text="Buka", width="small"
                    ),
                },
            )

            with st.expander("🔎 Detail hasil"):
                detail_options = {
                    int(row["No"]): (
                        f"{row['Judul']} — "
                        f"{int(row['Tahun']) if pd.notna(row['Tahun']) else 'tanpa tahun'}"
                    )
                    for _, row in filtered.iterrows()
                }
                selected_no = st.selectbox(
                    "Pilih hasil",
                    options=list(detail_options),
                    format_func=detail_options.get,
                    key="kw_detail_no",
                )
                detail = filtered[filtered["No"] == selected_no].iloc[0]
                st.markdown(f"### {detail['Judul']}")

                meta_left, meta_right = st.columns(2)
                meta_left.markdown(
                    f"**Penulis**  \n{detail['Penulis'] or '—'}\n\n"
                    f"**Venue**  \n{detail['Venue'] or '—'}\n\n"
                    f"**Penerbit**  \n{detail['Penerbit'] or '—'}"
                )
                meta_right.markdown(
                    f"**Tahun**  \n"
                    f"{detail['Tahun'] if pd.notna(detail['Tahun']) else '—'}\n\n"
                    f"**Sitasi**  \n"
                    f"{fmt_int(int(detail['Sitasi'])) if pd.notna(detail['Sitasi']) else '—'}\n\n"
                    f"**ID Scholar**  \n{detail['ID Publikasi'] or '—'}"
                )

                if detail["Ringkasan"]:
                    st.markdown("**Ringkasan**")
                    st.write(detail["Ringkasan"])

                link_cols = st.columns(4)
                if detail["Tautan Artikel"]:
                    link_cols[0].link_button(
                        "Halaman artikel ↗", detail["Tautan Artikel"], width="stretch"
                    )
                if detail["Tautan PDF"]:
                    link_cols[1].link_button(
                        "PDF ↗", detail["Tautan PDF"], width="stretch"
                    )
                if detail["Tautan Sitasi"]:
                    link_cols[2].link_button(
                        "Daftar sitasi ↗", detail["Tautan Sitasi"], width="stretch"
                    )
                if detail["Tautan Cluster"]:
                    link_cols[3].link_button(
                        "Semua versi ↗", detail["Tautan Cluster"], width="stretch"
                    )

with tab_analytics:
    frame = search_frame(search)
    if frame.empty:
        st.info("Belum ada hasil untuk dianalisis.")
    else:
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.markdown("#### Hasil per tahun")
            by_year = (
                frame.dropna(subset=["Tahun"])
                .groupby("Tahun", as_index=False)
                .size()
                .rename(columns={"size": "Hasil"})
            )
            if by_year.empty:
                st.caption("Tahun hasil tidak tersedia.")
            else:
                st.bar_chart(
                    by_year,
                    x="Tahun",
                    y="Hasil",
                    color="#7D2336",
                    height=300,
                )
        with chart_right:
            st.markdown("#### Venue terbanyak")
            venues = (
                frame.assign(
                    _venue=frame["Venue"].fillna("").astype(str).str.strip()
                )
                .loc[lambda data: data["_venue"] != ""]
                .groupby("_venue", as_index=False)
                .size()
                .rename(columns={"_venue": "Venue", "size": "Hasil"})
                .sort_values("Hasil", ascending=False)
                .head(10)
            )
            if venues.empty:
                st.caption("Nama venue tidak tersedia pada hasil ini.")
            else:
                st.bar_chart(
                    venues,
                    x="Venue",
                    y="Hasil",
                    color="#7D2336",
                    height=300,
                    horizontal=True,
                )

        citations = frame["Sitasi"].fillna(0)
        stat_a, stat_b, stat_c = st.columns(3)
        stat_a.metric("Total sitasi hasil", fmt_int(int(citations.sum())))
        stat_b.metric(
            "Median sitasi",
            fmt_int(int(citations.median())) if len(citations) else "—",
        )
        stat_c.metric(
            "Hasil tanpa sitasi", fmt_int(int((citations == 0).sum()))
        )

        st.markdown("#### 10 hasil paling banyak disitasi")
        top = frame.sort_values(
            "Sitasi", ascending=False, na_position="last"
        ).head(10)[["Judul", "Venue", "Tahun", "Sitasi"]]
        st.dataframe(top, hide_index=True, width="stretch")

with tab_info:
    st.markdown("#### Parameter dan status pencarian")
    info_view = search_info_frame(search).copy()
    info_view["Nilai"] = info_view["Nilai"].map(
        lambda value: "" if value is None else str(value)
    )
    st.dataframe(
        info_view,
        hide_index=True,
        width="stretch",
        column_config={
            "Atribut": st.column_config.TextColumn("Atribut", width="medium"),
            "Nilai": st.column_config.TextColumn("Nilai", width="large"),
        },
    )

    st.markdown("#### Catatan penggunaan")
    st.markdown(
        """
        - **Pencarian bukan API resmi.** Endpoint `/scholar` tidak diizinkan
          `robots.txt` Google Scholar; fitur ini memerlukan persetujuan eksplisit.
        - **Browser stealth disarankan.** Permintaan HTTP biasa biasanya
          dialihkan ke halaman verifikasi `sgsync` dan tidak menghasilkan data.
        - **Ambil secukupnya.** Gunakan 10–50 hasil, beri jeda antar halaman, dan
          hindari pengambilan berulang dalam waktu singkat.
        - **Angka sitasi** mengikuti Google Scholar dan dapat berbeda dari Scopus,
          Web of Science, atau OpenAlex.
        - **Hormati hak cipta.** Tautan PDF mengarah ke berkas pihak ketiga;
          periksa izin penggunaan sebelum mengunduh atau menyebarkannya.
        """
    )
    with st.expander("Lihat JSON"):
        st.json(json.loads(search_to_json_bytes(search)))

st.divider()
st.caption(
    "Google Scholar Scraper · Pencarian kata kunci · Scrapling + Streamlit · "
    f"Query: {search.query}"
)
