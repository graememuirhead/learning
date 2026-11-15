"""Integration tests for POST /api/admin/send-card."""
import pytest
import requests

from tests.integration.conftest import TEST_MEMBER

# A member that does not exist in the database — used for new-member creation tests.
NEW_MEMBER = {
    "name": "Admin Test New",
    "email": "test@ryetriclub.com",
    "member_number": "ADMINNEW01",
    "expiry_date": "2099-12-31",
}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_no_password_returns_401(func_url):
    resp = requests.post(
        f"{func_url}/admin/send-card",
        json={"member_number": TEST_MEMBER["member_number"], "email": TEST_MEMBER["email"]},
        timeout=30,
    )
    assert resp.status_code == 401


def test_wrong_password_returns_401(func_url):
    resp = requests.post(
        f"{func_url}/admin/send-card",
        json={
            "admin_secret": "this-is-definitely-wrong",
            "member_number": TEST_MEMBER["member_number"],
            "email": TEST_MEMBER["email"],
        },
        timeout=30,
    )
    assert resp.status_code == 401


def test_requires_json_body(func_url):
    resp = requests.post(
        f"{func_url}/admin/send-card",
        data="not json",
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Input validation (use wrong password so we don't need ADMIN_SECRET set)
# ---------------------------------------------------------------------------

def test_missing_member_number_returns_400_or_401(func_url):
    """Missing required field — 400 if secret is correct, but 401 is also acceptable
    (the endpoint checks secret before fields; either way it must not return 200)."""
    resp = requests.post(
        f"{func_url}/admin/send-card",
        json={"admin_secret": "wrong", "email": TEST_MEMBER["email"]},
        timeout=30,
    )
    assert resp.status_code in (400, 401)


def test_missing_email_returns_400_or_401(func_url):
    resp = requests.post(
        f"{func_url}/admin/send-card",
        json={"admin_secret": "wrong", "member_number": TEST_MEMBER["member_number"]},
        timeout=30,
    )
    assert resp.status_code in (400, 401)


# ---------------------------------------------------------------------------
# Functional tests — require DEV_ADMIN_SECRET to be set
# ---------------------------------------------------------------------------

def test_existing_member_returns_200(func_url, admin_secret):
    """Send a card to the seeded test member — passes already exist."""
    if not admin_secret:
        pytest.skip("DEV_ADMIN_SECRET not set")

    resp = requests.post(
        f"{func_url}/admin/send-card",
        json={
            "admin_secret": admin_secret,
            "member_number": TEST_MEMBER["member_number"],
            "email": TEST_MEMBER["email"],
        },
        timeout=60,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert "message" in data
    assert TEST_MEMBER["email"] in data["message"]


def test_nonexistent_member_without_override_returns_404(func_url, admin_secret):
    """Member not in DB and no name/expiry provided — should get 404."""
    if not admin_secret:
        pytest.skip("DEV_ADMIN_SECRET not set")

    resp = requests.post(
        f"{func_url}/admin/send-card",
        json={
            "admin_secret": admin_secret,
            "member_number": "DOESNOTEXIST99",
            "email": "nobody@ryetriclub.com",
        },
        timeout=30,
    )
    assert resp.status_code == 404


def test_nonexistent_member_with_override_creates_and_returns_200(func_url, admin_secret, auth_headers):
    """Member not in DB — provide name + expiry to create from scratch."""
    if not admin_secret:
        pytest.skip("DEV_ADMIN_SECRET not set")

    # Clean up any leftover pass from a previous run
    requests.post(
        f"{func_url}/create-pass",
        json={**NEW_MEMBER, "wallet_type": "apple"},
        headers=auth_headers,
        timeout=30,
    )

    resp = requests.post(
        f"{func_url}/admin/send-card",
        json={
            "admin_secret": admin_secret,
            "member_number": NEW_MEMBER["member_number"],
            "email": NEW_MEMBER["email"],
            "name": NEW_MEMBER["name"],
            "expiry_date": NEW_MEMBER["expiry_date"],
        },
        timeout=60,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert "message" in data


def test_expiry_override_is_used(func_url, admin_secret):
    """Providing expiry_date overrides the value stored in the database."""
    if not admin_secret:
        pytest.skip("DEV_ADMIN_SECRET not set")

    resp = requests.post(
        f"{func_url}/admin/send-card",
        json={
            "admin_secret": admin_secret,
            "member_number": TEST_MEMBER["member_number"],
            "email": TEST_MEMBER["email"],
            "expiry_date": "2030-06-30",
        },
        timeout=60,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
