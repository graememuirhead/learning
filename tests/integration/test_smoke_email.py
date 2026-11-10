"""
Smoke test: send a real welcome email to graeme@ryetriclub.com.

Run manually before pushing to production to verify the email template
and pass links look correct end-to-end.

    pytest tests/integration/test_smoke_email.py -v -m smoke

This test is excluded from normal CI runs.
"""
import pytest
import requests


SMOKE_PAYLOAD = {
    "EventType": "MembershipActivated",
    "AccountId": 123456,
    "Parameters": {
        "Contact": {
            "FirstName": "Graeme",
            "LastName": "Muirhead",
            "Email": "graeme@ryetriclub.com",
            "Id": 99997,
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

    resp = requests.post(
        f"{func_url}/webhook/wild-apricot",
        params={"secret": webhook_secret},
        json=SMOKE_PAYLOAD,
        timeout=60,
    )
    assert resp.status_code == 200, f"Webhook returned {resp.status_code}: {resp.text[:300]}"
    print("\n✓ Webhook accepted. Check graeme@ryetriclub.com for the welcome email.")
