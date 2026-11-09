"""E2E tests for the static reissue page using Playwright."""
import os

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def site_url() -> str:
    url = os.environ.get("DEV_STATIC_URL", "").rstrip("/")
    if not url:
        pytest.skip("DEV_STATIC_URL not set — skipping E2E tests")
    return url


def test_page_loads(page: Page, site_url: str):
    page.goto(site_url)
    expect(page.locator("#member_number")).to_be_visible()
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#submit-btn")).to_be_visible()


def test_page_shows_logo(page: Page, site_url: str):
    page.goto(site_url)
    logo = page.locator("img.logo")
    expect(logo).to_be_visible()
    # Verify image loaded (naturalWidth > 0)
    natural_width = logo.evaluate("img => img.naturalWidth")
    assert natural_width > 0, "Logo image did not load"


def test_empty_submit_shows_error(page: Page, site_url: str):
    page.goto(site_url)
    page.click("#submit-btn")
    expect(page.locator("#alert")).to_be_visible()
    expect(page.locator("#alert")).to_contain_text("membership number")


def test_invalid_combination_shows_error(page: Page, site_url: str):
    page.goto(site_url)
    page.fill("#member_number", "FAKEMEMBER")
    page.fill("#email", "nobody@example.com")
    page.click("#submit-btn")
    expect(page.locator("#alert")).to_be_visible(timeout=15_000)
    expect(page.locator("#alert")).to_contain_text("No membership found")


def test_valid_submission_shows_success(page: Page, site_url: str):
    page.goto(site_url)
    page.fill("#member_number", "TEST99999")
    page.fill("#email", "test@ryetriclub.com")
    page.click("#submit-btn")
    # Form should hide and success alert should appear
    expect(page.locator("#form")).to_be_hidden(timeout=30_000)
    expect(page.locator("#alert")).to_be_visible()
    expect(page.locator("#alert")).to_contain_text("Check your email")


def test_spinner_shown_during_submit(page: Page, site_url: str):
    page.goto(site_url)
    page.fill("#member_number", "FAKEMEMBER")
    page.fill("#email", "nobody@example.com")

    with page.expect_request("**/reissue-pass"):
        page.click("#submit-btn")
        # Spinner should appear while request is in-flight
        expect(page.locator(".spinner")).to_be_visible()


def test_mobile_layout_no_overflow(page: Page, site_url: str):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(site_url)
    scroll_width = page.evaluate("document.body.scrollWidth")
    client_width = page.evaluate("document.body.clientWidth")
    assert scroll_width <= client_width, (
        f"Horizontal overflow: scrollWidth={scroll_width} > clientWidth={client_width}"
    )
