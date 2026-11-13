"""
Smoke tests: send real emails to graeme@ryetriclub.com.

Run manually to verify the email template and pass links look correct end-to-end.

    # First issue (MembershipActivated webhook):
    pytest tests/integration/test_smoke_email.py::test_smoke_welcome_email -v -m smoke -s

    # Re-issue (self-service reissue endpoint) — run after the first test has fired today:
    pytest tests/integration/test_smoke_email.py::test_smoke_reissue_pass -v -m smoke -s

These tests are excluded from normal CI runs.
"""
from datetime import date

import pytest
import requests


def _smoke_payload() -> dict:
    # Use a date-based member ID so each calendar day gets fresh passes.
    # Format: 9YYYYMMDD fits in an int and is clearly a test ID (starts with 9).
    member_id = int(f"9{date.today().strftime('%Y%m%d')}")
    return {
        "EventType": "MembershipActivated",
        "AccountId": 123456,
        "Parameters": {
            "Contact": {
                "FirstName": "Graeme",
                "LastName": "Muirhead",
                "Email": "graeme@ryetriclub.com",
                "Id": member_id,
                "RenewalDue": "2099-12-31T00:00:00",
            }
        },
    }


@pytest.mark.smoke
def test_smoke_welcome_email(func_url, webhook_secret):
    """
    Trigger a MembershipActivated webhook for member 99997 (graeme@ryetriclub.com).
    A welcome email with Apple and Google pass links is sent to that address.
    Check your inbox to verify the email layout and that both pass links work.
    """
    if not webhook_secret:
        pytest.skip("DEV_WEBHOOK_SECRET not set")

    payload = _smoke_payload()
    member_id = payload["Parameters"]["Contact"]["Id"]
    print(f"\n  Smoke member ID for today: {member_id}")

    resp = requests.post(
        f"{func_url}/webhook/wild-apricot",
        params={"secret": webhook_secret},
        json=payload,
        timeout=60,
    )
    assert resp.status_code == 200, f"Webhook returned {resp.status_code}: {resp.text[:300]}"
    print("✓ Webhook accepted. Check graeme@ryetriclub.com for the welcome email.")


@pytest.mark.smoke
def test_smoke_reissue_pass(func_url):
    """
    Reissue passes for today's smoke member via the self-service /reissue-pass endpoint.
    Voids the existing passes and creates fresh ones, then sends a welcome email.

    Requires test_smoke_welcome_email to have run first today (to create the initial passes).
    """
    member_id = int(f"9{date.today().strftime('%Y%m%d')}")
    member_number = str(member_id)
    email = "graeme@ryetriclub.com"

    print(f"\n  Reissuing passes for smoke member: {member_number}")

    resp = requests.post(
        f"{func_url}/reissue-pass",
        json={"member_number": member_number, "email": email},
        timeout=60,
    )
    assert resp.status_code == 200, f"Reissue returned {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert "reissued" in data.get("message", "").lower(), f"Unexpected response: {data}"
    print("✓ Reissue accepted. Check graeme@ryetriclub.com for the new welcome email.")
