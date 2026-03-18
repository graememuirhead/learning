"""
Rye Tri Club Membership Card API
Azure Functions v2 (Python)

Endpoints
---------
POST   /api/create-pass
    Create an Apple or Google Wallet membership pass.
    Body: { "name", "member_number", "expiry_date", "wallet_type" }
    Returns: { "pass_url", "pass_id", "wallet_type" }

GET    /api/pass/{pass_id}
    Download the .pkpass file (Apple) or redirect to the Google Wallet save URL.

---- Apple Wallet Web Service (required for auto-expiry push updates) ----

POST   /api/apple/devices/{device_id}/registrations/{pass_type_id}/{serial}
    Register a device for pass update notifications.

DELETE /api/apple/devices/{device_id}/registrations/{pass_type_id}/{serial}
    Unregister a device.

GET    /api/apple/passes/{pass_type_id}/{serial}
    Return the latest version of a pass (used by Wallet after a push notification).

POST   /api/apple/log
    Receive error logs from Apple Wallet (optional, for debugging).
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import azure.functions as func

from config.settings import Settings
from passes.apple_pass import build_pkpass
from passes.google_pass import build_save_url
from storage import database as db

logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


# =========================================================================== #
# POST /api/create-pass
# =========================================================================== #

@app.route(route="create-pass", methods=["POST"])
def create_pass(req: func.HttpRequest) -> func.HttpResponse:
    """
    Create a new membership pass and return the download/save URL.

    Request body (JSON):
        name          (str, required)  – member's full name
        member_number (str, required)  – club membership number
        expiry_date   (str, required)  – ISO 8601 date, e.g. "2026-12-31"
        wallet_type   (str, required)  – "apple" or "google"

    Response (JSON):
        pass_id       – unique identifier for this pass
        pass_url      – URL to send to the member
        wallet_type   – echoed back
    """
    request_id = str(uuid.uuid4())

    try:
        body = req.get_json()
    except ValueError:
        return _bad_request("Request body must be valid JSON.")

    name = _str(body, "name")
    member_number = _str(body, "member_number")
    expiry_date = _str(body, "expiry_date")
    wallet_type = _str(body, "wallet_type", "").lower()

    # Validation
    if not all([name, member_number, expiry_date]):
        return _bad_request("Fields 'name', 'member_number', and 'expiry_date' are required.")

    if wallet_type not in ("apple", "google"):
        return _bad_request("'wallet_type' must be 'apple' or 'google'.")

    if not _valid_date(expiry_date):
        return _bad_request("'expiry_date' must be in YYYY-MM-DD format.")

    # Log the incoming request (audit trail)
    client_ip = req.headers.get("X-Forwarded-For") or req.headers.get("X-Real-IP")
    db.log_pass_request(request_id, name, member_number, expiry_date, wallet_type, client_ip)

    # Check whether a valid pass already exists for this member / wallet type
    existing = db.get_pass_by_member_number(member_number, wallet_type)
    if existing:
        db.update_request_status(request_id, "existing", existing["RowKey"])
        return _ok(
            {
                "pass_id": existing["RowKey"],
                "pass_url": existing["PassUrl"],
                "wallet_type": wallet_type,
                "note": "An active pass already exists for this member; returning existing URL.",
            }
        )

    serial_number = str(uuid.uuid4())
    authentication_token = secrets.token_urlsafe(32)

    try:
        if wallet_type == "apple":
            result = _issue_apple_pass(
                request_id, serial_number, authentication_token,
                name, member_number, expiry_date
            )
        else:
            result = _issue_google_pass(
                request_id, serial_number,
                name, member_number, expiry_date
            )
    except Exception as exc:
        logger.exception("Failed to create pass for request %s", request_id)
        db.update_request_status(request_id, "error")
        return _internal_error(str(exc))

    db.update_request_status(request_id, "issued", serial_number)
    return _ok(result)


def _issue_apple_pass(
    request_id: str,
    serial_number: str,
    authentication_token: str,
    name: str,
    member_number: str,
    expiry_date: str,
) -> dict:
    pkpass_bytes = build_pkpass(
        name=name,
        member_number=member_number,
        expiry_date=expiry_date,
        serial_number=serial_number,
        authentication_token=authentication_token,
    )
    db.store_pkpass(serial_number, pkpass_bytes)

    pass_url = f"{Settings.BASE_URL}/pass/{serial_number}"
    db.save_issued_pass(
        serial_number=serial_number,
        request_id=request_id,
        name=name,
        member_number=member_number,
        expiry_date=expiry_date,
        wallet_type="apple",
        pass_url=pass_url,
        authentication_token=authentication_token,
    )
    return {"pass_id": serial_number, "pass_url": pass_url, "wallet_type": "apple"}


def _issue_google_pass(
    request_id: str,
    serial_number: str,
    name: str,
    member_number: str,
    expiry_date: str,
) -> dict:
    save_url = build_save_url(
        name=name,
        member_number=member_number,
        expiry_date=expiry_date,
        serial_number=serial_number,
    )
    db.save_issued_pass(
        serial_number=serial_number,
        request_id=request_id,
        name=name,
        member_number=member_number,
        expiry_date=expiry_date,
        wallet_type="google",
        pass_url=save_url,
    )
    return {"pass_id": serial_number, "pass_url": save_url, "wallet_type": "google"}


# =========================================================================== #
# GET /api/pass/{pass_id}
# =========================================================================== #

@app.route(route="pass/{pass_id}", methods=["GET"])
def get_pass(req: func.HttpRequest, pass_id: str = None) -> func.HttpResponse:
    """
    For Apple passes: stream the .pkpass binary so the user can tap "Add to Wallet".
    For Google passes: redirect to the Google Wallet save URL.
    """
    if pass_id is None:
        pass_id = req.route_params.get("pass_id", "")

    pass_record = db.get_issued_pass(pass_id)
    if not pass_record:
        return func.HttpResponse("Pass not found.", status_code=404)

    if pass_record.get("Voided"):
        return func.HttpResponse(
            "This pass has been revoked. Please contact Rye Tri Club for a replacement.",
            status_code=410,
        )

    wallet_type = pass_record.get("WalletType", "").lower()

    if wallet_type == "apple":
        pkpass_bytes = db.get_pkpass(pass_id)
        if not pkpass_bytes:
            return func.HttpResponse("Pass file not found.", status_code=404)
        return func.HttpResponse(
            pkpass_bytes,
            status_code=200,
            mimetype="application/vnd.apple.pkpass",
            headers={
                "Content-Disposition": f'attachment; filename="{pass_id}.pkpass"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )

    if wallet_type == "google":
        return func.HttpResponse(
            status_code=302,
            headers={"Location": pass_record["PassUrl"]},
        )

    return func.HttpResponse("Unknown wallet type.", status_code=400)


# =========================================================================== #
# Apple Wallet Web Service  – device registration
# =========================================================================== #

@app.route(
    route="apple/devices/{device_id}/registrations/{pass_type_id}/{serial}",
    methods=["POST"],
)
def apple_register_device(
    req: func.HttpRequest,
    device_id: str = None,
    pass_type_id: str = None,
    serial: str = None,
) -> func.HttpResponse:
    """
    Apple calls this when a user adds the pass to Wallet.
    Enforces the one-wallet restriction.
    """
    if device_id is None:
        device_id = req.route_params.get("device_id", "")
    if serial is None:
        serial = req.route_params.get("serial", "")

    # Authenticate using the Authorization header: "ApplePass <token>"
    if not _verify_apple_auth(req, serial):
        return func.HttpResponse(status_code=401)

    try:
        body = req.get_json()
        push_token = body.get("pushToken", "")
    except (ValueError, AttributeError):
        push_token = ""

    registered = db.register_apple_device(device_id, push_token, serial)
    if not registered:
        # Pass already registered to another device
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "This pass is already registered to another device. "
                    "Please contact Rye Tri Club to transfer it."
                }
            ),
            status_code=403,
            mimetype="application/json",
        )

    return func.HttpResponse(status_code=201)


@app.route(
    route="apple/devices/{device_id}/registrations/{pass_type_id}/{serial}",
    methods=["DELETE"],
)
def apple_unregister_device(
    req: func.HttpRequest,
    device_id: str = None,
    pass_type_id: str = None,
    serial: str = None,
) -> func.HttpResponse:
    """Apple calls this when a user removes the pass from Wallet."""
    if device_id is None:
        device_id = req.route_params.get("device_id", "")
    if serial is None:
        serial = req.route_params.get("serial", "")

    if not _verify_apple_auth(req, serial):
        return func.HttpResponse(status_code=401)

    db.unregister_apple_device(device_id, serial)
    return func.HttpResponse(status_code=200)


# =========================================================================== #
# Apple Wallet Web Service  – latest pass version
# =========================================================================== #

@app.route(
    route="apple/passes/{pass_type_id}/{serial}",
    methods=["GET"],
)
def apple_get_latest_pass(
    req: func.HttpRequest,
    pass_type_id: str = None,
    serial: str = None,
) -> func.HttpResponse:
    """
    Apple calls this when it needs the latest version of a pass
    (e.g. after receiving a push notification, or on periodic refresh).
    """
    if serial is None:
        serial = req.route_params.get("serial", "")

    if not _verify_apple_auth(req, serial):
        return func.HttpResponse(status_code=401)

    pkpass_bytes = db.get_pkpass(serial)
    if not pkpass_bytes:
        return func.HttpResponse(status_code=404)

    pass_record = db.get_issued_pass(serial)
    if pass_record and pass_record.get("Voided"):
        return func.HttpResponse(status_code=410)

    last_modified = pass_record.get("IssuedAt", "") if pass_record else ""
    return func.HttpResponse(
        pkpass_bytes,
        status_code=200,
        mimetype="application/vnd.apple.pkpass",
        headers={"Last-Modified": last_modified},
    )


# =========================================================================== #
# Apple Wallet Web Service  – error log
# =========================================================================== #

@app.route(route="apple/log", methods=["POST"])
def apple_log(req: func.HttpRequest) -> func.HttpResponse:
    """Receive and log error messages from Apple Wallet."""
    try:
        body = req.get_json()
        logger.warning("Apple Wallet log: %s", json.dumps(body))
    except Exception:
        pass
    return func.HttpResponse(status_code=200)


# =========================================================================== #
# Helpers
# =========================================================================== #

def _verify_apple_auth(req: func.HttpRequest, serial: str) -> bool:
    """
    Validate the Authorization header sent by Apple Wallet.
    Format: "ApplePass <authenticationToken>"
    """
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("ApplePass "):
        return False
    token = auth[len("ApplePass "):]
    pass_record = db.get_issued_pass(serial)
    if not pass_record:
        return False
    return secrets.compare_digest(token, pass_record.get("AuthenticationToken", ""))


def _str(body: dict, key: str, default: str = "") -> str:
    return str(body.get(key, default)).strip()


def _valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _ok(data: dict) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(data),
        status_code=200,
        mimetype="application/json",
    )


def _bad_request(message: str) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": message}),
        status_code=400,
        mimetype="application/json",
    )


def _internal_error(message: str) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": "Internal server error.", "detail": message}),
        status_code=500,
        mimetype="application/json",
    )
