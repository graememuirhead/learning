# Rye Tri Membership API — Claude Code Guidelines

## Branch workflow

Always follow this order. Never skip a step.

1. **Develop on the working branch** (`claude/rye-tri-membership-api-TzGR0` or the current session branch).
2. **Push to `develop` first** — this triggers the dev CI, which deploys to the DEV function app and runs the full integration test suite against it.
3. **Only push to `master` after dev CI passes** — the production CI runs integration tests against DEV as a health gate before deploying to prod. If DEV is behind, that gate fails.

```
working branch → develop → (dev CI passes) → master → (prod CI passes) → deployed to prod
```

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
