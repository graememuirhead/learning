# Rye Tri Club Membership Card API

An Azure Functions API that issues Apple Wallet and Google Wallet membership cards
for **Rye Tri Club** (Rye, NY). Cards are issued automatically when a member joins
or renews via Wild Apricot, and can be reissued by the member or an admin at any time.

---

## Table of Contents

- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Environments](#environments)
- [API Reference](#api-reference)
- [Wild Apricot Webhook](#wild-apricot-webhook)
- [Admin Tools](#admin-tools)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)
- [Local Development](#local-development)
- [Prerequisites](#prerequisites)

---

## Architecture

```
Wild Apricot
  └── POST /api/webhook/wild-apricot   ← new member joins / renews

Azure Functions (Python 3.11)
  ├── POST /api/create-pass            ← manual pass creation (function key required)
  ├── GET  /api/pass/{id}              ← member taps this link to add to wallet
  ├── POST /api/reissue-pass           ← self-service: member reissues their own card
  ├── POST /api/manual-send-card       ← admin: send card to any member
  ├── GET  /api/call-log               ← admin: recent API activity log
  ├── GET  /api/members                ← admin: CSV export of active members
  └── /api/apple/...                   ← Apple Wallet web-service protocol (internal)

Azure Storage Account
  ├── Blob container "passes"          ← .pkpass files
  ├── Table "PassRequests"             ← audit log of every API call
  ├── Table "IssuedPasses"             ← every card ever created
  └── Table "DeviceRegistrations"      ← Apple device ↔ pass mapping

Azure Static Website (ryetriprodst.z19.web.core.windows.net)
  ├── /index.html                      ← member self-service reissue page
  └── /admin.html                      ← admin send-card page
```

---

## How It Works

1. A member joins or renews in Wild Apricot.
2. Wild Apricot POSTs a webhook to `/api/webhook/wild-apricot`.
3. The API calls the Wild Apricot API to fetch the member's details.
4. Apple Wallet and Google Wallet passes are created and stored.
5. A welcome email is sent via SendGrid with "Add to Apple Wallet" and "Add to Google Wallet" buttons.
6. When the member taps a button, they are taken to `GET /api/pass/{id}` which either:
   - Streams the `.pkpass` file (Apple), or
   - Redirects to the Google Wallet save URL (Google).

---

## Environments

| Environment | Function App | Static Site | Branch |
|---|---|---|---|
| **Production** | `ryetri-prod-func.azurewebsites.net` | `ryetriprodst.z19.web.core.windows.net` | `master` |
| **Dev/Test** | `ryetri-dev-func.azurewebsites.net` | Separate dev static site | `develop` |

**Admin page (prod):** https://ryetriprodst.z19.web.core.windows.net/admin.html

**Member reissue page (prod):** https://membercardrenewal.ryetriclub.com
_(custom domain pointing to the static site index page)_

---

## API Reference

### POST `/api/create-pass`

Create a membership pass manually. Protected by an Azure Function key
(`?code=<key>` query parameter or `x-functions-key` header).

**Request body:**

```json
{
  "name":          "Jane Smith",
  "email":         "jane@example.com",
  "member_number": "1042",
  "expiry_date":   "2026-12-31",
  "wallet_type":   "apple"
}
```

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Member's full name |
| `email` | Yes | Member's email address |
| `member_number` | Yes | Club membership number |
| `expiry_date` | Yes | ISO 8601 date, e.g. `2026-12-31` |
| `wallet_type` | Yes | `"apple"` or `"google"` |

**Response (200 OK):**

```json
{
  "pass_id":    "550e8400-e29b-41d4-a716-446655440000",
  "pass_url":   "https://ryetri-prod-func.azurewebsites.net/api/pass/550e8400...",
  "wallet_type": "apple"
}
```

**Duplicate handling:**

- If a pass already exists for `member_number` + `wallet_type` with identical data → **409 Conflict** with the existing `pass_url`.
- If only the email changed → email is updated in-place, existing pass URL returned with a `note`.
- If the name or expiry changed → old pass is voided and a new one is issued.

---

### GET `/api/pass/{pass_id}`

The link sent to the member. No authentication required.

- **Apple:** serves the `.pkpass` binary file directly.
- **Google:** HTTP 302 redirect to the Google Wallet save URL.
- **410 Gone:** if the pass has been voided.

---

### POST `/api/reissue-pass`

Self-service endpoint. The member supplies their membership number and email.
If they match a record in the database, existing passes are voided and new ones issued,
and a welcome email is sent.

No authentication — intentionally vague error responses to prevent enumeration.

**Request body:**

```json
{
  "member_number": "1042",
  "email":         "jane@example.com"
}
```

**Response (200 OK):**

```json
{
  "message":        "Your membership card has been reissued. Check your email for the new link.",
  "apple_pass_url": "https://...",
  "google_save_url": "https://pay.google.com/...",
  "email_sent":     true
}
```

**Response (404):** `"No membership found for that number and email combination."`
_(same message whether the member number doesn't exist or the email doesn't match)_

The member-facing form at **https://membercardrenewal.ryetriclub.com** calls this endpoint.

---

### POST `/api/manual-send-card`

Admin endpoint to send (or resend) a membership card to any member.
Protected by `ADMIN_SECRET` passed in the request body.

**Request body:**

```json
{
  "admin_secret":  "...",
  "member_number": "1042",
  "email":         "jane@example.com",
  "name":          "Jane Smith",
  "expiry_date":   "2026-12-31"
}
```

| Field | Required | Description |
|---|---|---|
| `admin_secret` | Yes | Must match the `ADMIN_SECRET` environment variable |
| `member_number` | Yes | Club membership number |
| `email` | Yes | Email address to send the card to |
| `name` | Only if member not in DB | Full name |
| `expiry_date` | Only if member not in DB | ISO 8601 date |

If the member already exists in the database, `name` and `expiry_date` are taken from
the existing record. `expiry_date` can be overridden if provided.

Existing passes are voided and fresh ones issued. A welcome email is sent.

**Response (200 OK):**

```json
{
  "message": "Membership card sent to jane@example.com."
}
```

**Admin page:** https://ryetriprodst.z19.web.core.windows.net/admin.html

---

### GET `/api/call-log`

Recent API activity. Requires a function key.

**Query parameters:**

| Param | Default | Max | Description |
|---|---|---|---|
| `limit` | 50 | 200 | Number of records to return |

**Response (200 OK):** JSON array of log entries, newest first.

```json
{
  "count": 3,
  "calls": [
    {
      "endpoint":     "webhook/wild-apricot",
      "event_type":   "MembershipActivated",
      "action":       "passes_issued",
      "result":       "success",
      "member_number": "99888561",
      "email":        "member@example.com",
      "email_sent":   true,
      "timestamp":    "2026-11-14T10:23:45Z"
    }
  ]
}
```

---

### GET `/api/members`

CSV export of all active (non-voided) members. Requires a function key.

**Response (200 OK):** `text/csv`

```
name,email,member_number,expiry_date
Jane Smith,jane@example.com,1042,2026-12-31
```

---

## Wild Apricot Webhook

Configure Wild Apricot to POST to:

```
https://ryetri-prod-func.azurewebsites.net/api/webhook/wild-apricot?secret=<WILD_APRICOT_WEBHOOK_SECRET>
```

The endpoint handles two payload shapes that Wild Apricot sends:

### Shape A — real webhook (StatusChanged)

Wild Apricot sends this when a member's status changes:

```json
{
  "MessageType": "Membership",
  "AccountId":   "530477",
  "Parameters": {
    "Action":           "StatusChanged",
    "Contact.Id":       "99888561",
    "Membership.LevelId": "1828218",
    "Membership.Status": "20"
  }
}
```

The API then calls the Wild Apricot REST API to fetch the full contact record.
A pass is only issued when `Membership.Status` is `"20"` (Active) **and** the contact's
`RenewalDue` field is set in Wild Apricot. If `RenewalDue` is blank, the webhook
returns **422**.

**Membership.Status values:**

| Value | Meaning |
|---|---|
| `"20"` | Active → pass issued |
| `"1"` | Non-active → ignored |
| `"0"` | Pending → ignored |

### Shape B — smoke-test / legacy format

Used by the smoke test workflows; includes the full Contact object:

```json
{
  "EventType":  "MembershipActivated",
  "AccountId":  530477,
  "Parameters": {
    "Contact": {
      "Id":         99999,
      "FirstName":  "Test",
      "LastName":   "Member",
      "Email":      "test@example.com",
      "RenewalDue": "2026-12-31T00:00:00"
    }
  }
}
```

### Webhook responses

| Status | Meaning |
|---|---|
| 200 | Processed (or deliberately ignored — wrong action, non-Active status) |
| 401 | Bad or missing `?secret=` |
| 422 | Missing required fields (no Contact.Id, or blank RenewalDue in Wild Apricot) |
| 502 | Could not reach Wild Apricot API to fetch contact details |

### TestWebhook ping

Wild Apricot sends a test ping when the webhook is first configured:

```json
{ "MessageType": "TestWebhook", "AccountId": "530477" }
```

The API returns 200 with `{"status": "ok", "message": "Rye Tri membership API is reachable."}`.

---

## Admin Tools

### Admin page

**https://ryetriprodst.z19.web.core.windows.net/admin.html**

A simple web form that calls `POST /api/manual-send-card`. Enter:
- Member number
- Email address
- (Optionally) name and renewal date if the member is not yet in the database
- Admin secret

### Member self-service reissue

**https://membercardrenewal.ryetriclub.com**

Members use this page when they get a new phone. They enter their member number
and email; the existing pass is voided and a new welcome email is sent.

---

## Deployment

### Branching strategy

```
working branch
  → develop   (dev CI: build + unit + integration + E2E tests)
  → master    (prod CI: manual dispatch only)
```

**Never push directly to `master` without updating `develop` first** — prod CI runs
integration tests against the DEV function app as a health gate before deploying.

### Deploy to production

Prod deploy is triggered manually via GitHub Actions workflow dispatch (not on push):

1. Push changes to `develop` and wait for dev CI to pass.
2. Push to `master`.
3. Go to **Actions → Deploy Rye Tri Membership API to Azure → Run workflow**.
4. The workflow deploys to `ryetri-prod-func`, then automatically sends smoke test #1
   (a real welcome email to graeme@ryetriclub.com).
5. Confirm the email looks correct.
6. Run smoke test #2 (reissue) via **Actions → Smoke Test 2 → Run workflow**.

### Smoke tests

| Workflow | What it does |
|---|---|
| `smoke-test.yml` (runs automatically in `deploy.yml`) | Issues a TEST99999 pass and sends a welcome email to graeme@ryetriclub.com |
| `smoke-test-2.yml` (manual dispatch) | Voids and reissues the TEST99999 pass, sends a second email |

---

## Environment Variables

Set these in `local.settings.json` for local development, or as Application Settings in Azure.

### Core

| Variable | Description |
|---|---|
| `BASE_URL` | Public base URL of the Function App, e.g. `https://ryetri-prod-func.azurewebsites.net/api` |
| `STORAGE_CONNECTION_STRING` | Azure Storage connection string |
| `ENVIRONMENT` | Set to `"dev"` for the dev environment (adds "TEST ONLY" watermark to passes) |
| `STATIC_WEBSITE_URL` | Public URL of the Azure Static Website, e.g. `https://ryetriprodst.z19.web.core.windows.net` |

### Apple Wallet

| Variable | Description |
|---|---|
| `APPLE_PASS_TYPE_IDENTIFIER` | Pass Type ID, e.g. `pass.com.ryetriclub.membership` |
| `APPLE_TEAM_IDENTIFIER` | 10-character Apple Team ID |
| `APPLE_PASS_CERTIFICATE_PEM` | Base64-encoded Pass Type certificate PEM |
| `APPLE_PASS_KEY_PEM` | Base64-encoded private key PEM |
| `APPLE_WWDR_CERTIFICATE_PEM` | Base64-encoded Apple WWDR G3 intermediate certificate PEM |
| `APPLE_KEY_PASSWORD` | Private key password (if any) |

### Google Wallet

| Variable | Description |
|---|---|
| `GOOGLE_ISSUER_ID` | Google Wallet Issuer ID |
| `GOOGLE_CLASS_SUFFIX` | Suffix for the Google Wallet class ID (default: `ryetri_membership`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Base64-encoded (or raw JSON) service account key |

### Notifications

| Variable | Description |
|---|---|
| `SENDGRID_API_KEY` | SendGrid API key for sending welcome emails |
| `FROM_EMAIL` | Sender email address (default: `membership@ryetriclub.com`) |

### Wild Apricot

| Variable | Description |
|---|---|
| `WILD_APRICOT_API_KEY` | Wild Apricot server-to-server API key |
| `WILD_APRICOT_ACCOUNT_ID` | Wild Apricot account ID (default: `530477`) |
| `WILD_APRICOT_WEBHOOK_SECRET` | Secret appended to the webhook URL (`?secret=...`) |

### Admin

| Variable | Description |
|---|---|
| `ADMIN_SECRET` | Password for the admin send-card page |

### Logo

| Variable | Description |
|---|---|
| `LOGO_FILENAME` | Logo filename in `assets/` (default: `logo.png`) |
| `LOGO_PUBLIC_URL` | Optional public HTTPS URL for the logo (used by Google Wallet) |

**Encoding secrets as base64:**

```bash
base64 -i assets/apple_pass_certificate.pem  | tr -d '\n'
base64 -i assets/apple_pass_key.pem          | tr -d '\n'
base64 -i assets/AppleWWDRCAG3.pem           | tr -d '\n'
base64 -i assets/google_service_account.json | tr -d '\n'
```

---

## Local Development

```bash
# 1. Install Azure Functions Core Tools v4
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# 2. Create a Python virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Copy and fill in local settings
cp local.settings.json.template local.settings.json
# Edit local.settings.json with your values

# 4. Start the local storage emulator (Azurite)
npx azurite --silent --location /tmp/azurite &

# 5. Run the function app
func start
```

The API will be available at `http://localhost:7071/api`.

**Run tests:**

```bash
# Unit tests (no Azure or Wild Apricot credentials needed)
pytest tests/unit/

# Integration tests (requires a running function app — targets DEV by default)
pytest tests/integration/
```

---

## Prerequisites

### Apple Wallet

1. Enrol in the [Apple Developer Program](https://developer.apple.com/programs/) ($99/year).
2. Create a **Pass Type ID** in the Developer Portal (e.g. `pass.com.ryetriclub.membership`).
3. Generate and download the Pass Type ID certificate.
4. Export the certificate and private key as PEM files:

```bash
# Export from macOS Keychain as .p12, then convert:
openssl pkcs12 -in pass_certificate.p12 -clcerts -nokeys -out apple_pass_certificate.pem
openssl pkcs12 -in pass_certificate.p12 -nocerts -nodes  -out apple_pass_key.pem

# Download Apple WWDR G3 from https://www.apple.com/certificateauthority/ and convert:
openssl x509 -inform der -in AppleWWDRCAG3.cer -out AppleWWDRCAG3.pem
```

5. Place the three files in `assets/` (**do not commit them** — they are in `.gitignore`).
6. Base64-encode them and store as Azure Application Settings (see [Environment Variables](#environment-variables)).

### Google Wallet

1. Open the [Google Pay & Wallet Console](https://pay.google.com/business/console).
2. Enrol as a pass issuer and note your **Issuer ID**.
3. Enable the **Google Wallet API** in your Google Cloud project.
4. Create a service account with the **Google Wallet Object Issuer** role.
5. Download the service account key JSON and store as `GOOGLE_SERVICE_ACCOUNT_JSON`.

### Wild Apricot

1. In Wild Apricot, go to **Settings → Integrations → Webhooks**.
2. Add a webhook for **Membership** events pointing to:
   ```
   https://ryetri-prod-func.azurewebsites.net/api/webhook/wild-apricot?secret=<WILD_APRICOT_WEBHOOK_SECRET>
   ```
3. Ensure all members have a **Renewal Due** date set — the webhook will return 422
   and no pass will be issued for members with a blank renewal date.

### SendGrid

1. Create a [SendGrid](https://sendgrid.com) account.
2. Verify your sending domain (`ryetriclub.com`) via DKIM/SPF CNAME records.
3. Create an API key with **Mail Send** permission.
4. Store it as `SENDGRID_API_KEY`.

---

## Data Storage

All data is stored in Azure Table Storage.

| Table | Contents |
|---|---|
| `PassRequests` | Every call to `POST /create-pass` (audit log) |
| `IssuedPasses` | Every pass ever created, including voided ones |
| `DeviceRegistrations` | Apple device ↔ pass registrations (one-device-per-pass policy) |

Blob container `passes` stores the raw `.pkpass` files.

---

## Security Notes

- `ADMIN_SECRET` and `WILD_APRICOT_WEBHOOK_SECRET` must never be committed to source control.
- Apple pass signing certificates must never be committed to source control.
- All secrets are stored as Azure Application Settings or GitHub Actions secrets.
- `local.settings.json` is excluded from git via `.gitignore`.
- The `/api/reissue-pass` endpoint returns a deliberately vague 404 to prevent member-number enumeration.
- The Apple one-device-per-pass policy is enforced server-side: a second device attempting to register the same pass receives HTTP 403.
