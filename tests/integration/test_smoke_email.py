"""
Smoke tests: send real emails to graeme@ryetriclub.com.

Smoke test #1 — new passes via MembershipActivated webhook:
    pytest tests/integration/test_smoke_email.py::test_smoke_welcome_email -v -m smoke -s

Smoke test #2 — reissue (void + recreate) via self-service endpoint:
    pytest tests/integration/test_smoke_email.py::test_smoke_reissue_pass -v -m smoke -s

Run test #1 first; test #2 operates on the same member.
These tests are excluded from normal CI runs.
"""
from datetime import date

import pytest
import requests


def _smoke_member_id() -> int:
    # Date-based ID: one smoke member per calendar day.
    # Test 1 may reuse existing passes; test 2 always voids and recreates.
    return int(f"9{date.today().strftime('%Y%m%d')}")


@pytest.mark.smoke
def test_smoke_welcome_email(func_url, webhook_secret):
    """
    Trigger a MembershipActivated webhook for today's smoke member.
    Fresh passes are created each hour, so this always produces a new pass.
    Check graeme@ryetriclub.com for the welcome email with Apple + Google buttons.
    """
    if not webhook_secret:
        pytest.skip("DEV_WEBHOOK_SECRET not set")

    member_id = _smoke_member_id()
    print(f"\n  Smoke member ID: {member_id}")

    payload = {
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

    Run test_smoke_welcome_email first (within the same hour) to create the initial passes.
    """
    member_number = str(_smoke_member_id())
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
