"""
Smoke test: send a real welcome email to graeme@ryetriclub.com.

Run manually before pushing to production to verify the email template
and pass links look correct end-to-end.

    pytest tests/integration/test_smoke_email.py -v -m smoke

This test is excluded from normal CI runs.
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
