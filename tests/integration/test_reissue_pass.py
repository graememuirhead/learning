"""Integration tests for POST /api/reissue-pass (anonymous endpoint)."""
import requests

from tests.integration.conftest import TEST_MEMBER


def test_reissue_no_auth_required(func_url):
    """The endpoint is anonymous — no function key needed."""
    resp = requests.post(
        f"{func_url}/reissue-pass",
        json={"member_number": "DOESNOTEXIST", "email": "nobody@example.com"},
        timeout=30,
    )
    # Should get 404, not 401
    assert resp.status_code == 404


def test_reissue_missing_member_number(func_url):
    resp = requests.post(
        f"{func_url}/reissue-pass",
        json={"email": TEST_MEMBER["email"]},
        timeout=30,
    )
    assert resp.status_code == 400


def test_reissue_missing_email(func_url):
    resp = requests.post(
        f"{func_url}/reissue-pass",
        json={"member_number": TEST_MEMBER["member_number"]},
        timeout=30,
    )
    assert resp.status_code == 400


def test_reissue_wrong_email_returns_404(func_url):
    resp = requests.post(
        f"{func_url}/reissue-pass",
        json={"member_number": TEST_MEMBER["member_number"], "email": "wrong@example.com"},
        timeout=30,
    )
    assert resp.status_code == 404


def test_reissue_nonexistent_member_returns_404(func_url):
    resp = requests.post(
        f"{func_url}/reissue-pass",
        json={"member_number": "NOSUCHEMEMBER", "email": TEST_MEMBER["email"]},
        timeout=30,
    )
    assert resp.status_code == 404


def test_reissue_valid_combination_returns_200(func_url):
    resp = requests.post(
        f"{func_url}/reissue-pass",
        json={
            "member_number": TEST_MEMBER["member_number"],
            "email": TEST_MEMBER["email"],
        },
        timeout=60,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
