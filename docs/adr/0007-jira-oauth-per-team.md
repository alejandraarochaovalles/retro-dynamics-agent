# 0007 — Per-team Jira OAuth instead of a single global token

**Status**: Accepted and deployed.

## Context
Exporting action items to Jira relied on one **global** API token (`JIRA_API_TOKEN`), set once by whoever has access to the Vercel dashboard. That's fine for a single-team demo, but it doesn't hold up for the app's actual purpose: any team (or company) trying this out has no way to connect *their own* Jira, since they have no access to the deployment's environment variables or code.

## Options considered
- **Keep the single global token**: zero extra work, but permanently limits the app to whoever owns the deployment's Jira account — unusable as a real multi-tenant product.
- **Let each team paste their own Jira API token into a form**: removes the single-tenant limitation, but means the app has to receive and store a long-lived personal credential directly from the user — worse trust model than delegated OAuth, and still requires the user to know how to generate a Jira API token themselves.
- **Real OAuth 2.0 (3-legged) against Atlassian**: the user only ever enters their password on Atlassian's own site, never on this app; the app receives a scoped, revocable, expiring token instead of a long-lived credential.

## Decision
Implemented Atlassian's OAuth 2.0 (3LO) flow for Jira only — a "Connect with Jira" button that redirects to `auth.atlassian.com`, exchanges the returned code for tokens (`integrations/jira_oauth.py`), and stores them **encrypted at rest** (Fernet, `crypto.py`) on the team's row (`Team.integration.oauth`, a JSON column — no schema migration needed). `jira_client.create_issue` prefers a team's own OAuth token when present and falls back to the original global-token path unchanged, so the manual "Advanced / manual setup" form keeps working as a plan B and remains the only path for Azure DevOps.

Two design constraints shaped the implementation:
- **No server-side session store** — this app is serverless (ADR-0003), so nothing persists in memory between the `/connect` redirect and the `/callback` request. The OAuth `state` param is instead a self-contained, HMAC-signed, TTL-checked payload (`integrations/oauth_state.py`) carrying `team_id`/`session_id`/`project_key` — no DB table, no cache, verified purely by recomputing the signature.
- **No frontend persistence** — the React app keeps everything in memory, with no router or localStorage. A real OAuth redirect would normally wipe that state. Fixed by having the signed `state` carry the retro's `session_id` through the whole round trip; the callback echoes it back in its redirect query string, and the frontend just re-fetches `GET /api/sessions/{id}` on mount to land back on the same summary screen.

## Consequences
- **Refresh token rotation**: Atlassian issues a new `refresh_token` on every refresh, not just a new `access_token`. `jira_client._access_token_for` persists the full rotated pair every time — reusing a stale `refresh_token` after the first refresh would silently break the next one.
- **Single-site-per-team assumption**: `get_accessible_resources` can return multiple Jira sites for one Atlassian account; this app always takes `resources[0]`. Fine for the app's scope (one team, one Jira site) but a documented limitation, not solved generically.
- **No row-locking around concurrent refresh**: two near-simultaneous exports for the same team could both see an expiring token and both refresh, with the second write winning. Low risk for this app's single-admin-per-team usage; would need a DB-level lock or a dedicated token-refresh endpoint to fully close.
- **Azure DevOps intentionally out of scope**: its OAuth requires registering an app in Microsoft Entra ID, a heavier setup than Atlassian's; it keeps using the manual global-token flow unchanged.
- **One new secret ties two features together**: `TOKEN_ENCRYPTION_KEY` both encrypts stored tokens and derives the signing key for the `state` param (`hmac.new(key, b"oauth-state-v1", sha256)`) — deliberate, since OAuth is meaningless without encryption configured anyway, and it keeps `.env.example` from growing an extra secret.
- Adding the `cryptography` dependency for this work is what surfaced the `uv.lock` vs `requirements.txt` deployment bug documented in ADR-0003.
