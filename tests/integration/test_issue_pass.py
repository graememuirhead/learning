"""Integration tests for POST /api/create-pass."""
import zipfile
import io

import requests

from tests.integration.conftest import TEST_MEMBER


def test_issue_pass_requires_auth(func_url):
    resp = requests.post(
        f"{func_url}/create-pass",
        json={**TEST_MEMBER, "wallet_type": "apple"},
        timeout=30,
    )
    assert resp.status_code == 401


def test_issue_pass_missing_name(func_url, auth_headers):
    body = {k: v for k, v in TEST_MEMBER.items() if k != "name"}
    body["wallet_type"] = "apple"
    resp = requests.post(f"{func_url}/create-pass", json=body, headers=auth_headers, timeout=30)
    assert resp.status_code == 400


def test_issue_pass_missing_email(func_url, auth_headers):
    body = {k: v for k, v in TEST_MEMBER.items() if k != "email"}
    body["wallet_type"] = "apple"
    resp = requests.post(f"{func_url}/create-pass", json=body, headers=auth_headers, timeout=30)
    assert resp.status_code == 400


def test_issue_pass_invalid_wallet_type(func_url, auth_headers):
    resp = requests.post(
        f"{func_url}/create-pass",
        json={**TEST_MEMBER, "wallet_type": "samsung"},
        headers=auth_headers,
        timeout=30,
    )
    assert resp.status_code == 400


def test_issue_apple_pass_returns_pass_url(func_url, auth_headers):
    """Apple pass for TEST99999 may already exist (409) or be newly created (200) — both give a pass_url."""
    resp = requests.post(
        f"{func_url}/create-pass",
        json={**TEST_MEMBER, "wallet_type": "apple"},
        headers=auth_headers,
        timeout=30,
    )
    assert resp.status_code in (200, 409)
    data = resp.json()
    assert "pass_url" in data
    assert "/api/pass/" in data["pass_url"]


def test_apple_pass_url_serves_pkpass(func_url, auth_headers):
    """Follow the pass_url and verify the response is a valid ZIP (.pkpass)."""
    resp = requests.post(
        f"{func_url}/create-pass",
        json={**TEST_MEMBER, "wallet_type": "apple"},
        headers=auth_headers,
        timeout=30,
    )
    assert resp.status_code in (200, 409)
    pass_url = resp.json()["pass_url"]

    pkpass_resp = requests.get(pass_url, timeout=15)
    assert pkpass_resp.status_code == 200
    assert pkpass_resp.headers.get("Content-Type") == "application/vnd.apple.pkpass"
    assert zipfile.is_zipfile(io.BytesIO(pkpass_resp.content))


def test_issue_google_pass_returns_save_url(func_url, auth_headers):
    resp = requests.post(
        f"{func_url}/create-pass",
        json={
            "name": "Google Test Member",
            "email": "gtest@ryetriclub.com",
            "member_number": "TEST99998",
            "expiry_date": "2099-12-31",
            "wallet_type": "google",
        },
        headers=auth_headers,
        timeout=30,
    )
    assert resp.status_code in (200, 409)
    data = resp.json()
    assert "pass_url" in data
    assert data["pass_url"].startswith("https://pay.google.com/gp/v/save/")
