"""Unit tests for welcome email HTML generation."""
import os
from unittest.mock import patch

import pytest

from notifications.email import _build_html, send_welcome_email


APPLE_URL = "https://ryetri-dev-func.azurewebsites.net/api/pass/test-apple-id"
GOOGLE_URL = "https://pay.google.com/gp/v/save/test-jwt"


def test_email_contains_first_name():
    html = _build_html("Jane Smith", "M001", "2099-12-31", APPLE_URL, GOOGLE_URL)
    assert "Jane" in html


def test_email_contains_member_number():
    html = _build_html("Jane Smith", "M001", "2099-12-31", APPLE_URL, GOOGLE_URL)
    assert "M001" in html


def test_email_apple_button_shown():
    html = _build_html("Jane Smith", "M001", "2099-12-31", APPLE_URL, GOOGLE_URL)
    assert "Add to Apple Wallet" in html
    assert APPLE_URL in html


def test_email_google_button_shown():
    html = _build_html("Jane Smith", "M001", "2099-12-31", APPLE_URL, GOOGLE_URL)
    assert "Add to Google Wallet" in html
    assert GOOGLE_URL in html


def test_email_no_apple_button_when_no_url():
    html = _build_html("Jane Smith", "M001", "2099-12-31", None, GOOGLE_URL)
    assert "Add to Apple Wallet" not in html


def test_email_no_google_button_when_no_url():
    html = _build_html("Jane Smith", "M001", "2099-12-31", APPLE_URL, None)
    assert "Add to Google Wallet" not in html


def test_email_no_buttons_when_no_urls():
    html = _build_html("Jane Smith", "M001", "2099-12-31", None, None)
    assert "Add to Apple Wallet" not in html
    assert "Add to Google Wallet" not in html


def test_email_contains_reissue_link():
    html = _build_html("Jane Smith", "M001", "2099-12-31", APPLE_URL, GOOGLE_URL)
    assert "membercardrenewal.ryetriclub.com" in html


def test_email_skipped_without_api_key():
    with patch.dict(os.environ, {"SENDGRID_API_KEY": ""}):
        # Re-read settings to pick up the empty value
        from config import settings
        with patch.object(settings.Settings, "SENDGRID_API_KEY", ""):
            result = send_welcome_email(
                "Jane Smith", "jane@example.com", "M001", "2099-12-31",
                APPLE_URL, GOOGLE_URL,
            )
    assert result is False
