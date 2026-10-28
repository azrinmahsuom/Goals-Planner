"""The page in a real (headless) browser: no script errors, labelled inputs, no horizontal
scrolling at phone width, the four-set headline, and the SRS warning following the age input.
Skipped where Playwright's browser isn't installed (e.g. CI)."""

import pytest

from analysis.config import ROOT

sync_api = pytest.importorskip("playwright.sync_api")
PAGE = (ROOT / "app" / "index.html").as_uri()
READY = (
    "document.getElementById('results').getAttribute('aria-busy') === 'false'"
    " && document.getElementById('headline').children.length === 4"
)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as err:  # browser binary not installed
            pytest.skip(f"Chromium not available: {err}")
        yield b
        b.close()


def open_page(browser, width: int, scheme: str = "light"):
    page = browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(PAGE)
    page.wait_for_function(READY, timeout=60_000)
    return page, errors


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "light"), (390, "dark")])
def test_page_renders_without_errors_or_horizontal_scroll(browser, width, scheme):
    page, errors = open_page(browser, width, scheme)
    assert errors == []
    assert page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 0
    assert page.locator("#headline .card").count() == 4
    assert page.locator("#headline .card.reference").count() == 1
    assert "no single answer" in page.text_content("#spread")
    page.close()


def test_every_input_has_a_label(browser):
    page, _ = open_page(browser, 1280)
    unlabeled = page.evaluate(
        "[...document.querySelectorAll('input, select')]"
        ".filter(e => !e.labels || e.labels.length === 0).map(e => e.id)"
    )
    assert unlabeled == []
    page.close()


def test_srs_warning_follows_the_statutory_age_input(browser):
    page, errors = open_page(browser, 1280)
    page.click("text=Example D")
    page.check("#srs-on")
    page.fill("#years", "23")  # age 40 + 23 = 63
    page.select_option("#sra", "62")
    page.wait_for_timeout(400)
    page.wait_for_function(READY, timeout=60_000)
    assert page.evaluate("document.getElementById('srs-warning').hidden") is True
    page.select_option("#sra", "64")
    page.wait_for_timeout(400)
    page.wait_for_function(READY, timeout=60_000)
    assert page.evaluate("document.getElementById('srs-warning').hidden") is False
    assert "(64)" in page.text_content("#srs-warning")
    assert errors == []
    page.close()


def test_preset_shows_the_full_engine_result_and_gap(browser):
    page, _ = open_page(browser, 1280)
    text = page.text_content("#headline")
    assert "Full engine:" in text and "simplified engine" in text
    page.fill("#goal", "650000")  # no longer a preset
    page.wait_for_timeout(400)
    page.wait_for_function(READY, timeout=60_000)
    assert "Full engine:" not in page.text_content("#headline")
    assert "lower in" in page.text_content("#engine-note")
    page.close()
