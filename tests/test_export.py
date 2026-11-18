from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from scrapling.parser import Selector

from scholar_scraper.export import (
    ARTICLE_COLUMNS,
    SEARCH_COLUMNS,
    articles_frame,
    history_frame,
    profile_frame,
    search_frame,
    search_info_frame,
    search_to_csv_bytes,
    search_to_excel_bytes,
    search_to_json_bytes,
    to_csv_bytes,
    to_excel_bytes,
    to_json_bytes,
)
from scholar_scraper.models import ScholarSearch
from scholar_scraper.parser import parse_profile_page
from scholar_scraper.search import parse_search_page

FIXTURE = Path(__file__).parent / "fixtures" / "profile_page.html"
SEARCH_FIXTURE = Path(__file__).parent / "fixtures" / "search_page.html"


@pytest.fixture(scope="module")
def profile():
    page = Selector(FIXTURE.read_text(encoding="utf-8"))
    return parse_profile_page(page, "kukA0LcAAAAJ")


@pytest.fixture(scope="module")
def search():
    page = Selector(SEARCH_FIXTURE.read_text(encoding="utf-8"))
    return ScholarSearch(
        query="machine learning education",
        max_results=20,
        results=tuple(parse_search_page(page)),
        total_label="About 5.460.000 results",
    )


def test_articles_frame(profile):
    frame = articles_frame(profile)
    assert list(frame.columns) == ARTICLE_COLUMNS
    assert len(frame) == 3
    assert frame.iloc[0]["Judul"] == "Deep learning"
    assert int(frame.iloc[0]["Sitasi"]) == 123987
    assert str(frame["Tahun"].dtype) == "Int64"


def test_history_frame(profile):
    frame = history_frame(profile)
    assert list(frame.columns) == ["Tahun", "Sitasi"]
    assert len(frame) == 6


def test_profile_frame(profile):
    frame = profile_frame(profile)
    values = dict(zip(frame["Atribut"], frame["Nilai"]))
    assert values["Nama"] == "Yoshua Bengio"
    assert values["Artikel terbaca"] == 3


def test_csv_has_utf8_bom(profile):
    data = to_csv_bytes(profile)
    assert data.startswith(b"\xef\xbb\xbf")
    assert "Judul" in data.decode("utf-8-sig")


def test_json_roundtrip(profile):
    payload = json.loads(to_json_bytes(profile))
    assert payload["name"] == "Yoshua Bengio"
    assert payload["article_count"] == 3
    assert payload["articles"][0]["title"] == "Deep learning"


def test_excel_has_three_sheets(profile):
    data = to_excel_bytes(profile)
    sheets = pd.read_excel(BytesIO(data), sheet_name=None)
    assert set(sheets) == {"Artikel", "Profil", "Sitasi per Tahun"}
    assert len(sheets["Artikel"]) == 3
    assert sheets["Artikel"].iloc[0]["Judul"] == "Deep learning"


def test_search_frame(search):
    frame = search_frame(search)
    assert list(frame.columns) == SEARCH_COLUMNS
    assert len(frame) == 3
    assert frame.iloc[0]["Judul"].startswith("A review")
    assert frame.iloc[0]["Penerbit"] == "JSTOR"
    assert int(frame.iloc[0]["Sitasi"]) == 466
    assert str(frame["Tahun"].dtype) == "Int64"


def test_search_info_frame(search):
    frame = search_info_frame(search)
    values = dict(zip(frame["Atribut"], frame["Nilai"]))
    assert values["Kata kunci"] == "machine learning education"
    assert values["Batas hasil"] == "20 hasil"
    assert values["Hasil terbaca"] == 3
    assert values["Rentang tahun"] == "Semua tahun"


def test_search_info_frame_all_pages():
    search = ScholarSearch(
        query="machine learning education",
        max_results=None,
        total_label="About 5.460.000 results",
    )
    info = search_info_frame(search)
    values = dict(zip(info["Atribut"], info["Nilai"]))
    assert values["Batas hasil"] == "Semua halaman (maks. 1.000 hasil)"


def test_search_info_frame_unlimited():
    search = ScholarSearch(
        query="machine learning education",
        max_results=None,
        safety_cap=None,
        total_label="About 5.460.000 results",
    )
    info = search_info_frame(search)
    values = dict(zip(info["Atribut"], info["Nilai"]))
    assert values["Batas hasil"] == "Tidak dibatasi"


def test_search_csv(search):
    data = search_to_csv_bytes(search)
    assert data.startswith(b"\xef\xbb\xbf")
    assert "machine learning education" in data.decode("utf-8-sig")


def test_search_json(search):
    payload = json.loads(search_to_json_bytes(search))
    assert payload["query"] == "machine learning education"
    assert payload["result_count"] == 3
    assert payload["results"][0]["publication_id"] == "hz3AS4i1RYcJ"


def test_search_excel(search):
    data = search_to_excel_bytes(search)
    sheets = pd.read_excel(BytesIO(data), sheet_name=None)
    assert set(sheets) == {"Hasil", "Pencarian"}
    assert len(sheets["Hasil"]) == 3
    assert sheets["Hasil"].iloc[0]["Venue"] == "Educational Technology & Society"
