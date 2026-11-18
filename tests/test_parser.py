from __future__ import annotations

from pathlib import Path

import pytest
from scrapling.parser import Selector

from scholar_scraper.errors import InvalidProfileError
from scholar_scraper.parser import (
    build_profile_url,
    detect_block,
    extract_scholar_id,
    is_login_redirect,
    parse_articles,
    parse_citation_history,
    parse_header,
    parse_metrics,
    parse_profile_page,
)

FIXTURE = Path(__file__).parent / "fixtures" / "profile_page.html"


@pytest.fixture(scope="module")
def page():
    return Selector(FIXTURE.read_text(encoding="utf-8"))


class TestExtractScholarId:
    def test_accepts_raw_id(self):
        assert extract_scholar_id("kukA0LcAAAAJ") == "kukA0LcAAAAJ"

    def test_accepts_full_url(self):
        url = "https://scholar.google.com/citations?hl=id&user=kukA0LcAAAAJ"
        assert extract_scholar_id(url) == "kukA0LcAAAAJ"

    def test_accepts_country_domain(self):
        url = "https://scholar.google.co.id/citations?user=kukA0LcAAAAJ"
        assert extract_scholar_id(url) == "kukA0LcAAAAJ"

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            "https://example.com/citations?user=kukA0LcAAAAJ",
            "https://scholar.google.com.evil.com/citations?user=kukA0LcAAAAJ",
            "https://scholar.google.com/citations?view_op=search_authors",
            "id dengan spasi",
        ],
    )
    def test_rejects_invalid_input(self, value):
        with pytest.raises(InvalidProfileError):
            extract_scholar_id(value)

    def test_url_without_scheme(self):
        url = "scholar.google.com/citations?user=kukA0LcAAAAJ"
        assert extract_scholar_id(url) == "kukA0LcAAAAJ"


class TestBuildUrl:
    def test_default_has_no_cstart(self):
        url = build_profile_url("kukA0LcAAAAJ")
        assert "user=kukA0LcAAAAJ" in url
        assert "pagesize=100" in url
        assert "cstart" not in url

    def test_pagination_only_when_requested(self):
        url = build_profile_url("kukA0LcAAAAJ", cstart=100)
        assert "cstart=100" in url

    def test_sort_parameter(self):
        url = build_profile_url("kukA0LcAAAAJ", sort="year")
        assert "sortby=pubdate" in url
        assert "view_op=list_works" in url


class TestParseProfile:
    def test_header(self, page):
        header = parse_header(page)
        assert header.name == "Yoshua Bengio"
        assert "University of Montreal" in header.affiliation
        assert header.email == "Verified email at umontreal.ca"
        assert header.homepage == "https://yoshuabengio.org/"
        assert header.interests == (
            "Machine learning",
            "deep learning",
            "artificial intelligence",
        )

    def test_metrics_all_time_and_recent(self, page):
        metrics, recent, since_year = parse_metrics(page)
        assert metrics.citations == 1191845
        assert metrics.h_index == 263
        assert metrics.i10_index == 1131
        assert recent.citations == 804387
        assert recent.h_index == 216
        assert since_year == 2021

    def test_articles(self, page):
        articles = parse_articles(page)
        assert len(articles) == 3
        first = articles[0]
        assert first.index == 1
        assert first.title == "Deep learning"
        assert first.authors == "Y LeCun, Y Bengio, G Hinton"
        assert first.venue == "nature 521 (7553), 436-444"
        assert first.year == 2015
        assert first.citations == 123987
        assert first.article_url.startswith(
            "https://scholar.google.com/citations?"
        )
        assert first.citations_url.startswith("https://scholar.google.com/scholar?")
        assert first.publication_id == "naSTrk-c4S8C"

    def test_citation_history_is_sorted(self, page):
        history = parse_citation_history(page)
        assert len(history) == 6
        assert [item.year for item in history] == sorted(
            item.year for item in history
        )
        assert history[-1].year == 2026

    def test_full_profile(self, page):
        profile = parse_profile_page(page, "kukA0LcAAAAJ")
        assert profile.name == "Yoshua Bengio"
        assert len(profile.articles) == 3
        assert profile.source_url == (
            "https://scholar.google.com/citations?user=kukA0LcAAAAJ&hl=en"
        )
        assert profile.has_more is False
        assert profile.fetched_at is not None


class TestBlockDetection:
    def test_http_status(self):
        assert detect_block(429, "", "") == "HTTP 429"
        assert detect_block(403, "", "") == "HTTP 403"

    def test_captcha_html(self):
        html = '<form id="gs_captcha_f"></form>'
        assert detect_block(200, "https://scholar.google.com/sorry/index", html) == (
            "halaman verifikasi Google"
        )
        assert detect_block(200, "https://scholar.google.com/citations", html) == "CAPTCHA"

    def test_normal_page(self):
        assert detect_block(200, "https://scholar.google.com/citations?user=x", "<html></html>") is None

    def test_login_redirect(self):
        assert is_login_redirect("https://accounts.google.com/v3/signin/identifier")
        assert not is_login_redirect("https://scholar.google.com/citations?user=x")
