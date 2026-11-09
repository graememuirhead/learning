"""Integration tests for POST /api/create-pass."""
import base64
import hashlib
import io
import json
import zipfile

import requests

from tests.integration.conftest import TEST_MEMBER


def _decode_jwt_payload(token: str) -> dict:
    """Base64-decode the JWT payload segment without verifying the signature."""
    payload_b64 = token.split(".")[1]
    # Add padding if needed
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


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


def test_apple_pass_manifest_hashes_are_valid(func_url, auth_headers):
    """
    Download the .pkpass, open it as a ZIP, read manifest.json, and verify
    that the SHA1 hash of every listed file matches what Apple Wallet expects.
    A hash mismatch means the pass will be rejected by Wallet even if it looks fine.
    """
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

    zf = zipfile.ZipFile(io.BytesIO(pkpass_resp.content))
    names = zf.namelist()

    # Required files must all be present
    for required in ("pass.json", "manifest.json", "signature"):
        assert required in names, f"Missing required file in .pkpass: {required}"

    manifest = json.loads(zf.read("manifest.json"))
    assert manifest, "manifest.json is empty"

    # Every file listed in the manifest must have a matching SHA1
    for filename, expected_sha1 in manifest.items():
        actual_sha1 = hashlib.sha1(zf.read(filename)).hexdigest()
        assert actual_sha1 == expected_sha1, (
            f"SHA1 mismatch for {filename}: "
            f"manifest says {expected_sha1}, file is {actual_sha1}"
        )


def test_google_pass_jwt_payload_is_valid(func_url, auth_headers):
    """
    Decode the JWT inside the Google Wallet save URL (without verifying the
    signature — that requires Google's public key) and check the payload has
    the correct structure, issuer, and member data.
    A malformed payload means Google Wallet will show an error page.
    """
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
    pass_url = resp.json()["pass_url"]

    # URL is https://pay.google.com/gp/v/save/<jwt>
    jwt_token = pass_url.split("/")[-1]
    payload = _decode_jwt_payload(jwt_token)

    assert payload.get("aud") == "google"
    assert payload.get("typ") == "savetowallet"
    assert "iss" in payload, "JWT missing 'iss' (service account email)"

    objects = payload.get("payload", {}).get("genericObjects", [])
    assert objects, "No genericObjects in JWT payload"

    obj = objects[0]
    assert "id" in obj
    assert "classId" in obj
    assert obj["header"]["defaultValue"]["value"] == "Google Test Member"
    assert any(
        m["id"] == "member_number" and m["body"] == "TEST99998"
        for m in obj.get("textModulesData", [])
    ), "Member number not found in textModulesData"
