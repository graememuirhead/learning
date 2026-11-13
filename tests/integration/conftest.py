"""Shared fixtures for integration tests against the dev Function App."""
import os

import pytest
import requests

# Constants for the test member used across all integration tests
TEST_MEMBER = {
    "name": "CI Test Member",
    "email": "test@ryetriclub.com",
    "member_number": "TEST99999",
    "expiry_date": "2099-12-31",
}


@pytest.fixture(scope="session")
def func_url() -> str:
    url = os.environ.get("DEV_FUNCTION_URL", "").rstrip("/")
    if not url:
        pytest.skip("DEV_FUNCTION_URL not set — skipping integration tests")
    return url


@pytest.fixture(scope="session")
def func_key() -> str:
    key = os.environ.get("DEV_FUNCTION_KEY", "")
    if not key:
        pytest.skip("DEV_FUNCTION_KEY not set — skipping integration tests")
    return key


@pytest.fixture(scope="session")
def webhook_secret() -> str:
    return os.environ.get("DEV_WEBHOOK_SECRET", "").strip()


@pytest.fixture(scope="session")
def storage_connection_string() -> str:
    return os.environ.get("DEV_STORAGE_CONNECTION_STRING", "")


@pytest.fixture(scope="session")
def auth_headers(func_key) -> dict:
    return {"x-functions-key": func_key, "Content-Type": "application/json"}


@pytest.fixture(scope="session", autouse=True)
def seed_test_member(func_url, auth_headers):
    """Ensure TEST99999 has an active apple pass before integration tests run."""
    import time

    # Retry up to 180 s to handle the case where dev is mid-deployment.
    deadline = time.time() + 180
    delay = 5
    while True:
        resp = requests.post(
            f"{func_url}/create-pass",
            json={**TEST_MEMBER, "wallet_type": "apple"},
            headers=auth_headers,
            timeout=30,
        )
        # 200 = created, 409 = already exists — both are fine
        if resp.status_code in (200, 409):
            return
        if time.time() >= deadline:
            assert False, f"Could not seed test member: {resp.status_code} {resp.text[:300]}"
        time.sleep(delay)
