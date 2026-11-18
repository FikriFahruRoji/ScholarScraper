"""Halaman Profil Scholar: ambil artikel dari satu profil publik."""
from __future__ import annotations

import html
import json

import pandas as pd
import streamlit as st

from scholar_scraper import (
    AccessBlockedError,
    BrowserUnavailableError,
    InvalidProfileError,
    ProfileNotFoundError,
    ScholarProfile,
    ScholarScraper,
    ScraperError,
    ScrapeOptions,
)
from scholar_scraper.export import (
    articles_frame,
    history_frame,
    profile_frame,
    to_csv_bytes,
    to_excel_bytes,
    to_json_bytes,
)
from scholar_scraper.ui import (
    fmt_int,
    local_time,
    max_articles_label,
    render_chips,
)

EXAMPLE_PROFILE = "https://scholar.google.com/citations?user=kukA0LcAAAAJ&hl=en"

LANGUAGES = {"en": "English", "id": "Bahasa Indonesia"}
SORTS = {
    "citations": "Sitasi (terbanyak)",
    "year": "Tahun terbaru",
    "title": "Judul (A\u2013Z)",
}
ENGINES = {
    "auto": "Otomatis (HTTP \u2192 browser)",
    "http": "HTTP saja (cepat)",
    "browser": "Browser stealth",
}
MAX_ARTICLES = [100, 200, 300, 500, 1000, "Semua"]
SORT_DISPLAY = [
    "Sitasi (terbanyak)",
    "Tahun (terbaru)",
    "Judul (A\u2013Z)",
    "Urutan Google Scholar",
]


def fill_example() -> None:
    st.session_state["profile_input"] = EXAMPLE_PROFILE


def clear_result() -> None:
    for key in (
        "scholar_profile",
        "filter_query",
        "filter_citations",
        "filter_sort",
        "filter_years",
        "detail_article",
    ):
        st.session_state.pop(key, None)


def reset_filters() -> None:
    for key in (
        "filter_query",
        "filter_citations",
        "filter_sort",
        "filter_years",
        "detail_article",
    ):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
stored_profile: ScholarProfile | None = st.session_state.get("scholar_profile")

st.sidebar.markdown("## 🎓 Scholar Scraper")
st.sidebar.caption("Ambil daftar artikel dari satu profil Google Scholar.")
st.sidebar.button(
    "Gunakan contoh profil",
    on_click=fill_example,
    width="stretch",
)

profile_input = st.sidebar.text_input(
    "URL atau ID profil",
    key="profile_input",
    placeholder="https://scholar.google.com/citations?user=...",
    help="Tempel URL lengkap atau ID dari parameter user=.",
)

with st.sidebar.expander("Opsi pengambilan", expanded=True):
    language_label = st.selectbox(
        "Bahasa halaman Scholar",
        options=list(LANGUAGES.values()),
        index=0,
        key="opt_language",
    )
    sort_label = st.selectbox(
        "Urutan daftar artikel",
        options=list(SORTS.values()),
        index=0,
        key="opt_sort",
    )
    max_choice = st.selectbox(
        "Jumlah artikel",
        options=MAX_ARTICLES,
        index=0,
        format_func=max_articles_label,
        key="opt_max",
        help=(
            "Default 100 artikel = satu halaman. Angka di atas 100 memerlukan "
            "pagination (parameter cstart)."
        ),
    )
    engine_label = st.selectbox(
        "Metode pengambilan",
        options=list(ENGINES.values()),
        index=0,
        key="opt_engine",
    )
    delay = st.slider(
        "Jeda antar halaman (detik)",
        min_value=1.0,
        max_value=10.0,
        value=2.0,
        step=0.5,
        key="opt_delay",
        disabled=max_choice == 100,
    )

needs_pagination = max_choice != 100
allow_pagination = True
if needs_pagination:
    st.sidebar.warning(
        "Lebih dari 100 artikel memakai parameter `cstart`. robots.txt Google "
        "Scholar saat ini melarang URL tersebut."
    )
    allow_pagination = st.sidebar.checkbox(
        "Saya memahami risikonya dan tetap melanjutkan",
        value=False,
        key="opt_consent",
    )

run = st.sidebar.button(
    "Ambil data artikel",
    type="primary",
    width="stretch",
    disabled=needs_pagination and not allow_pagination,
)
if needs_pagination and not allow_pagination:
    st.sidebar.caption("Centang persetujuan untuk mengaktifkan tombol.")

if stored_profile is not None:
    st.sidebar.divider()
    st.sidebar.caption(
        f"Hasil tersimpan: **{stored_profile.name}** · "
        f"{len(stored_profile.articles)} artikel"
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
    if not profile_input.strip():
        st.error("Masukkan URL atau ID profil Google Scholar terlebih dahulu.")
    elif needs_pagination and not allow_pagination:
        st.error("Centang persetujuan pagination di sidebar untuk melanjutkan.")
    else:
        st.session_state.pop("scholar_profile", None)
        language = next(
            code for code, label in LANGUAGES.items() if label == language_label
        )
        sort = next(code for code, label in SORTS.items() if label == sort_label)
        engine = next(
            code for code, label in ENGINES.items() if label == engine_label
        )
        max_articles = None if max_choice == "Semua" else int(max_choice)

        with st.status("Menghubungi Google Scholar...", expanded=True) as status:
            progress = st.progress(0.0)

            def on_progress(message: str, fraction: float | None) -> None:
                status.write(message)
                if fraction is not None:
                    progress.progress(min(1.0, max(0.0, fraction)))

            try:
                options = ScrapeOptions(
                    hl=language,
                    sort=sort,
                    max_articles=max_articles,
                    allow_pagination=allow_pagination,
                    engine=engine,
                    delay=delay,
                )
                with st.spinner("Mengambil dan menyusun artikel..."):
                    profile = ScholarScraper(options).scrape(
                        profile_input, on_progress=on_progress
                    )
                progress.progress(1.0)
                status.update(
                    label=(
                        f"Berhasil: {len(profile.articles)} artikel dari "
                        f"{profile.pages_fetched} halaman"
                    ),
                    state="complete",
                    expanded=False,
                )
                st.session_state["scholar_profile"] = profile
                reset_filters()
            except (ScraperError, ValueError) as exc:
                status.update(label="Gagal mengambil data", state="error", expanded=True)
                st.error(str(exc))
                if isinstance(exc, AccessBlockedError):
                    st.info(
                        "Google Scholar membatasi akses otomatis. Tunggu beberapa "
                        "menit, coba mode **Browser stealth**, atau ganti jaringan. "
                        "Jangan menekan tombol berulang kali."
                    )
                elif isinstance(exc, BrowserUnavailableError):
                    st.info(
                        "Pasang browser Scrapling di environment yang sama: "
                        '`pip install "scrapling[fetchers]"` lalu `scrapling install`.'
                    )
                elif isinstance(exc, ProfileNotFoundError):
                    st.info(
                        "Pastikan profil bersifat publik dan URL berbentuk "
                        "`https://scholar.google.com/citations?user=ID`."
                    )
                elif isinstance(exc, InvalidProfileError):
                    st.info(
                        "Contoh input yang benar: "
                        f"`{EXAMPLE_PROFILE}`"
                    )
            except Exception as exc:  # pragma: no cover - jaring pengaman UI
                status.update(label="Gagal tak terduga", state="error", expanded=True)
                st.error(
                    "Terjadi kesalahan tak terduga. Periksa koneksi internet dan "
                    "environment Python."
                )
                with st.expander("Detail teknis"):
                    st.exception(exc)

profile: ScholarProfile | None = st.session_state.get("scholar_profile")

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------
if profile is None:
    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">Google Scholar · Scrapling · Streamlit</div>
            <h1>Ubah profil Scholar menjadi<br>tabel artikel yang siap diolah.</h1>
            <p>
                Tempel satu URL profil publik. Aplikasi membaca identitas, metrik
                sitasi, dan daftar artikel, lalu menyediakannya sebagai tabel,
                grafik, CSV, Excel, dan JSON.
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
                <h3>Tempel profil</h3>
                <p>Gunakan URL lengkap atau ID dari parameter <code>user=</code>.
                URL divalidasi dan dibangun ulang oleh aplikasi.</p>
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
                <p>Default 100 artikel teratas dalam satu halaman. Pagination
                tersedia sebagai opsi dengan peringatan robots.txt.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class="step-card">
                <span class="num">3</span>
                <h3>Unduh & analisis</h3>
                <p>Filter, urutkan, lihat detail sitasi, lalu unduh CSV, Excel
                multi-sheet, atau JSON lengkap.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.write("")
    left, right = st.columns([1, 1.4])
    with left:
        st.link_button("Lihat contoh profil ↗", EXAMPLE_PROFILE, width="stretch")
    with right:
        st.caption(
            "Mulai dari sidebar. Data diambil langsung dari halaman publik Google "
            "Scholar; angka dapat berbeda dari Scopus atau Web of Science."
        )
    st.stop()

# ---------------------------------------------------------------------------
# Result header
# ---------------------------------------------------------------------------
head_left, head_right = st.columns([3, 1.2], vertical_alignment="center")
with head_left:
    st.header(profile.name)
    st.markdown(
        f"**{html.escape(profile.affiliation) or '—'}**"
        if profile.affiliation
        else "—"
    )
    render_chips(profile.interests)
with head_right:
    st.link_button("Buka profil di Scholar ↗", profile.source_url, width="stretch")
    st.caption(
        f"Diambil {local_time(profile.fetched_at)} · "
        f"{'browser stealth' if profile.engine == 'browser' else 'HTTP'} · "
        f"{profile.pages_fetched} halaman"
    )

metric_cols = st.columns(4)
metric_cols[0].metric(
    "Sitasi",
    fmt_int(profile.metrics.citations),
    help=(
        f"Sejak {profile.recent_since_year}: {fmt_int(profile.recent_metrics.citations)}"
        if profile.recent_since_year
        else None
    ),
)
metric_cols[1].metric(
    "h-index",
    fmt_int(profile.metrics.h_index),
    help=(
        f"Sejak {profile.recent_since_year}: {fmt_int(profile.recent_metrics.h_index)}"
        if profile.recent_since_year
        else None
    ),
)
metric_cols[2].metric(
    "i10-index",
    fmt_int(profile.metrics.i10_index),
    help=(
        f"Sejak {profile.recent_since_year}: {fmt_int(profile.recent_metrics.i10_index)}"
        if profile.recent_since_year
        else None
    ),
)
metric_cols[3].metric(
    "Artikel terbaca",
    f"{len(profile.articles):,}".replace(",", "."),
    help="Jumlah artikel yang berhasil dibaca pada pengambilan ini.",
)

if profile.has_more:
    st.info(
        f"Masih ada artikel lain di profil ini. Pengambilan saat ini dibatasi "
        f"{len(profile.articles)} artikel. Pilih jumlah lebih besar di sidebar "
        "dan setujui opsi pagination jika ingin mengambil lebih banyak."
    )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_articles, tab_analytics, tab_profile = st.tabs(
    ["📄 Artikel", "📊 Analitik", "👤 Profil & Riwayat"]
)

with tab_articles:
    frame = articles_frame(profile)
    if frame.empty:
        st.warning("Tidak ada artikel yang terbaca pada halaman profil ini.")
    else:
        download_left, download_mid, download_right = st.columns([1, 1, 1])
        download_left.download_button(
            "⬇️ CSV artikel",
            data=to_csv_bytes(profile),
            file_name=f"scholar_{profile.scholar_id}_artikel.csv",
            mime="text/csv",
            width="stretch",
        )
        download_mid.download_button(
            "⬇️ Excel lengkap",
            data=to_excel_bytes(profile),
            file_name=f"scholar_{profile.scholar_id}_lengkap.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        download_right.download_button(
            "⬇️ JSON lengkap",
            data=to_json_bytes(profile),
            file_name=f"scholar_{profile.scholar_id}.json",
            mime="application/json",
            width="stretch",
        )
        st.caption(
            "Unduhan memuat seluruh artikel yang berhasil diambil, bukan hanya "
            "hasil filter di bawah."
        )

        filter_query_col, filter_citation_col, filter_sort_col = st.columns(
            [2.4, 1, 1.3]
        )
        query = filter_query_col.text_input(
            "Cari artikel",
            placeholder="Judul, penulis, atau nama venue",
            key="filter_query",
        )
        min_citations = filter_citation_col.number_input(
            "Sitasi minimal",
            min_value=0,
            value=0,
            step=10,
            key="filter_citations",
        )
        sort_display = filter_sort_col.selectbox(
            "Urutkan tampilan",
            options=SORT_DISPLAY,
            key="filter_sort",
        )

        years = sorted(
            int(year) for year in frame["Tahun"].dropna().unique().tolist()
        )
        year_range: tuple[int, int] | None = None
        if len(years) > 1:
            year_range = st.slider(
                "Rentang tahun",
                min_value=years[0],
                max_value=years[-1],
                value=(years[0], years[-1]),
                key="filter_years",
            )

        filtered = frame.copy()
        if query.strip():
            mask = pd.Series(False, index=filtered.index)
            for column in ("Judul", "Penulis", "Venue"):
                mask |= (
                    filtered[column]
                    .fillna("")
                    .astype(str)
                    .str.contains(query.strip(), case=False, regex=False)
                )
            filtered = filtered[mask]
        if min_citations > 0:
            filtered = filtered[filtered["Sitasi"].fillna(0) >= min_citations]
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

        st.caption(
            f"Menampilkan {len(filtered)} dari {len(frame)} artikel."
        )
        if filtered.empty:
            st.info("Tidak ada artikel yang cocok dengan filter. Longgarkan filter.")
        else:
            display = filtered[
                ["No", "Judul", "Penulis", "Venue", "Tahun", "Sitasi", "Tautan Artikel"]
            ].rename(columns={"Tautan Artikel": "Tautan"})
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
                    "Tautan": st.column_config.LinkColumn(
                        "Tautan", display_text="Buka", width="small"
                    ),
                },
            )

            with st.expander("🔎 Detail artikel"):
                detail_options = {
                    int(row["No"]): (
                        f"{row['Judul']} — "
                        f"{int(row['Tahun']) if pd.notna(row['Tahun']) else 'tanpa tahun'}"
                    )
                    for _, row in filtered.iterrows()
                }
                selected_no = st.selectbox(
                    "Pilih artikel",
                    options=list(detail_options),
                    format_func=detail_options.get,
                    key="detail_article",
                )
                detail = filtered[filtered["No"] == selected_no].iloc[0]
                st.markdown(f"### {detail['Judul']}")
                detail_left, detail_right = st.columns(2)
                detail_left.markdown(
                    f"**Penulis**  \n{detail['Penulis'] or '—'}\n\n"
                    f"**Venue**  \n{detail['Venue'] or '—'}"
                )
                detail_right.markdown(
                    f"**Tahun**  \n{detail['Tahun'] if pd.notna(detail['Tahun']) else '—'}\n\n"
                    f"**Sitasi**  \n"
                    f"{fmt_int(int(detail['Sitasi'])) if pd.notna(detail['Sitasi']) else '—'}"
                )
                link_cols = st.columns(2)
                if detail["Tautan Artikel"]:
                    link_cols[0].link_button(
                        "Halaman artikel ↗",
                        detail["Tautan Artikel"],
                        width="stretch",
                    )
                if detail["Tautan Sitasi"]:
                    link_cols[1].link_button(
                        "Daftar sitasi ↗",
                        detail["Tautan Sitasi"],
                        width="stretch",
                    )

with tab_analytics:
    frame = articles_frame(profile)
    if frame.empty:
        st.info("Belum ada artikel untuk dianalisis.")
    else:
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.markdown("#### Artikel per tahun")
            by_year = (
                frame.dropna(subset=["Tahun"])
                .groupby("Tahun", as_index=False)
                .size()
                .rename(columns={"size": "Artikel"})
            )
            if by_year.empty:
                st.caption("Tahun artikel tidak tersedia.")
            else:
                st.bar_chart(
                    by_year,
                    x="Tahun",
                    y="Artikel",
                    color="#7D2336",
                    height=300,
                )
        with chart_right:
            st.markdown("#### Sitasi baru per tahun")
            history = history_frame(profile)
            if history.empty:
                st.caption("Grafik sitasi per tahun tidak tersedia pada profil ini.")
            else:
                st.bar_chart(
                    history,
                    x="Tahun",
                    y="Sitasi",
                    color="#7D2336",
                    height=300,
                )

        citations = frame["Sitasi"].fillna(0)
        stat_a, stat_b, stat_c = st.columns(3)
        stat_a.metric("Total sitasi artikel", fmt_int(int(citations.sum())))
        stat_b.metric(
            "Median sitasi",
            fmt_int(int(citations.median())) if len(citations) else "—",
        )
        stat_c.metric(
            "Artikel tanpa sitasi", fmt_int(int((citations == 0).sum()))
        )

        st.markdown("#### 10 artikel paling banyak disitasi")
        top = frame.sort_values(
            "Sitasi", ascending=False, na_position="last"
        ).head(10)[["Judul", "Venue", "Tahun", "Sitasi"]]
        st.dataframe(top, hide_index=True, width="stretch")

with tab_profile:
    st.markdown("#### Identitas dan metrik")
    profile_view = profile_frame(profile).copy()
    # Kolom "Nilai" berisi campuran angka dan teks; samakan ke string agar
    # kompatibel dengan Arrow/Streamlit tanpa peringatan serialisasi.
    profile_view["Nilai"] = profile_view["Nilai"].map(
        lambda value: "" if value is None else str(value)
    )
    st.dataframe(
        profile_view,
        hide_index=True,
        width="stretch",
        column_config={
            "Atribut": st.column_config.TextColumn("Atribut", width="medium"),
            "Nilai": st.column_config.TextColumn("Nilai", width="large"),
        },
    )

    st.markdown("#### Riwayat sitasi tahunan")
    history = history_frame(profile)
    if history.empty:
        st.caption("Tidak ada data riwayat sitasi pada halaman profil.")
    else:
        st.dataframe(history, hide_index=True, width="stretch")

    st.markdown("#### Data mentah")
    st.caption(
        "JSON memuat identitas, metrik, riwayat sitasi, dan seluruh artikel "
        "dengan tautan aslinya."
    )
    st.download_button(
        "⬇️ Unduh JSON",
        data=to_json_bytes(profile),
        file_name=f"scholar_{profile.scholar_id}.json",
        mime="application/json",
    )
    with st.expander("Lihat JSON"):
        st.json(json.loads(to_json_bytes(profile)))

st.divider()
with st.expander("Catatan penggunaan dan batasan"):
    st.markdown(
        """
        - **Default satu halaman.** URL `citations?user=...&pagesize=100` sesuai
          aturan `robots.txt` Google Scholar dan dapat memuat hingga 100 artikel.
        - **Pagination bersifat opt-in.** Parameter `cstart` yang dipakai untuk
          halaman berikutnya saat ini dilarang `robots.txt`; aplikasi hanya
          memakainya jika Anda mencentang persetujuan.
        - **Bukan API resmi.** Google Scholar dapat membatasi akses kapan saja.
          Jika muncul CAPTCHA/429, tunggu, coba mode browser, atau ganti jaringan.
        - **Angka sitasi** mengikuti Google Scholar dan dapat berbeda dari Scopus,
          Web of Science, atau OpenAlex.
        - **Gunakan secara wajar.** Hormati ketentuan layanan, hak penulis, dan
          ketentuan perlindungan data yang berlaku.
        """
    )
st.caption(
    "Google Scholar Scraper · Scrapling + Streamlit · "
    f"Data profil: {profile.source_url}"
)
