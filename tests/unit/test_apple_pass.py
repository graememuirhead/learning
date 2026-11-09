"""Unit tests for Apple Wallet pass JSON generation."""
import json
import os
import re

import pytest

os.environ.setdefault("APPLE_PASS_TYPE_IDENTIFIER", "pass.com.test.membership")
os.environ.setdefault("APPLE_TEAM_IDENTIFIER", "TESTTEAM12")

from passes.apple_pass import _build_pass_json  # noqa: E402


MEMBER = dict(
    name="Test Member",
    email="test@ryetriclub.com",
    member_number="TEST99999",
    expiry_date="2099-12-31",
    serial_number="unit-test-serial-001",
    authentication_token="unit-test-auth-token",
)


def _pass(**overrides) -> dict:
    return json.loads(_build_pass_json(**{**MEMBER, **overrides}))


def test_apple_pass_required_fields():
    p = _pass()
    for field in ("passTypeIdentifier", "serialNumber", "teamIdentifier",
                  "expirationDate", "generic", "organizationName"):
        assert field in p


def test_apple_pass_expiry_format():
    p = _pass()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", p["expirationDate"])


def test_apple_pass_dev_logo_text(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings.Settings, "IS_DEV", True)
    assert _pass()["logoText"] == "TEST ONLY"


def test_apple_pass_prod_logo_text(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings.Settings, "IS_DEV", False)
    assert _pass()["logoText"] == ""


def test_apple_pass_qr_message():
    p = _pass()
    assert p["barcode"]["message"] == f"RYETRI-{MEMBER['member_number']}"
    assert p["barcodes"][0]["message"] == f"RYETRI-{MEMBER['member_number']}"


def test_apple_pass_member_name_in_primary_fields():
    p = _pass()
    assert any(f["value"] == MEMBER["name"] for f in p["generic"]["primaryFields"])


def test_apple_pass_member_number_in_secondary_fields():
    p = _pass()
    assert any(f["value"] == MEMBER["member_number"] for f in p["generic"]["secondaryFields"])
