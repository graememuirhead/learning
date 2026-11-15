"""
Smoke tests: send real emails to graeme@ryetriclub.com.

Smoke test #1 — new passes via MembershipActivated webhook:
    pytest tests/integration/test_smoke_email.py::test_smoke_welcome_email -v -m smoke -s

Smoke test #2 — reissue (void + recreate) via self-service endpoint:
    pytest tests/integration/test_smoke_email.py::test_smoke_reissue_pass -v -m smoke -s

Run test #1 first; test #2 operates on the same member.
These tests are excluded from normal CI runs.
"""
import os

import pytest
import requests

SMOKE_MEMBER_NUMBER = "TEST99999"
SMOKE_EMAIL = "graeme@ryetriclub.com"


@pytest.mark.smoke
def test_smoke_welcome_email(func_url):
    """
    Issue (or reissue) a membership card for the smoke member via manual-send-card.
    This always voids any existing pass and sends a fresh welcome email, making it
    reliable regardless of how many times the smoke test runs in the same day.
    Check graeme@ryetriclub.com for the welcome email with Apple + Google buttons.
    """
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    if not admin_secret:
        pytest.skip("ADMIN_SECRET not set")

    resp = requests.post(
        f"{func_url}/manual-send-card",
        json={
            "admin_secret": admin_secret,
            "member_number": SMOKE_MEMBER_NUMBER,
            "email": SMOKE_EMAIL,
            "name": "Test Member",
            "expiry_date": "2099-12-31",
        },
        timeout=60,
    )
    assert resp.status_code == 200, f"manual-send-card returned {resp.status_code}: {resp.text[:300]}"
    print(f"\n  Smoke member: {SMOKE_MEMBER_NUMBER}")
    print("✓ Card issued. Check graeme@ryetriclub.com for the welcome email.")


@pytest.mark.smoke
def test_smoke_reissue_pass(func_url):
    """
    Reissue passes for today's smoke member via the self-service /reissue-pass endpoint.
    Voids the existing passes and creates fresh ones, then sends a welcome email.

    Run test_smoke_welcome_email first (within the same hour) to create the initial passes.
    """
    member_number = SMOKE_MEMBER_NUMBER
    email = SMOKE_EMAIL

    print(f"\n  Reissuing passes for smoke member: {member_number}")

    resp = requests.post(
        f"{func_url}/reissue-pass",
        json={"member_number": member_number, "email": email},
        timeout=60,
    )
    assert resp.status_code == 200, f"Reissue returned {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert "reissued" in data.get("message", "").lower(), f"Unexpected response: {data}"

    apple_url  = data.get("apple_pass_url")
    google_url = data.get("google_save_url")
    email_sent = data.get("email_sent", False)

    assert apple_url or google_url, "No pass URL returned — card was not issued"
    assert email_sent, "Pass issued but email was not sent"

    print("✓ New card issued successfully.")
    if apple_url:
        print(f"  Apple pass : {apple_url}")
    if google_url:
        print(f"  Google pass: {google_url}")
    print(f"  Email sent : {email_sent}")
    print("  Check graeme@ryetriclub.com for the new welcome email.")
