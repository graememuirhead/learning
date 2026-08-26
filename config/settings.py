import os
import base64
import json
from pathlib import Path


ASSETS_DIR = Path(__file__).parent.parent / "assets"


class Settings:
    # API base URL (used in Apple pass webServiceURL)
    BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:7071/api")

    # Azure Storage
    STORAGE_CONNECTION_STRING: str = os.environ.get(
        "STORAGE_CONNECTION_STRING",
        os.environ.get("AzureWebJobsStorage", "UseDevelopmentStorage=true"),
    )
    STORAGE_CONTAINER_PASSES: str = os.environ.get("STORAGE_CONTAINER_PASSES", "passes")

    # ---- Apple Wallet ----
    APPLE_PASS_TYPE_IDENTIFIER: str = os.environ.get(
        "APPLE_PASS_TYPE_IDENTIFIER", "pass.com.ryetriclub.membership"
    )
    APPLE_TEAM_IDENTIFIER: str = os.environ.get("APPLE_TEAM_IDENTIFIER", "YNAZR962LC")
    APPLE_KEY_PASSWORD: str = os.environ.get("APPLE_KEY_PASSWORD", "")

    @staticmethod
    def get_apple_cert_pem() -> bytes:
        """Return PEM bytes for the Pass Type Certificate."""
        b64 = os.environ.get("APPLE_PASS_CERTIFICATE_PEM", "")
        if b64:
            return base64.b64decode(b64)
        # Fall back to a file next to this module
        cert_file = ASSETS_DIR / "apple_pass_certificate.pem"
        if cert_file.exists():
            return cert_file.read_bytes()
        raise RuntimeError(
            "Apple pass certificate not found. "
            "Set APPLE_PASS_CERTIFICATE_PEM env var or place apple_pass_certificate.pem in assets/."
        )

    @staticmethod
    def get_apple_key_pem() -> bytes:
        """Return PEM bytes for the Pass Type private key."""
        b64 = os.environ.get("APPLE_PASS_KEY_PEM", "")
        if b64:
            return base64.b64decode(b64)
        key_file = ASSETS_DIR / "apple_pass_key.pem"
        if key_file.exists():
            return key_file.read_bytes()
        raise RuntimeError(
            "Apple pass private key not found. "
            "Set APPLE_PASS_KEY_PEM env var or place apple_pass_key.pem in assets/."
        )

    @staticmethod
    def get_apple_wwdr_pem() -> bytes:
        """Return PEM bytes for the Apple WWDR (G3) intermediate certificate."""
        b64 = os.environ.get("APPLE_WWDR_CERTIFICATE_PEM", "")
        if b64:
            return base64.b64decode(b64)
        wwdr_file = ASSETS_DIR / "AppleWWDRCAG4.pem"
        if wwdr_file.exists():
            return wwdr_file.read_bytes()
        raise RuntimeError(
            "Apple WWDR certificate not found. "
            "Set APPLE_WWDR_CERTIFICATE_PEM env var or place AppleWWDRCAG3.pem in assets/."
        )

    # ---- Google Wallet ----
    GOOGLE_ISSUER_ID: str = os.environ.get("GOOGLE_ISSUER_ID", "")
    GOOGLE_CLASS_SUFFIX: str = os.environ.get("GOOGLE_CLASS_SUFFIX", "ryetri_membership")

    @staticmethod
    def get_google_service_account() -> dict:
        """Return parsed Google service account JSON."""
        b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if b64:
            return json.loads(base64.b64decode(b64))
        sa_file = ASSETS_DIR / "google_service_account.json"
        if sa_file.exists():
            return json.loads(sa_file.read_text())
        raise RuntimeError(
            "Google service account not found. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON env var or place google_service_account.json in assets/."
        )

    # ---- Logo ----
    LOGO_FILENAME: str = os.environ.get("LOGO_FILENAME", "logo.png")

    @staticmethod
    def get_logo_path() -> Path:
        """Return path to the logo file stored in assets/."""
        return ASSETS_DIR / Settings.LOGO_FILENAME

    @staticmethod
    def get_logo_bytes() -> bytes:
        logo = Settings.get_logo_path()
        if logo.exists():
            return logo.read_bytes()
        # Return a tiny 1×1 transparent PNG as a placeholder
        import base64
        placeholder = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        return base64.b64decode(placeholder)
