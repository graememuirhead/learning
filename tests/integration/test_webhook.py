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


# ---- Shape A: real Wild Apricot webhook (MessageType=Membership, flat Contact.Id) ----
# Shape A is what Wild Apricot sends in production; it contains only a Contact.Id
# and requires a callback to the Wild Apricot API to fetch full contact details.


def test_shape_a_missing_contact_id_rejected(func_url, webhook_secret):
    """Shape A RenewalDateChanged with no Contact.Id should be rejected with 422."""
    if not webhook_secret:
        import pytest
        pytest.skip("DEV_WEBHOOK_SECRET not set")
    resp = requests.post(
        f"{func_url}/webhook/wild-apricot",
        params={"secret": webhook_secret},
        json={
            "MessageType": "Membership",
            "AccountId": "530477",
            "Parameters": {
                "Action": "RenewalDateChanged",
                "Membership.Status": "20",
                # Contact.Id intentionally absent
            },
        },
        timeout=30,
    )
    assert resp.status_code == 422


def test_shape_a_non_renewal_date_action_ignored(func_url, webhook_secret):
    """Shape A with Action != RenewalDateChanged should be silently ignored (200)."""
    if not webhook_secret:
        import pytest
        pytest.skip("DEV_WEBHOOK_SECRET not set")
    for action in ("StatusChanged", "Added", "LevelChanged"):
        resp = requests.post(
            f"{func_url}/webhook/wild-apricot",
            params={"secret": webhook_secret},
            json={
                "MessageType": "Membership",
                "AccountId": "530477",
                "Parameters": {
                    "Action": action,
                    "Contact.Id": "99999999",
                    "Membership.Status": "20",
                },
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200 for Action={action}, got {resp.status_code}"


def test_shape_a_calls_wild_apricot_api(func_url, webhook_secret):
    """
    Shape A RenewalDateChanged with an unknown contact ID exercises the full WA API call path.
    Wild Apricot returns 404 for the bogus ID, which the function maps to 502.
    A 502 (not 422/400) confirms wa_get_contact() was called rather than bypassed.
    """
    if not webhook_secret:
        import pytest
        pytest.skip("DEV_WEBHOOK_SECRET not set")
    resp = requests.post(
        f"{func_url}/webhook/wild-apricot",
        params={"secret": webhook_secret},
        json={
            "MessageType": "Membership",
            "AccountId": "530477",
            "Parameters": {
                "Action": "RenewalDateChanged",
                "Contact.Id": "9999999",  # valid format, non-existent contact
                "Membership.Status": "20",
            },
        },
        timeout=30,
    )
    assert resp.status_code == 502, (
        f"Expected 502 (WA API called, contact not found) but got {resp.status_code}: {resp.text[:300]}"
    )
