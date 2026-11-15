"""
Wild Apricot API client.

Uses the API key (client_credentials OAuth2) to fetch contact details
when the webhook only provides a contact ID.

Docs: https://app.wildapricot.org/api/v2.2
Auth: https://gethelp.wildapricot.com/en/articles/180
"""

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from config.settings import Settings

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://oauth.wildapricot.org/auth/token"
_API_BASE = "https://api.wildapricot.org/v2.2"

# Simple in-memory token cache (Azure Functions instances are short-lived)
_cached_token: dict = {}


def get_contact(account_id: str, contact_id: str) -> dict:
    """
    Fetch a contact from the Wild Apricot API and return a normalised dict:
        first_name, last_name, name, email, renewal_due, status
    """
    token = _get_token()
    url = f"{_API_BASE}/accounts/{account_id}/contacts/{contact_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(
            f"Wild Apricot API returned {e.code} for contact {contact_id}: {body[:500]}"
        )

    first_name = (data.get("FirstName") or "").strip()
    last_name = (data.get("LastName") or "").strip()
    name = f"{first_name} {last_name}".strip()
    email = (data.get("Email") or "").strip().lower()

    # RenewalDue is an ISO datetime string — take just the date part
    renewal_due = (data.get("RenewalDue") or "")
    expiry_date = renewal_due[:10] if renewal_due else ""

    # Status.Value is a string like "Active", "Lapsed", "Suspended"
    status_obj = data.get("Status") or {}
    status = (status_obj.get("Value") or str(status_obj)).strip() if isinstance(status_obj, dict) else str(status_obj).strip()

    logger.info(
        "wild-apricot contact=%s name=%r email=%r status=%s renewal=%s",
        contact_id, name, email, status, expiry_date,
    )
    return {
        "first_name": first_name,
        "last_name": last_name,
        "name": name,
        "email": email,
        "expiry_date": expiry_date,
        "status": status,
        "raw": data,
    }


def _get_token() -> str:
    """Return a cached or fresh OAuth2 access token."""
    import time

    # Return cached token if still valid (with 60s buffer)
    if _cached_token.get("expires_at", 0) > time.time() + 60:
        return _cached_token["access_token"]

    api_key = Settings.WILD_APRICOT_API_KEY
    if not api_key:
        raise RuntimeError("WILD_APRICOT_API_KEY is not configured")

    # Wild Apricot uses the API key as both username and password
    credentials = base64.b64encode(f"APIKEY:{api_key}".encode()).decode()
    payload = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "auto"}).encode()

    req = urllib.request.Request(
        _TOKEN_URL,
        data=payload,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Wild Apricot token request failed {e.code}: {body[:500]}")

    access_token = token_data["access_token"]
    expires_in = int(token_data.get("expires_in", 3600))

    _cached_token["access_token"] = access_token
    _cached_token["expires_at"] = time.time() + expires_in

    logger.info("Wild Apricot token obtained, expires_in=%ds", expires_in)
    return access_token
