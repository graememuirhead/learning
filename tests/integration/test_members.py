"""Integration tests for GET /api/members CSV export."""
import csv
import io

import pytest
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


def test_members_csv_count_matches_database(func_url, auth_headers, storage_connection_string):
    """
    Count distinct active members directly in Table Storage, then verify the
    API returns exactly that many rows.  Catches off-by-one errors, pagination
    bugs, and incorrect Voided filtering without relying on a fixed known total.
    """
    if not storage_connection_string:
        pytest.skip("DEV_STORAGE_CONNECTION_STRING not set")

    from azure.data.tables import TableServiceClient

    # Count distinct non-voided members directly in Table Storage
    svc = TableServiceClient.from_connection_string(storage_connection_string)
    client = svc.get_table_client("IssuedPasses")
    entities = client.query_entities(
        "PartitionKey eq 'RyeTri' and Voided eq false",
        select=["MemberNumber"],
    )
    db_member_numbers = {e["MemberNumber"] for e in entities}
    db_count = len(db_member_numbers)

    # Fetch the API response and count rows
    resp = requests.get(f"{func_url}/members", headers=auth_headers, timeout=15)
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.text))
    api_member_numbers = {row["member_number"] for row in reader}
    api_count = len(api_member_numbers)

    assert api_count == db_count, (
        f"API returned {api_count} members but Table Storage has {db_count} active. "
        f"Missing from API: {db_member_numbers - api_member_numbers}. "
        f"Extra in API: {api_member_numbers - db_member_numbers}."
    )
