"""
Apple Wallet (.pkpass) pass generation and signing.

Requires:
  - A Pass Type ID certificate (from Apple Developer Portal)
  - The matching private key
  - The Apple WWDR G3 intermediate certificate (download from
    https://www.apple.com/certificateauthority/AppleWWDRCAG3.cer and convert to PEM)

The resulting .pkpass file is a ZIP archive containing:
  pass.json, manifest.json, signature, icon.png, icon@2x.png, logo.png, logo@2x.png
"""

import hashlib
import io
import json
import logging
import os
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from config.settings import Settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def build_pkpass(
    name: str,
    email: str,
    member_number: str,
    expiry_date: str,
    serial_number: str,
    authentication_token: str,
) -> bytes:
    """
    Build and sign a .pkpass file.

    Args:
        name:                 Full name of the member.
        email:                Member's email address.
        member_number:        Club membership number (string).
        expiry_date:          ISO 8601 date string, e.g. "2026-12-31".
        serial_number:        Unique identifier for this pass (UUID).
        authentication_token: Secret token used to authenticate web-service calls.

    Returns:
        Raw bytes of the signed .pkpass ZIP archive.
    """
    pass_json = _build_pass_json(name, email, member_number, expiry_date, serial_number, authentication_token)
    logo_bytes = Settings.get_logo_bytes()

    # Build icon: derive a small copy of the logo (or use the same image).
    icon_bytes = _resize_image(logo_bytes, (29, 29))
    icon2x_bytes = _resize_image(logo_bytes, (58, 58))
    logo2x_bytes = _resize_image(logo_bytes, (320, 100))

    files = {
        "pass.json": pass_json.encode("utf-8"),
        "icon.png": icon_bytes,
        "icon@2x.png": icon2x_bytes,
        "logo.png": logo_bytes,
        "logo@2x.png": logo2x_bytes,
    }

    manifest = _build_manifest(files)
    manifest_bytes = json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8")

    signature = _sign_manifest(manifest_bytes)

    return _zip_pass(files, manifest_bytes, signature)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _build_pass_json(
    name: str,
    email: str,
    member_number: str,
    expiry_date: str,
    serial_number: str,
    authentication_token: str,
) -> str:
    """Build the pass.json content for a generic membership card."""

    # Apple requires full RFC 3339 for expirationDate
    try:
        exp_dt = datetime.strptime(expiry_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
    except ValueError:
        # Already includes time component
        exp_dt = datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))

    expiration_iso = exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    pass_data = {
        "formatVersion": 1,
        "passTypeIdentifier": Settings.APPLE_PASS_TYPE_IDENTIFIER,
        "serialNumber": serial_number,
        "teamIdentifier": Settings.APPLE_TEAM_IDENTIFIER,
        "webServiceURL": f"{Settings.BASE_URL}/apple",
        "authenticationToken": authentication_token,
        "organizationName": "Rye Tri Club",
        "logoText": "",
        "description": "Rye Tri Club Membership Card",
        "expirationDate": expiration_iso,
        "voided": False,
        "generic": {
            "headerFields": [
                {
                    "key": "club_name",
                    "label": "",
                    "value": "Rye Tri Club",
                    "textAlignment": "PKTextAlignmentRight",
                }
            ],
            "primaryFields": [
                {
                    "key": "member_name",
                    "label": "MEMBER",
                    "value": name,
                }
            ],
            "secondaryFields": [
                {
                    "key": "member_number",
                    "label": "MEMBER #",
                    "value": member_number,
                },
                {
                    "key": "expiry",
                    "label": "VALID THROUGH",
                    "value": expiry_date,
                    "textAlignment": "PKTextAlignmentRight",
                },
            ],
            "backFields": [
                {
                    "key": "info",
                    "label": "RYE TRI CLUB",
                    "value": (
                        "Welcome to Rye Tri Club!\n\n"
                        "This card is personal and non-transferable. "
                        "It is valid until the expiry date shown on the front.\n\n"
                        "www.ryetri.org"
                    ),
                },
                {
                    "key": "member_number_back",
                    "label": "MEMBER NUMBER",
                    "value": member_number,
                },
                {
                    "key": "email_back",
                    "label": "EMAIL",
                    "value": email,
                },
                {
                    "key": "expiry_back",
                    "label": "EXPIRY DATE",
                    "value": expiry_date,
                },
            ],
        },
        "barcode": {
            "message": f"RYETRI-{member_number}",
            "format": "PKBarcodeFormatQR",
            "messageEncoding": "iso-8859-1",
            "altText": f"Member #{member_number}",
        },
        "barcodes": [
            {
                "message": f"RYETRI-{member_number}",
                "format": "PKBarcodeFormatQR",
                "messageEncoding": "iso-8859-1",
                "altText": f"Member #{member_number}",
            }
        ],
        "backgroundColor": "rgb(255, 255, 255)",
        "foregroundColor": "rgb(10, 36, 99)",
        "labelColor": "rgb(120, 120, 120)",
    }

    return json.dumps(pass_data, indent=2)


def _build_manifest(files: dict[str, bytes]) -> dict:
    """Build manifest.json: SHA1 hashes of all files in the pass."""
    manifest = {}
    for filename, data in files.items():
        manifest[filename] = hashlib.sha1(data).hexdigest()
    return manifest


def _sign_manifest(manifest_bytes: bytes) -> bytes:
    """
    Create a detached PKCS7 signature over manifest_bytes using openssl smime.
    This produces the exact format Apple Wallet requires.
    """
    cert_pem = Settings.get_apple_cert_pem()
    key_pem = Settings.get_apple_key_pem()
    wwdr_pem = Settings.get_apple_wwdr_pem()
    password = Settings.APPLE_KEY_PASSWORD

    with tempfile.TemporaryDirectory() as tmpdir:
        cert_file = os.path.join(tmpdir, "cert.pem")
        key_file = os.path.join(tmpdir, "key.pem")
        wwdr_file = os.path.join(tmpdir, "wwdr.pem")
        manifest_file = os.path.join(tmpdir, "manifest.json")

        with open(cert_file, "wb") as f:
            f.write(cert_pem)
        with open(key_file, "wb") as f:
            f.write(key_pem)
        with open(wwdr_file, "wb") as f:
            f.write(wwdr_pem)
        with open(manifest_file, "wb") as f:
            f.write(manifest_bytes)

        cmd = [
            "openssl", "smime", "-binary", "-sign",
            "-certfile", wwdr_file,
            "-signer", cert_file,
            "-inkey", key_file,
            "-in", manifest_file,
            "-outform", "DER",
        ]
        if password:
            cmd += ["-passin", f"pass:{password}"]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
        except FileNotFoundError:
            raise RuntimeError("openssl not found — cannot sign pass")
        except subprocess.TimeoutExpired:
            raise RuntimeError("openssl signing timed out")

        if result.returncode != 0:
            raise RuntimeError(f"PKCS7 signing failed: {result.stderr.decode(errors='replace')}")

        logger.debug("PKCS7 signature generated (%d bytes)", len(result.stdout))
        return result.stdout


def _zip_pass(
    files: dict[str, bytes],
    manifest_bytes: bytes,
    signature: bytes,
) -> bytes:
    """Assemble all files into the .pkpass ZIP archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, data in files.items():
            zf.writestr(filename, data)
        zf.writestr("manifest.json", manifest_bytes)
        zf.writestr("signature", signature)
    return buffer.getvalue()


def _resize_image(image_bytes: bytes, size: tuple[int, int]) -> bytes:
    """
    Resize image to *size* using Pillow, maintaining aspect ratio with padding.
    If Pillow fails (e.g., placeholder 1×1 PNG), return original bytes.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        img.thumbnail(size, Image.LANCZOS)

        # Paste onto a transparent canvas of the exact target size
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
        canvas.paste(img, offset, img)

        out = io.BytesIO()
        canvas.save(out, format="PNG")
        return out.getvalue()
    except Exception as exc:
        logger.warning("Image resize to %s failed, using original bytes: %s", size, exc)
        return image_bytes


def void_pass_json(original_pass_json: bytes) -> bytes:
    """Return a new pass.json with voided=True, used to revoke a pass."""
    data = json.loads(original_pass_json)
    data["voided"] = True
    return json.dumps(data, indent=2).encode("utf-8")
