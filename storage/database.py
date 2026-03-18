"""
Azure Table Storage layer for the Rye Tri membership API.

Tables
------
PassRequests   – one row per POST /create-pass API call received.
IssuedPasses   – one row per pass successfully created and stored.
DeviceReg      – Apple Wallet device registrations (for web-service protocol).

Blob container "passes"
-----------------------
  {serial_number}.pkpass   – raw .pkpass archive (Apple)
  {serial_number}.meta.json – lightweight JSON with pass metadata
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableServiceClient, TableClient
from azure.storage.blob import BlobServiceClient

from config.settings import Settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Table names
# --------------------------------------------------------------------------- #
TABLE_REQUESTS = "PassRequests"
TABLE_PASSES = "IssuedPasses"
TABLE_DEVICE_REG = "DeviceRegistrations"

# Use a single partition key for simplicity (low-volume use-case).
# For higher volumes, partition by member number or date prefix.
PARTITION_KEY = "RyeTri"


# --------------------------------------------------------------------------- #
# Client helpers
# --------------------------------------------------------------------------- #

def _table_client(table_name: str) -> TableClient:
    svc = TableServiceClient.from_connection_string(Settings.STORAGE_CONNECTION_STRING)
    try:
        svc.create_table(table_name)
    except ResourceExistsError:
        pass
    return svc.get_table_client(table_name)


def _blob_client():
    svc = BlobServiceClient.from_connection_string(Settings.STORAGE_CONNECTION_STRING)
    try:
        svc.create_container(Settings.STORAGE_CONTAINER_PASSES)
    except ResourceExistsError:
        pass
    return svc


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Pass Requests  (audit log of every API call)
# --------------------------------------------------------------------------- #

def log_pass_request(
    request_id: str,
    name: str,
    member_number: str,
    expiry_date: str,
    wallet_type: str,
    client_ip: Optional[str],
) -> None:
    """Record every incoming /create-pass request."""
    entity = {
        "PartitionKey": PARTITION_KEY,
        "RowKey": request_id,
        "Name": name,
        "MemberNumber": member_number,
        "ExpiryDate": expiry_date,
        "WalletType": wallet_type,
        "ClientIP": client_ip or "",
        "RequestedAt": _now_iso(),
        "Status": "pending",
    }
    _table_client(TABLE_REQUESTS).upsert_entity(entity)


def update_request_status(request_id: str, status: str, pass_id: Optional[str] = None) -> None:
    """Update the status of a logged request (e.g. 'issued', 'error')."""
    client = _table_client(TABLE_REQUESTS)
    try:
        entity = client.get_entity(PARTITION_KEY, request_id)
        entity["Status"] = status
        if pass_id:
            entity["PassId"] = pass_id
        entity["UpdatedAt"] = _now_iso()
        client.update_entity(entity)
    except ResourceNotFoundError:
        logger.warning("Request %s not found when updating status.", request_id)


# --------------------------------------------------------------------------- #
# Issued Passes
# --------------------------------------------------------------------------- #

def save_issued_pass(
    serial_number: str,
    request_id: str,
    name: str,
    member_number: str,
    expiry_date: str,
    wallet_type: str,
    pass_url: str,
    authentication_token: Optional[str] = None,
) -> None:
    """Record a successfully issued pass."""
    entity = {
        "PartitionKey": PARTITION_KEY,
        "RowKey": serial_number,
        "RequestId": request_id,
        "Name": name,
        "MemberNumber": member_number,
        "ExpiryDate": expiry_date,
        "WalletType": wallet_type,
        "PassUrl": pass_url,
        "AuthenticationToken": authentication_token or "",
        "IssuedAt": _now_iso(),
        "Voided": False,
        "DeviceCount": 0,
    }
    _table_client(TABLE_PASSES).upsert_entity(entity)


def get_issued_pass(serial_number: str) -> Optional[dict]:
    """Fetch a pass record by its serial number."""
    try:
        return dict(_table_client(TABLE_PASSES).get_entity(PARTITION_KEY, serial_number))
    except ResourceNotFoundError:
        return None


def get_pass_by_member_number(member_number: str, wallet_type: str) -> Optional[dict]:
    """
    Look up an existing, non-voided pass for a given member number and wallet type.
    Returns the most recently issued one if multiple exist (shouldn't happen normally).
    """
    client = _table_client(TABLE_PASSES)
    filter_expr = (
        f"PartitionKey eq '{PARTITION_KEY}' "
        f"and MemberNumber eq '{member_number}' "
        f"and WalletType eq '{wallet_type}' "
        f"and Voided eq false"
    )
    entities = list(client.query_entities(filter_expr))
    if not entities:
        return None
    # Sort by IssuedAt descending, return the latest
    entities.sort(key=lambda e: e.get("IssuedAt", ""), reverse=True)
    return dict(entities[0])


def void_issued_pass(serial_number: str) -> bool:
    """Mark a pass as voided (e.g. added to a second device)."""
    client = _table_client(TABLE_PASSES)
    try:
        entity = client.get_entity(PARTITION_KEY, serial_number)
        entity["Voided"] = True
        entity["VoidedAt"] = _now_iso()
        client.update_entity(entity)
        return True
    except ResourceNotFoundError:
        return False


def increment_device_count(serial_number: str) -> int:
    """Increment the registered-device count and return the new value."""
    client = _table_client(TABLE_PASSES)
    try:
        entity = client.get_entity(PARTITION_KEY, serial_number)
        count = int(entity.get("DeviceCount", 0)) + 1
        entity["DeviceCount"] = count
        client.update_entity(entity)
        return count
    except ResourceNotFoundError:
        return 0


def decrement_device_count(serial_number: str) -> int:
    """Decrement the registered-device count and return the new value."""
    client = _table_client(TABLE_PASSES)
    try:
        entity = client.get_entity(PARTITION_KEY, serial_number)
        count = max(0, int(entity.get("DeviceCount", 0)) - 1)
        entity["DeviceCount"] = count
        client.update_entity(entity)
        return count
    except ResourceNotFoundError:
        return 0


# --------------------------------------------------------------------------- #
# Apple Device Registrations
# --------------------------------------------------------------------------- #

def register_apple_device(
    device_library_id: str,
    push_token: str,
    serial_number: str,
) -> bool:
    """
    Register an Apple device for a pass.

    Returns False if the pass is already registered to a *different* device
    (enforces one-wallet policy).
    """
    pass_record = get_issued_pass(serial_number)
    if not pass_record:
        return False

    # Check existing registrations for this serial number
    existing = _get_device_registration(serial_number)
    if existing:
        if existing["DeviceLibraryIdentifier"] == device_library_id:
            # Same device re-registering – update push token
            existing["PushToken"] = push_token
            existing["UpdatedAt"] = _now_iso()
            _table_client(TABLE_DEVICE_REG).update_entity(existing)
            return True
        else:
            # Different device – enforce one-wallet policy
            logger.warning(
                "Pass %s already registered to device %s; rejecting device %s.",
                serial_number,
                existing["DeviceLibraryIdentifier"],
                device_library_id,
            )
            return False

    # First registration
    entity = {
        "PartitionKey": serial_number,
        "RowKey": device_library_id,
        "DeviceLibraryIdentifier": device_library_id,
        "SerialNumber": serial_number,
        "PushToken": push_token,
        "RegisteredAt": _now_iso(),
        "UpdatedAt": _now_iso(),
    }
    _table_client(TABLE_DEVICE_REG).upsert_entity(entity)
    increment_device_count(serial_number)
    return True


def unregister_apple_device(device_library_id: str, serial_number: str) -> bool:
    """Remove a device registration, freeing the pass for another device."""
    client = _table_client(TABLE_DEVICE_REG)
    try:
        client.delete_entity(serial_number, device_library_id)
        decrement_device_count(serial_number)
        return True
    except ResourceNotFoundError:
        return False


def _get_device_registration(serial_number: str) -> Optional[dict]:
    """Return the first (and should be only) registration for a serial number."""
    client = _table_client(TABLE_DEVICE_REG)
    entities = list(client.query_entities(f"PartitionKey eq '{serial_number}'"))
    return dict(entities[0]) if entities else None


def get_device_registrations(serial_number: str) -> list[dict]:
    """Return all device registrations for a given serial number."""
    client = _table_client(TABLE_DEVICE_REG)
    return [dict(e) for e in client.query_entities(f"PartitionKey eq '{serial_number}'")]


# --------------------------------------------------------------------------- #
# Blob Storage – .pkpass files
# --------------------------------------------------------------------------- #

def store_pkpass(serial_number: str, pkpass_bytes: bytes) -> None:
    """Store a .pkpass file in Azure Blob Storage."""
    blob = _blob_client().get_blob_client(
        container=Settings.STORAGE_CONTAINER_PASSES,
        blob=f"{serial_number}.pkpass",
    )
    blob.upload_blob(pkpass_bytes, overwrite=True)


def get_pkpass(serial_number: str) -> Optional[bytes]:
    """Retrieve a .pkpass file from Blob Storage."""
    blob = _blob_client().get_blob_client(
        container=Settings.STORAGE_CONTAINER_PASSES,
        blob=f"{serial_number}.pkpass",
    )
    try:
        return blob.download_blob().readall()
    except ResourceNotFoundError:
        return None
