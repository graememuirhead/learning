"""
Google Wallet pass generation.

Produces a signed JWT that the user opens at:
  https://pay.google.com/gp/v/save/{jwt}

Pass type used: GenericClass / GenericObject (Google Wallet Generic pass).

Requires:
  - A Google Cloud project with the Google Wallet API enabled.
  - A service account with the "Google Wallet Object Issuer" role.
  - An Issuer ID obtained from the Google Pay & Wallet Console
    (https://pay.google.com/business/console).
"""

import json
import time
from datetime import datetime, timezone

import google.auth.crypt
import google.auth.jwt

from config.settings import Settings


GOOGLE_WALLET_SAVE_URL = "https://pay.google.com/gp/v/save"
GOOGLE_WALLET_API_BASE = "https://walletobjects.googleapis.com/walletobjects/v1"
SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def build_save_url(
    name: str,
    member_number: str,
    expiry_date: str,
    serial_number: str,
    class_already_exists: bool = False,
) -> str:
    """
    Build a Google Wallet save URL for a membership card.

    Args:
        name:                Full name of the member.
        member_number:       Club membership number.
        expiry_date:         ISO 8601 date, e.g. "2026-12-31".
        serial_number:       Unique pass identifier (UUID).
        class_already_exists: If True, skip class creation in the JWT payload.

    Returns:
        A URL the user can open to add the pass to Google Wallet.
    """
    issuer_id = Settings.GOOGLE_ISSUER_ID
    class_suffix = Settings.GOOGLE_CLASS_SUFFIX
    class_id = f"{issuer_id}.{class_suffix}"
    object_id = f"{issuer_id}.{serial_number}"

    payload = {
        "iss": _get_service_account_email(),
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "genericObjects": [
                _build_generic_object(
                    object_id, class_id, name, member_number, expiry_date
                )
            ],
        },
        "origins": [],
    }

    # Include the class definition only on first issue (or always for simplicity)
    if not class_already_exists:
        payload["payload"]["genericClasses"] = [_build_generic_class(class_id)]

    signer = _get_signer()
    token = google.auth.jwt.encode(signer, payload).decode("utf-8")
    return f"{GOOGLE_WALLET_SAVE_URL}/{token}"


def void_google_pass(serial_number: str) -> bool:
    """
    Mark a Google Wallet pass object as expired/voided via the REST API.
    Returns True on success, False if the API call fails.
    """
    import requests

    object_id = f"{Settings.GOOGLE_ISSUER_ID}.{serial_number}"
    url = f"{GOOGLE_WALLET_API_BASE}/genericObject/{object_id}"

    patch_body = {"state": "EXPIRED"}
    try:
        resp = requests.patch(url, json=patch_body, headers=_auth_headers())
        return resp.status_code in (200, 204)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Pass structure builders
# --------------------------------------------------------------------------- #

def _build_generic_class(class_id: str) -> dict:
    """Build the GenericClass definition (template shared by all member passes)."""
    return {
        "id": class_id,
        "classTemplateInfo": {
            "cardTemplateOverride": {
                "cardRowTemplateInfos": [
                    {
                        "twoItems": {
                            "startItem": {
                                "firstValue": {
                                    "fields": [
                                        {
                                            "fieldPath": "object.textModulesData['member_number']"
                                        }
                                    ]
                                }
                            },
                            "endItem": {
                                "firstValue": {
                                    "fields": [
                                        {
                                            "fieldPath": "object.textModulesData['expiry']"
                                        }
                                    ]
                                }
                            },
                        }
                    }
                ]
            }
        },
        "imageModulesData": [
            {
                "mainImage": {
                    "sourceUri": {
                        "uri": _logo_data_uri()
                    },
                    "contentDescription": {
                        "defaultValue": {
                            "language": "en-US",
                            "value": "Rye Tri Club Logo",
                        }
                    },
                },
                "id": "club_logo",
            }
        ],
    }


def _build_generic_object(
    object_id: str,
    class_id: str,
    name: str,
    member_number: str,
    expiry_date: str,
) -> dict:
    """Build a GenericObject for a single membership card."""

    # Google Wallet uses RFC 3339 for dates
    try:
        exp_dt = datetime.strptime(expiry_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
    except ValueError:
        exp_dt = datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
    expiration_iso = exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "id": object_id,
        "classId": class_id,
        "genericType": "GENERIC_TYPE_UNSPECIFIED",
        "hexBackgroundColor": "#0a2463",
        "logo": {
            "sourceUri": {
                "uri": _logo_data_uri()
            },
            "contentDescription": {
                "defaultValue": {
                    "language": "en-US",
                    "value": "Rye Tri Club Logo",
                }
            },
        },
        "cardTitle": {
            "defaultValue": {
                "language": "en-US",
                "value": "Rye Tri Club",
            }
        },
        "subheader": {
            "defaultValue": {
                "language": "en-US",
                "value": "Membership Card",
            }
        },
        "header": {
            "defaultValue": {
                "language": "en-US",
                "value": name,
            }
        },
        "textModulesData": [
            {
                "id": "member_number",
                "header": "MEMBER #",
                "body": member_number,
            },
            {
                "id": "expiry",
                "header": "VALID THROUGH",
                "body": expiry_date,
            },
            {
                "id": "location",
                "header": "CLUB LOCATION",
                "body": "Rye, NY",
            },
        ],
        "barcode": {
            "type": "QR_CODE",
            "value": f"RYETRI-{member_number}",
            "alternateText": f"Member #{member_number}",
        },
        "state": "ACTIVE",
        "validTimeInterval": {
            "end": {
                "date": expiration_iso,
            }
        },
        "groupingInfo": {
            "groupingId": "rye-tri-membership",
            "sortIndex": 1,
        },
        "notifications": {
            "expiryNotification": {
                "enableNotification": True,
            }
        },
    }


# --------------------------------------------------------------------------- #
# Auth / signing helpers
# --------------------------------------------------------------------------- #

def _get_service_account() -> dict:
    return Settings.get_google_service_account()


def _get_service_account_email() -> str:
    return _get_service_account()["client_email"]


def _get_signer() -> google.auth.crypt.RSASigner:
    sa = _get_service_account()
    return google.auth.crypt.RSASigner.from_service_account_info(sa)


def _auth_headers() -> dict:
    """
    Return Authorization headers for direct REST API calls (e.g. voiding passes).
    """
    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.load_credentials_from_dict(
        _get_service_account(), scopes=SCOPES
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {credentials.token}"}


def _logo_data_uri() -> str:
    """
    Return the logo as a data URI so it can be embedded in the JWT payload.
    Falls back to an empty string if the logo is unavailable.

    NOTE: Google Wallet also accepts a public HTTPS URL. If you host the logo
    publicly, set LOGO_PUBLIC_URL in env and return that instead.
    """
    import base64
    import os

    public_url = os.environ.get("LOGO_PUBLIC_URL", "")
    if public_url:
        return public_url

    logo_bytes = Settings.get_logo_bytes()
    b64 = base64.b64encode(logo_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"
