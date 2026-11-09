"""Unit tests for Google Wallet pass object structure."""
import os

import pytest

os.environ.setdefault("GOOGLE_ISSUER_ID", "1234567890")
os.environ.setdefault("GOOGLE_CLASS_SUFFIX", "ryetri_membership_test")

from passes.google_pass import _build_generic_object  # noqa: E402


MEMBER = dict(
    object_id="1234567890.unit-test-serial",
    class_id="1234567890.ryetri_membership_test",
    name="Test Member",
    email="test@ryetriclub.com",
    member_number="TEST99999",
    expiry_date="2099-12-31",
)


def _obj(**overrides) -> dict:
    return _build_generic_object(**{**MEMBER, **overrides})


def test_google_pass_required_fields():
    obj = _obj()
    for field in ("id", "classId", "cardTitle", "header", "subheader", "textModulesData"):
        assert field in obj


def test_google_pass_dev_subheader(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings.Settings, "IS_DEV", True)
    assert _obj()["subheader"]["defaultValue"]["value"] == "TEST ONLY"


def test_google_pass_prod_subheader(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings.Settings, "IS_DEV", False)
    assert _obj()["subheader"]["defaultValue"]["value"] == "Membership Card"


def test_google_pass_member_name_in_header():
    assert _obj()["header"]["defaultValue"]["value"] == MEMBER["name"]


def test_google_pass_member_number_in_text_modules():
    modules = {m["id"]: m["body"] for m in _obj().get("textModulesData", [])}
    assert modules.get("member_number") == MEMBER["member_number"]


def test_google_pass_expiry_in_text_modules():
    modules = {m["id"]: m["body"] for m in _obj().get("textModulesData", [])}
    assert modules.get("expiry") == MEMBER["expiry_date"]
