"""Integration tests for GET /api/members CSV export."""
import csv
import io

import requests


def test_members_csv_requires_auth(func_url):
    resp = requests.get(f"{func_url}/members", timeout=15)
    assert resp.status_code == 401


def test_members_csv_returns_csv(func_url, auth_headers):
    resp = requests.get(f"{func_url}/members", headers=auth_headers, timeout=15)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("Content-Type", "")


def test_members_csv_has_expected_columns(func_url, auth_headers):
    resp = requests.get(f"{func_url}/members", headers=auth_headers, timeout=15)
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.text))
    assert reader.fieldnames == ["name", "email", "member_number", "expiry_date"]


def test_members_csv_contains_test_member(func_url, auth_headers):
    resp = requests.get(f"{func_url}/members", headers=auth_headers, timeout=15)
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.text))
    numbers = [row["member_number"] for row in reader]
    assert "TEST99999" in numbers
