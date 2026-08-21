# Chunk 4 Validation Record

## Automated gate

- Original Chunk 2.1 tests: 7/7 pass.
- Chunk 3 regression tests: 5/5 pass.
- Chunk 4 tests: 10/10 pass.
- Total: 22/22 pass.
- Python compilation: pass.
- `static/embed.js` JavaScript syntax check: pass.
- Existing `static/store.js` JavaScript syntax check: pass.

## What the automated tests prove

- The embed script is independently served from `/embed.js`.
- A separate-origin test website contains only the installation script and no business knowledge/provider secret.
- Widget history is stored in that website's `localStorage`.
- Only the latest 8 previous messages are sent to inference.
- Allowed origins receive CORS permission and can call `/embed-api/chat`.
- Missing/disallowed origins are rejected.
- CORS preflight is denied for an unapproved origin.
- Static/manual demo business knowledge stays on the backend.
- Minimum in-memory rate limiting returns HTTP 429 after the configured threshold.
- Public embed mode disables `/api/chat`, preventing the old client-supplied business-knowledge endpoint from being exposed as the public inference path.
- The provider-neutral `AIService` boundary remains intact.
- Render deployment configuration keeps Gemini key and allowed origins out of source values.

## Manual acceptance gate still required

With a real Gemini key and a public HTTPS backend:

1. Load the widget on the separate website origin.
2. Ask: `Which one is for dry skin?` -> Cloud Cream.
3. Ask: `Does it work with acne?` -> exactly `I don't have that information yet.`
4. Ask: `How much did you say it costs?` -> $28 / Cloud Cream.
5. Close/reopen widget -> messages remain.
6. Refresh/reopen website -> messages return.
7. Remove the website origin from the allowlist -> calls fail.
8. Lower the rate limit temporarily and confirm excess requests receive 429.

Chunk 4 should be frozen only after this manual public-cross-site validation passes.
