"""Konversi hasil scraping menjadi tabel dan berkas unduhan."""
from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import ScholarProfile, ScholarSearch

ARTICLE_COLUMNS = [
    "No",
    "Judul",
    "Penulis",
    "Venue",
    "Tahun",
    "Sitasi",
    "Tautan Artikel",
    "Tautan Sitasi",
    "ID Publikasi",
]

SEARCH_COLUMNS = [
    "No",
    "Judul",
    "Penulis",
    "Venue",
    "Penerbit",
    "Tahun",
    "Sitasi",
    "Tautan Artikel",
    "Tautan PDF",
    "Tautan Sitasi",
    "Tautan Cluster",
    "Ringkasan",
    "ID Publikasi",
]

HEADER_FILL = PatternFill("solid", fgColor="7D2336")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def articles_frame(profile: ScholarProfile) -> pd.DataFrame:
    """Data artikel dengan kolom berbahasa Indonesia untuk UI dan ekspor."""
    rows = [
        {
            "No": article.index,
            "Judul": article.title,
            "Penulis": article.authors,
            "Venue": article.venue,
            "Tahun": article.year,
            "Sitasi": article.citations,
            "Tautan Artikel": article.article_url,
            "Tautan Sitasi": article.citations_url,
            "ID Publikasi": article.publication_id,
        }
        for article in profile.articles
    ]
    frame = pd.DataFrame(rows, columns=ARTICLE_COLUMNS)
    for column in ("No", "Tahun", "Sitasi"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    return frame


def search_frame(search: ScholarSearch) -> pd.DataFrame:
    """Data hasil pencarian kata kunci untuk UI dan ekspor."""
    rows = [
        {
            "No": result.index,
            "Judul": result.title,
            "Penulis": result.authors,
            "Venue": result.venue,
            "Penerbit": result.publisher,
            "Tahun": result.year,
            "Sitasi": result.citations,
            "Tautan Artikel": result.article_url,
            "Tautan PDF": result.pdf_url,
            "Tautan Sitasi": result.citations_url,
            "Tautan Cluster": result.cluster_url,
            "Ringkasan": result.snippet,
            "ID Publikasi": result.publication_id,
        }
        for result in search.results
    ]
    frame = pd.DataFrame(rows, columns=SEARCH_COLUMNS)
    for column in ("No", "Tahun", "Sitasi"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    return frame



def history_frame(profile: ScholarProfile) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {"Tahun": item.year, "Sitasi": item.citations}
            for item in profile.citation_history
        ],
        columns=["Tahun", "Sitasi"],
    )
    for column in ("Tahun", "Sitasi"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    return frame


def profile_frame(profile: ScholarProfile) -> pd.DataFrame:
    rows: list[tuple[str, object]] = [
        ("Nama", profile.name),
        ("ID Scholar", profile.scholar_id),
        ("Afiliasi", profile.affiliation or "—"),
        ("Email terverifikasi", profile.email or "—"),
        ("Homepage", profile.homepage or "—"),
        ("Minat riset", ", ".join(profile.interests) if profile.interests else "—"),
        ("Sitasi (all-time)", profile.metrics.citations),
        ("h-index (all-time)", profile.metrics.h_index),
        ("i10-index (all-time)", profile.metrics.i10_index),
        (
            f"Sitasi (sejak {profile.recent_since_year})"
            if profile.recent_since_year
            else "Sitasi (5 tahun terakhir)",
            profile.recent_metrics.citations,
        ),
        (
            f"h-index (sejak {profile.recent_since_year})"
            if profile.recent_since_year
            else "h-index (5 tahun terakhir)",
            profile.recent_metrics.h_index,
        ),
        (
            f"i10-index (sejak {profile.recent_since_year})"
            if profile.recent_since_year
            else "i10-index (5 tahun terakhir)",
            profile.recent_metrics.i10_index,
        ),
        ("Artikel terbaca", len(profile.articles)),
        ("Artikel lain tersedia", "Ya" if profile.has_more else "Tidak"),
        ("Urutan daftar", profile.sort),
        ("Halaman diambil", profile.pages_fetched),
        ("Metode", "Browser stealth" if profile.engine == "browser" else "HTTP"),
        (
            "Waktu pengambilan (UTC)",
            profile.fetched_at.strftime("%Y-%m-%d %H:%M:%S")
            if profile.fetched_at
            else "—",
        ),
        ("URL profil", profile.source_url),
    ]
    return pd.DataFrame(rows, columns=["Atribut", "Nilai"])


def search_info_frame(search: ScholarSearch) -> pd.DataFrame:
    """Ringkasan parameter dan status satu pencarian kata kunci."""
    if search.year_from and search.year_to:
        year_label = f"{search.year_from}–{search.year_to}"
    elif search.year_from:
        year_label = f"Sejak {search.year_from}"
    elif search.year_to:
        year_label = f"Sampai {search.year_to}"
    else:
        year_label = "Semua tahun"

    if search.max_results is None:
        if search.safety_cap is None:
            limit_label = "Tidak dibatasi"
        else:
            limit_label = (
                f"Semua halaman (maks. {int(search.safety_cap):,} hasil)"
                .replace(",", ".")
            )
    else:
        limit_label = f"{search.max_results} hasil"

    rows: list[tuple[str, object]] = [
        ("Kata kunci", search.query),
        ("Batas hasil", limit_label),
        ("Perkiraan total hasil", search.total_label or "—"),
        ("Hasil terbaca", len(search.results)),
        ("Halaman diambil", search.pages_fetched),
        ("Urutan", "Tanggal terbaru" if search.sort == "date" else "Relevansi"),
        ("Bahasa halaman", search.hl),
        ("Rentang tahun", year_label),
        ("Metode", "Browser stealth" if search.engine == "browser" else "HTTP"),
        ("Masih ada hasil lain", "Ya" if search.has_more else "Tidak"),
        (
            "Waktu pengambilan (UTC)",
            search.fetched_at.strftime("%Y-%m-%d %H:%M:%S")
            if search.fetched_at
            else "—",
        ),
        ("URL pencarian", search.source_url),
    ]
    return pd.DataFrame(rows, columns=["Atribut", "Nilai"])


def to_csv_bytes(profile: ScholarProfile) -> bytes:
    return articles_frame(profile).to_csv(index=False).encode("utf-8-sig")


def to_json_bytes(profile: ScholarProfile) -> bytes:
    return json.dumps(
        profile.to_dict(), ensure_ascii=False, indent=2, default=str
    ).encode("utf-8")


def search_to_csv_bytes(search: ScholarSearch) -> bytes:
    return search_frame(search).to_csv(index=False).encode("utf-8-sig")


def search_to_json_bytes(search: ScholarSearch) -> bytes:
    return json.dumps(
        search.to_dict(), ensure_ascii=False, indent=2, default=str
    ).encode("utf-8")


def to_excel_bytes(profile: ScholarProfile) -> bytes:
    buffer = BytesIO()
    articles = articles_frame(profile)
    excel_profile = profile_frame(profile)
    history = history_frame(profile)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        articles.to_excel(writer, sheet_name="Artikel", index=False)
        excel_profile.to_excel(writer, sheet_name="Profil", index=False)
        history.to_excel(writer, sheet_name="Sitasi per Tahun", index=False)

        style_sheet(
            writer.sheets["Artikel"], articles, url_headers={"Tautan Artikel", "Tautan Sitasi"}
        )
        style_sheet(writer.sheets["Profil"], excel_profile, url_headers={"Nilai"})
        style_sheet(writer.sheets["Sitasi per Tahun"], history)
    return buffer.getvalue()


def search_to_excel_bytes(search: ScholarSearch) -> bytes:
    buffer = BytesIO()
    results = search_frame(search)
    info = search_info_frame(search)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        results.to_excel(writer, sheet_name="Hasil", index=False)
        info.to_excel(writer, sheet_name="Pencarian", index=False)

        style_sheet(
            writer.sheets["Hasil"],
            results,
            url_headers={
                "Tautan Artikel",
                "Tautan PDF",
                "Tautan Sitasi",
                "Tautan Cluster",
            },
        )
        style_sheet(writer.sheets["Pencarian"], info, url_headers={"Nilai"})
    return buffer.getvalue()


def style_sheet(
    worksheet,
    frame: pd.DataFrame,
    *,
    url_headers: set[str] | None = None,
) -> None:
    url_headers = url_headers or set()
    worksheet.freeze_panes = "A2"
    if worksheet.max_row >= 2:
        worksheet.auto_filter.ref = worksheet.dimensions

    for column_index, header in enumerate(frame.columns, start=1):
        cell = worksheet.cell(row=1, column=column_index)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
        width = max(
            [len(str(header))]
            + [
                len(str(value))
                for value in frame[header].head(200).tolist()
                if value is not None and str(value) != "<NA>"
            ],
            default=10,
        )
        worksheet.column_dimensions[get_column_letter(column_index)].width = min(
            60, max(12, width + 2)
        )

    for column_index, header in enumerate(frame.columns, start=1):
        if header in {"Tahun", "Sitasi", "No"}:
            for row_index in range(2, worksheet.max_row + 1):
                worksheet.cell(row=row_index, column=column_index).number_format = "#,##0"
        if header in url_headers:
            for row_index in range(2, worksheet.max_row + 1):
                cell = worksheet.cell(row=row_index, column=column_index)
                value = cell.value
                if value and str(value).startswith(("http://", "https://")):
                    cell.hyperlink = str(value)
                    cell.style = "Hyperlink"
