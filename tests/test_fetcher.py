from __future__ import annotations

from pathlib import Path

import pytest
from scrapling.parser import Selector

from scholar_scraper.fetcher import ScholarScraper, ScrapeOptions

FIXTURE = Path(__file__).parent / "fixtures" / "profile_page.html"


def make_page(row_count: int, *, more: bool, start: int = 1) -> Selector:
    """Bangun halaman sintetis dengan jumlah baris artikel yang bisa diatur."""
    fixture = Selector(FIXTURE.read_text(encoding="utf-8"))
    header = fixture.css("#gsc_prf_i")[0].html_content
    metrics = fixture.css("#gsc_rsb_st")[0].html_content
    template = fixture.css("tr.gsc_a_tr")[0].html_content
    rows = []
    for offset in range(row_count):
        index = start + offset
        rows.append(
            template.replace("Deep learning", f"Artikel uji {index}").replace(
                "naSTrk-c4S8C", f"pubID{index:04d}"
            )
        )
    more_button = '<button id="gsc_bpf_more"></button>' if more else ""
    return Selector(
        "<html><body>"
        + header
        + metrics
        + "".join(rows)
        + f'<span id="gsc_a_nn">Articles {start}–{start + row_count - 1}</span>'
        + more_button
        + "</body></html>"
    )


def test_default_is_single_page():
    scraper = ScholarScraper()
    assert scraper.options.max_articles == 100
    assert scraper.options.allow_pagination is False


def test_pagination_needs_explicit_consent():
    with pytest.raises(ValueError, match="allow_pagination"):
        ScholarScraper(ScrapeOptions(max_articles=200))


def test_pagination_with_consent_is_valid():
    scraper = ScholarScraper(
        ScrapeOptions(max_articles=200, allow_pagination=True)
    )
    assert scraper.options.max_articles == 200


@pytest.mark.parametrize("engine", ["", "selenium", "HTTP"])
def test_invalid_engine(engine):
    with pytest.raises(ValueError, match="engine"):
        ScholarScraper(ScrapeOptions(engine=engine))


@pytest.mark.parametrize("sort", ["", "citations_desc"])
def test_invalid_sort(sort):
    with pytest.raises(ValueError, match="sort"):
        ScholarScraper(ScrapeOptions(sort=sort))


def test_invalid_timeout():
    with pytest.raises(ValueError, match="timeout"):
        ScholarScraper(ScrapeOptions(timeout=1))


def test_default_fetch_never_uses_cstart(monkeypatch):
    scraper = ScholarScraper(
        ScrapeOptions(max_articles=100, allow_pagination=False, delay=0)
    )
    requested: list[str] = []

    def fake_get(session, engine, url):
        requested.append(url)
        return make_page(20, more=True)

    monkeypatch.setattr(scraper, "_get", fake_get)
    profile = scraper._paginate(object(), "http", "kukA0LcAAAAJ", None)

    assert len(requested) == 1
    assert "cstart" not in requested[0]
    assert len(profile.articles) == 20
    assert profile.has_more is True


def test_pagination_uses_actual_row_count_as_offset(monkeypatch):
    scraper = ScholarScraper(
        ScrapeOptions(
            max_articles=100, allow_pagination=True, delay=0, engine="http"
        )
    )
    pages = [
        make_page(20, more=True, start=1),
        make_page(5, more=False, start=21),
    ]
    requested: list[str] = []

    def fake_get(session, engine, url):
        requested.append(url)
        return pages[len(requested) - 1]

    monkeypatch.setattr(scraper, "_get", fake_get)
    profile = scraper._paginate(object(), "http", "kukA0LcAAAAJ", None)

    assert len(profile.articles) == 25
    assert profile.pages_fetched == 2
    assert "cstart=20" in requested[1]
    assert "cstart=100" not in requested[1]
    assert profile.has_more is False
