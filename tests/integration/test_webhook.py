"""Integration tests for POST /api/webhook/wild-apricot."""
import requests


VALID_PAYLOAD = {
    "EventType": "MembershipActivated",
    "AccountId": 123456,
    "Parameters": {
        "Contact": {
            "FirstName": "Webhook",
            "LastName": "Test",
            "Email": "webhooktest@ryetriclub.com",
            "Id": 88888,
            "RenewalDue": "2099-12-31T00:00:00",
        }
    },
}


def test_webhook_missing_secret(func_url):
    resp = requests.post(
        f"{func_url}/webhook/wild-apricot",
        json=VALID_PAYLOAD,
        timeout=30,
    )
    assert resp.status_code == 401


def test_webhook_wrong_secret(func_url):
    resp = requests.post(
        f"{func_url}/webhook/wild-apricot?secret=WRONG",
        json=VALID_PAYLOAD,
        timeout=30,
    )
    assert resp.status_code == 401


def test_webhook_membership_activated(func_url, webhook_secret):
    if not webhook_secret:
        import pytest
        pytest.skip("DEV_WEBHOOK_SECRET not set")
    resp = requests.post(
        f"{func_url}/webhook/wild-apricot",
        params={"secret": webhook_secret},
        json=VALID_PAYLOAD,
        timeout=60,
    )
    assert resp.status_code == 200


def test_webhook_membership_renewed(func_url, webhook_secret):
    if not webhook_secret:
        import pytest
        pytest.skip("DEV_WEBHOOK_SECRET not set")
    payload = {**VALID_PAYLOAD, "EventType": "MembershipRenewed"}
    resp = requests.post(
        f"{func_url}/webhook/wild-apricot",
        params={"secret": webhook_secret},
        json=payload,
        timeout=60,
    )
    assert resp.status_code == 200


def test_webhook_unknown_event_type_is_ignored(func_url, webhook_secret):
    if not webhook_secret:
        import pytest
        pytest.skip("DEV_WEBHOOK_SECRET not set")
    payload = {**VALID_PAYLOAD, "EventType": "SomeOtherEvent"}
    resp = requests.post(
        f"{func_url}/webhook/wild-apricot",
        params={"secret": webhook_secret},
        json=payload,
        timeout=30,
    )
    assert resp.status_code == 200
