from __future__ import annotations

from pathlib import Path

import pytest
from scrapling.parser import Selector

from scholar_scraper.errors import AccessBlockedError
from scholar_scraper.models import ScholarSearch
from scholar_scraper.search import (
    ScholarSearcher,
    SearchOptions,
    build_search_url,
    detect_search_block,
    parse_byline,
    parse_search_page,
    parse_total_label,
    search_has_more,
    search_is_empty,
)

FIXTURE = Path(__file__).parent / "fixtures" / "search_page.html"


@pytest.fixture(scope="module")
def page():
    return Selector(FIXTURE.read_text(encoding="utf-8"))


def make_search_page(count: int, *, more: bool, start: int = 0) -> Selector:
    """Bangun halaman pencarian sintetis dengan jumlah hasil yang bisa diatur."""
    fixture = Selector(FIXTURE.read_text(encoding="utf-8"))
    template = fixture.css("div.gs_r.gs_or.gs_scl")[0].html_content
    blocks = []
    for offset in range(count):
        index = start + offset
        cid = f"cid{index:06d}"
        blocks.append(template.replace("hz3AS4i1RYcJ", cid))
    next_button = (
        '<button type="button" aria-label="Next">Next</button>' if more else ""
    )
    html = (
        "<html><body>"
        '<div id="gs_ab_md"><div class="gs_ab_mdw">About 100 results</div></div>'
        + "".join(blocks)
        + f'<div id="gs_nm">{next_button}</div>'
        + "</body></html>"
    )
    return Selector(html)


def test_default_options():
    options = SearchOptions()
    assert options.engine == "browser"
    assert options.max_results == 20
    assert options.sort == "relevance"


class TestBuildSearchUrl:
    def test_default_url(self):
        url = build_search_url("machine learning")
        assert url.startswith("https://scholar.google.com/scholar?")
        assert "q=machine+learning" in url
        assert "hl=en" in url
        assert "as_sdt=0%2C5" in url
        assert "start=" not in url
        assert "as_ylo" not in url

    def test_pagination_and_years(self):
        url = build_search_url(
            "machine learning",
            start=20,
            year_from=2020,
            year_to=2024,
            sort="date",
        )
        assert "start=20" in url
        assert "as_ylo=2020" in url
        assert "as_yhi=2024" in url
        assert "scisbd=1" in url

    def test_phrase_is_encoded(self):
        url = build_search_url('"machine learning" education')
        assert "%22machine+learning%22+education" in url

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"query": ""},
            {"query": "   "},
            {"query": "x" * 501},
            {"query": "ok", "sort": "citations"},
            {"query": "ok", "year_from": 2024, "year_to": 2020},
            {"query": "ok", "year_from": 1000},
        ],
    )
    def test_rejects_invalid_input(self, kwargs):
        with pytest.raises(ValueError):
            build_search_url(**kwargs)


class TestParseByline:
    def test_full_byline(self):
        assert parse_byline(
            "H Luan, CC Tsai - Educational Technology & Society, 2021 - JSTOR"
        ) == ("H Luan, CC Tsai", "Educational Technology & Society", "JSTOR", 2021)

    def test_without_publisher(self):
        assert parse_byline("A Smith, B Jones - Journal of Learning, 2020") == (
            "A Smith, B Jones",
            "Journal of Learning",
            "",
            2020,
        )

    def test_year_only(self):
        assert parse_byline("A Smith - 2021") == ("A Smith", "", "", 2021)

    def test_empty(self):
        assert parse_byline("") == ("", "", "", None)


class TestParseSearchPage:
    def test_result_count_skips_non_results(self, page):
        results = parse_search_page(page)
        assert len(results) == 3

    def test_first_result(self, page):
        first = parse_search_page(page)[0]
        assert first.index == 1
        assert first.title == (
            "A review of using machine learning approaches for precision education"
        )
        assert first.authors == "H Luan, CC Tsai"
        assert first.venue == "Educational Technology & Society"
        assert first.publisher == "JSTOR"
        assert first.year == 2021
        assert first.citations == 466
        assert first.article_url == "https://www.jstor.org/stable/26977871"
        assert first.pdf_url.endswith("ETS_24_1_19.pdf")
        assert first.citations_url.startswith(
            "https://scholar.google.com/scholar?cites="
        )
        assert first.cluster_url.startswith(
            "https://scholar.google.com/scholar?cluster="
        )
        assert "precision education" in first.snippet
        assert first.publication_id == "hz3AS4i1RYcJ"

    def test_title_badges_are_stripped(self, page):
        second = parse_search_page(page)[1]
        assert second.title.startswith("A systematic review")
        assert "[PDF]" not in second.title
        assert second.year == 2023
        assert second.publisher == "Springer"

    def test_missing_fields_are_safe(self, page):
        third = parse_search_page(page)[2]
        assert third.title.startswith("Learning analytics")
        assert third.pdf_url == ""
        assert third.citations is None
        assert third.cluster_url == ""
        assert third.publisher == ""

    def test_custom_start_index(self, page):
        results = parse_search_page(page, start_index=11)
        assert [result.index for result in results] == [11, 12, 13]

    def test_indonesian_citation_label(self):
        html = (
            '<div class="gs_r gs_or gs_scl" data-cid="idResult01">'
            '<div class="gs_ri">'
            '<h3 class="gs_rt"><a href="https://example.org/a">Judul uji</a></h3>'
            '<div class="gs_a">A B - Jurnal Uji, 2020 - Penerbit</div>'
            '<div class="gs_fl">'
            '<a href="/scholar?cites=1">Dirujuk 466 kali</a>'
            "</div></div></div>"
        )
        results = parse_search_page(Selector(html))
        assert results[0].citations == 466
        assert results[0].venue == "Jurnal Uji"


class TestPageMeta:
    def test_total_label(self, page):
        label = parse_total_label(page)
        assert label.startswith("About 5.460.000 results")
        assert search_has_more(page) is True
        assert search_is_empty(page) is False

    def test_no_more_button(self):
        page = Selector('<html><body><div id="gs_nm"></div></body></html>')
        assert search_has_more(page) is False

    def test_empty_result_message(self):
        page = Selector(
            "<html><body>Your search did not match any articles.</body></html>"
        )
        assert search_is_empty(page) is True


class TestSearchBlockDetection:
    def test_sgsync_redirect(self):
        reason = detect_search_block(
            200,
            "https://www.google.com/sgsync?url=https%3A%2F%2Fscholar.google.com",
            "<html></html>",
        )
        assert reason is not None
        assert "sgsync" in reason

    def test_verifying_title(self):
        reason = detect_search_block(
            200,
            "https://scholar.google.com/scholar?q=x",
            "<html><head><title>Verifying...</title></head></html>",
        )
        assert reason is not None

    def test_normal_page(self):
        assert (
            detect_search_block(
                200,
                "https://scholar.google.com/scholar?q=x",
                "<html><title>machine learning - Google Scholar</title></html>",
            )
            is None
        )


class TestOptionsValidation:
    @pytest.mark.parametrize("engine", ["", "selenium", "Browser"])
    def test_invalid_engine(self, engine):
        with pytest.raises(ValueError, match="engine"):
            ScholarSearcher(SearchOptions(engine=engine))

    @pytest.mark.parametrize("sort", ["", "newest"])
    def test_invalid_sort(self, sort):
        with pytest.raises(ValueError, match="sort"):
            ScholarSearcher(SearchOptions(sort=sort))

    @pytest.mark.parametrize("max_results", [0, -1, 1001])
    def test_invalid_max_results(self, max_results):
        with pytest.raises(ValueError, match="max_results"):
            ScholarSearcher(SearchOptions(max_results=max_results))

    def test_all_pages_option_is_valid(self):
        searcher = ScholarSearcher(SearchOptions(max_results=None))
        assert searcher.options.max_results is None

    def test_unlimited_option_is_valid(self):
        searcher = ScholarSearcher(
            SearchOptions(max_results=None, safety_cap=None)
        )
        assert searcher.options.max_results is None
        assert searcher.options.safety_cap is None

    @pytest.mark.parametrize("safety_cap", [0, -1])
    def test_invalid_safety_cap(self, safety_cap):
        with pytest.raises(ValueError, match="safety_cap"):
            ScholarSearcher(SearchOptions(safety_cap=safety_cap))

    @pytest.mark.parametrize("delay_mode", ["", "fast", "SAFE"])
    def test_invalid_delay_mode(self, delay_mode):
        with pytest.raises(ValueError, match="delay_mode"):
            ScholarSearcher(SearchOptions(delay_mode=delay_mode))

    def test_year_range_order(self):
        with pytest.raises(ValueError, match="Tahun awal"):
            ScholarSearcher(SearchOptions(year_from=2024, year_to=2020))


class TestAutoEngine:
    def test_http_block_falls_back_to_browser(self, monkeypatch):
        searcher = ScholarSearcher(SearchOptions(engine="auto"))
        calls: list[str] = []
        sentinel = object()

        def fake_search_with(engine, query, callback):
            calls.append(engine)
            if engine == "http":
                raise AccessBlockedError("dialihkan ke sgsync")
            return sentinel

        monkeypatch.setattr(searcher, "_search_with", fake_search_with)
        assert searcher.search("machine learning") is sentinel
        assert calls == ["http", "browser"]


class TestTotalEstimate:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("About 5.460.000 results (0,09 sec)", 5_460_000),
            ("About 3 results", 3),
            ("Sekitar 1.230 hasil (0,05 detik)", 1_230),
            ("", None),
            ("Jumlah total tidak tersedia", None),
        ],
    )
    def test_parses_only_result_count(self, label, expected):
        assert ScholarSearch(query="x", total_label=label).total_estimate == expected


class TestPagination:
    def test_two_pages(self, monkeypatch):
        searcher = ScholarSearcher(
            SearchOptions(
                max_results=20,
                engine="browser",
                delay_mode="fixed",
                delay=0,
            )
        )
        requested: list[str] = []
        pages = [
            make_search_page(10, more=True, start=0),
            make_search_page(10, more=True, start=10),
        ]

        def fake_get(session, engine, url):
            requested.append(url)
            return pages[len(requested) - 1]

        monkeypatch.setattr(searcher, "_get", fake_get)
        search = searcher._paginate(object(), "browser", "machine learning", None)

        assert len(requested) == 2
        assert "start=10" in requested[1]
        assert len(search.results) == 20
        assert search.pages_fetched == 2
        assert search.has_more is True

    def test_stops_when_no_next_page(self, monkeypatch):
        searcher = ScholarSearcher(
            SearchOptions(
                max_results=50,
                engine="browser",
                delay_mode="fixed",
                delay=0,
            )
        )
        requested: list[str] = []

        def fake_get(session, engine, url):
            requested.append(url)
            return make_search_page(5, more=False)

        monkeypatch.setattr(searcher, "_get", fake_get)
        search = searcher._paginate(object(), "browser", "machine learning", None)

        assert len(requested) == 1
        assert len(search.results) == 5
        assert search.has_more is False

    def test_duplicate_results_are_dropped(self, monkeypatch):
        searcher = ScholarSearcher(
            SearchOptions(
                max_results=20,
                engine="browser",
                delay_mode="fixed",
                delay=0,
            )
        )
        requested: list[str] = []
        pages = [
            make_search_page(10, more=True, start=0),
            make_search_page(10, more=True, start=0),
        ]

        def fake_get(session, engine, url):
            requested.append(url)
            return pages[len(requested) - 1]

        monkeypatch.setattr(searcher, "_get", fake_get)
        search = searcher._paginate(object(), "browser", "machine learning", None)

        assert len(search.results) == 10
        assert search.pages_fetched == 2

    def test_all_pages_until_no_next(self, monkeypatch):
        searcher = ScholarSearcher(
            SearchOptions(
                max_results=None,
                engine="browser",
                delay_mode="fixed",
                delay=0,
            )
        )
        requested: list[str] = []
        pages = [
            make_search_page(10, more=True, start=0),
            make_search_page(10, more=True, start=10),
            make_search_page(5, more=False, start=20),
        ]

        def fake_get(session, engine, url):
            requested.append(url)
            return pages[len(requested) - 1]

        monkeypatch.setattr(searcher, "_get", fake_get)
        search = searcher._paginate(object(), "browser", "machine learning", None)

        assert len(requested) == 3
        assert len(search.results) == 25
        assert search.pages_fetched == 3
        assert search.has_more is False
        assert search.max_results is None

    def test_all_pages_respects_safety_cap(self, monkeypatch):
        searcher = ScholarSearcher(
            SearchOptions(
                max_results=None,
                safety_cap=15,
                engine="browser",
                delay_mode="fixed",
                delay=0,
            )
        )
        requested: list[str] = []
        pages = [
            make_search_page(10, more=True, start=0),
            make_search_page(10, more=True, start=10),
        ]

        def fake_get(session, engine, url):
            requested.append(url)
            return pages[len(requested) - 1]

        monkeypatch.setattr(searcher, "_get", fake_get)
        search = searcher._paginate(object(), "browser", "machine learning", None)

        assert len(requested) == 2
        assert len(search.results) == 15
        assert search.has_more is True

    def test_unlimited_pages_until_no_next(self, monkeypatch):
        searcher = ScholarSearcher(
            SearchOptions(
                max_results=None,
                safety_cap=None,
                engine="browser",
                delay_mode="fixed",
                delay=0,
            )
        )
        requested: list[str] = []
        pages = [
            make_search_page(10, more=True, start=0),
            make_search_page(10, more=True, start=10),
            make_search_page(10, more=True, start=20),
            make_search_page(5, more=False, start=30),
        ]

        def fake_get(session, engine, url):
            requested.append(url)
            return pages[len(requested) - 1]

        monkeypatch.setattr(searcher, "_get", fake_get)
        search = searcher._paginate(object(), "browser", "machine learning", None)

        assert len(requested) == 4
        assert len(search.results) == 35
        assert search.pages_fetched == 4
        assert search.has_more is False
        assert search.safety_cap is None


class TestPageDelay:
    def test_safe_and_very_safe_ranges(self, monkeypatch):
        calls: list[tuple[float, float]] = []

        def fake_uniform(low, high):
            calls.append((low, high))
            return 7.5

        monkeypatch.setattr("scholar_scraper.search.random.uniform", fake_uniform)

        safe = ScholarSearcher(SearchOptions(delay_mode="safe"))
        assert safe._page_wait() == 7.5
        very_safe = ScholarSearcher(SearchOptions(delay_mode="very_safe"))
        assert very_safe._page_wait() == 7.5
        assert calls == [(5.0, 12.0), (12.0, 25.0)]

    def test_fixed_delay_uses_manual_value(self, monkeypatch):
        def fail_uniform(low, high):  # pragma: no cover - tidak boleh dipanggil
            raise AssertionError("random.uniform tidak dipakai pada mode fixed")

        monkeypatch.setattr("scholar_scraper.search.random.uniform", fail_uniform)
        searcher = ScholarSearcher(SearchOptions(delay_mode="fixed", delay=3.5))
        assert searcher._page_wait() == 3.5


def test_limit_inside_last_search_page(monkeypatch):
    searcher = ScholarSearcher(SearchOptions(max_results=2))
    monkeypatch.setattr(searcher, "_get", lambda *_: make_search_page(5, more=False, start=0))
    search = searcher._paginate(object(), "http", "test", None)
    assert len(search.results) == 2
    assert search.has_more
