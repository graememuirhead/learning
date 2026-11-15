# Rye Tri Membership API — Claude Code Guidelines

## Deployment process

Always follow these steps in order. Never skip one.

```
working branch
  → develop   (dev CI: build + unit tests + integration tests + E2E tests)
  → master    (prod CI: build + integration tests against DEV + deploy + smoke test #1)
  → user confirms smoke test #1 email looks correct
  → run smoke test #2 (reissue) on request
  → production confirmed ✓
```

### Step by step

1. **Make changes on the working branch** (`claude/rye-tri-membership-api-TzGR0` or the current session branch).
2. **Push to `develop`** — triggers dev CI: deploys to DEV, runs unit + integration + E2E tests.
3. **Wait for dev CI to pass.**
4. **Push to `master`** — triggers prod CI: runs integration tests against DEV as a health gate, then deploys to prod, then runs **smoke test #1** automatically (sends a real welcome email to graeme@ryetriclub.com).
5. **User checks their email** — confirms the Apple + Google Wallet pass links arrived correctly.
6. **Run smoke test #2** when asked — voids and reissues the smoke passes, sends a second email. Triggered via the `smoke-test.yml` workflow dispatch.
7. **Production confirmed.**

Pushing directly to `master` without updating `develop` first will cause the prod CI to fail because DEV will be running stale code.

## Environments

| Branch    | Function App          | Purpose                        |
|-----------|-----------------------|--------------------------------|
| `develop` | `ryetri-dev-func`     | Integration tests, smoke tests |
| `master`  | `ryetri-prod-func`    | Live production                |

## Key secrets (GitHub)

- `ADMIN_SECRET` — password for the admin send-card page
- `WILD_APRICOT_API_KEY` — Wild Apricot server-to-server API key
- `WILD_APRICOT_ACCOUNT_ID` — `530477`
- `WILD_APRICOT_WEBHOOK_SECRET` — secret appended to the WA webhook URL
