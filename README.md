# Rye Tri Club Membership Card API

An Azure Functions API that issues Apple Wallet and Google Wallet membership cards
for **Rye Tri Club** (Rye, NY).

---

## Features

| Feature | Details |
|---|---|
| **Apple Wallet** | Signed `.pkpass` file served over HTTPS; member taps link → "Add to Wallet" |
| **Google Wallet** | JWT-signed Generic pass; member taps link → "Save to Google Wallet" |
| **Auto-expiry** | Pass expires automatically on the configured expiry date (both platforms) |
| **One-wallet policy** | An Apple pass can only be registered to one device at a time |
| **Audit trail** | Every API request and every issued pass is recorded in Azure Table Storage |
| **Logo** | Drop a `logo.png` into `assets/` – no code change needed |

---

## Architecture

```
Azure Functions (Python 3.11)
  ├── POST /api/create-pass      ← your backend calls this
  ├── GET  /api/pass/{id}        ← link sent to member
  └── /api/apple/...             ← Apple Wallet web-service protocol

Azure Storage Account
  ├── Blob container "passes"    ← .pkpass files
  ├── Table "PassRequests"       ← audit log of every API call
  ├── Table "IssuedPasses"       ← every card ever created
  └── Table "DeviceRegistrations"← Apple device ↔ pass mapping

Azure Key Vault (optional)       ← store certificates securely
```

---

## Prerequisites

### Apple Wallet

1. Enrol in the [Apple Developer Program](https://developer.apple.com/programs/) ($99/year).
2. Create a **Pass Type ID** in the Developer Portal (e.g. `pass.com.ryetriclub.membership`).
3. Generate a Pass Type ID certificate and download it.
4. Export the certificate + private key as PEM files:

```bash
# Export from macOS Keychain as .p12, then convert:
openssl pkcs12 -in pass_certificate.p12 -clcerts -nokeys -out apple_pass_certificate.pem
openssl pkcs12 -in pass_certificate.p12 -nocerts -nodes  -out apple_pass_key.pem

# Download the Apple WWDR G3 intermediate cert and convert to PEM:
# From https://www.apple.com/certificateauthority/ (Apple Worldwide Developer Relations CA - G3)
openssl x509 -inform der -in AppleWWDRCAG3.cer -out AppleWWDRCAG3.pem
```

5. Place the three PEM files in `assets/`:
   - `assets/apple_pass_certificate.pem`
   - `assets/apple_pass_key.pem`
   - `assets/AppleWWDRCAG3.pem`

   **Do not commit these files.** They are in `.gitignore`.
   Store them as base64-encoded environment variables in Azure (see below).

### Google Wallet

1. Open the [Google Pay & Wallet Console](https://pay.google.com/business/console).
2. Enrol as a pass issuer and note your **Issuer ID**.
3. Enable the **Google Wallet API** in your Google Cloud project.
4. Create a **Service Account** with the role **Google Wallet Object Issuer**.
5. Download the service account key JSON file.
6. Place it at `assets/google_service_account.json` (also in `.gitignore`).

---

## Logo

Place your club logo at `assets/logo.png` (PNG, ideally 320×100 px or wider).
The filename is configurable via the `LOGO_FILENAME` environment variable.

The logo is:
- Embedded in both the Apple and Google pass
- Automatically resized for Apple icon images

---

## Local Development

```bash
# 1. Install Azure Functions Core Tools v4
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# 2. Create a Python virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Copy and fill in local.settings.json
cp local.settings.json.template local.settings.json
# Edit local.settings.json with your values

# 4. Start the local emulator (Azurite) for storage
npx azurite --silent --location /tmp/azurite &

# 5. Run the function app locally
func start
```

The API will be available at `http://localhost:7071/api`.

---

## Environment Variables

Set these in `local.settings.json` for local dev, or as Application Settings in Azure.

| Variable | Description |
|---|---|
| `BASE_URL` | Public base URL of your Function App, e.g. `https://ryetri-prod-func.azurewebsites.net/api` |
| `STORAGE_CONNECTION_STRING` | Azure Storage connection string |
| `APPLE_PASS_TYPE_IDENTIFIER` | Your Pass Type ID, e.g. `pass.com.ryetriclub.membership` |
| `APPLE_TEAM_IDENTIFIER` | Your 10-character Apple Team ID |
| `APPLE_PASS_CERTIFICATE_PEM` | Base64-encoded pass certificate PEM |
| `APPLE_PASS_KEY_PEM` | Base64-encoded private key PEM |
| `APPLE_WWDR_CERTIFICATE_PEM` | Base64-encoded Apple WWDR G3 PEM |
| `APPLE_KEY_PASSWORD` | Password for the private key (if any) |
| `GOOGLE_ISSUER_ID` | Google Wallet Issuer ID |
| `GOOGLE_CLASS_SUFFIX` | Suffix for the Google Wallet class ID (default: `ryetri_membership`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Base64-encoded service account JSON |
| `LOGO_FILENAME` | Filename of the logo in `assets/` (default: `logo.png`) |
| `LOGO_PUBLIC_URL` | (Optional) Public HTTPS URL for the logo image, used by Google Wallet |

**Encoding secrets as base64:**

```bash
base64 -i assets/apple_pass_certificate.pem | tr -d '\n'
base64 -i assets/apple_pass_key.pem         | tr -d '\n'
base64 -i assets/AppleWWDRCAG3.pem          | tr -d '\n'
base64 -i assets/google_service_account.json | tr -d '\n'
```

---

## Deploy to Azure

### One-time setup

```bash
# Create a resource group
az group create --name rye-tri-rg --location eastus

# Create a service principal for GitHub Actions
az ad sp create-for-rbac \
  --name "rye-tri-github-actions" \
  --role contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/rye-tri-rg \
  --json-auth
```

Copy the JSON output and add it as a GitHub secret named `AZURE_CREDENTIALS`.

### Deploy via GitHub Actions

Push to `master` – the workflow in `.github/workflows/deploy.yml` will:
1. Deploy the Bicep infrastructure (storage, function app, key vault).
2. Build and publish the Python function app.

### Set secrets after deploy

```bash
az functionapp config appsettings set \
  --name ryetri-prod-func \
  --resource-group rye-tri-rg \
  --settings \
    APPLE_TEAM_IDENTIFIER="ABCD123456" \
    APPLE_PASS_CERTIFICATE_PEM="$(base64 -i assets/apple_pass_certificate.pem | tr -d '\n')" \
    APPLE_PASS_KEY_PEM="$(base64 -i assets/apple_pass_key.pem | tr -d '\n')" \
    APPLE_WWDR_CERTIFICATE_PEM="$(base64 -i assets/AppleWWDRCAG3.pem | tr -d '\n')" \
    GOOGLE_ISSUER_ID="<your-issuer-id>" \
    GOOGLE_SERVICE_ACCOUNT_JSON="$(base64 -i assets/google_service_account.json | tr -d '\n')"
```

---

## API Reference

### POST `/api/create-pass`

Create a membership pass. Protected by the Azure Function default key
(`?code=<key>` query parameter or `x-functions-key` header).

**Request body:**

```json
{
  "name":          "Jane Smith",
  "member_number": "1042",
  "expiry_date":   "2026-12-31",
  "wallet_type":   "apple"
}
```

`wallet_type` must be `"apple"` or `"google"`.

**Response (200 OK):**

```json
{
  "pass_id":    "550e8400-e29b-41d4-a716-446655440000",
  "pass_url":   "https://ryetri-prod-func.azurewebsites.net/api/pass/550e8400...",
  "wallet_type": "apple"
}
```

Send `pass_url` to the member via email or SMS. Tapping the link on their phone
opens the "Add to Wallet" / "Save to Google Wallet" prompt.

If a non-voided pass already exists for the same `member_number` + `wallet_type`,
the existing URL is returned with a `note` field.

---

### GET `/api/pass/{pass_id}`

- **Apple:** streams the `.pkpass` binary file.
- **Google:** HTTP 302 redirect to the Google Wallet save URL.
- **410 Gone:** if the pass has been revoked.

---

## One-Wallet Policy

**Apple Wallet:**

When a member adds the pass on their phone, Apple calls the registration endpoint.
The API records which device holds the pass. If a second device tries to register
the same pass, the API returns HTTP 403 and the pass is not added.

When a member removes the pass from their wallet, Apple calls the unregister endpoint,
freeing the pass for another device (e.g. after a phone upgrade — the member simply
deletes the pass on their old phone, then taps the link again on their new phone).

**Google Wallet:**

Google does not expose a device-registration webhook for Generic passes.
The API returns the same save URL for repeat requests for the same member/wallet
combination, so the member can only ever save one instance.

---

## Data Storage

All data is stored in Azure Table Storage.

| Table | Contents |
|---|---|
| `PassRequests` | Every call to `POST /create-pass` (audit log) |
| `IssuedPasses` | Every pass successfully created |
| `DeviceRegistrations` | Apple device ↔ pass registrations |

Blob container `passes` stores the raw `.pkpass` files.

---

## Updating the Logo

1. Replace `assets/logo.png` with your new logo (PNG format recommended).
2. Redeploy the function app.
3. Newly issued passes will use the new logo.

---

## Security Notes

- The API uses Azure Function **function-level** auth keys. Keep the key secret.
- Apple pass signing certificates must **never** be committed to source control.
- Store all secrets as environment variables or in Azure Key Vault.
- The `local.settings.json` file is excluded from git via `.gitignore`.
