# Security, privacy and access (task 14.4)

## Access control

- **Sign-in**: Supabase Auth (email and password). The API verifies every access token against
  the project's public keys (JWKS, ES256), with HS256 as a fallback for legacy projects.
- **Roles and brands, checked on every route**: admins manage guidelines, facts, assets, settings
  and the website check; creators upload and fix their own content; managers approve, send back
  and approve exceptions; everyone works only on their own brand. Content a user may not see is
  reported as not found. The backend connects as the database owner, so these checks live in
  `backend/app/api/deps.py` and each route, and are tested in `backend/tests/api` and
  `backend/tests/db`.
- **Row-level security** is on for every table (`db/schema.sql`), with policies in
  `db/policies.sql`: creators see only their own content; managers and admins see their brand;
  only admins write rules, facts, assets and settings; workflow tables are read-only through the
  Supabase API; anonymous callers see nothing; nobody can change their own role.
  `backend/tests/db/test_rls.py` proves it with two creators, a manager, an admin and a second
  brand, and `test_schema.py` checks that every table has RLS switched on.
- **Workflow**: content moves only through the state machine (`app/review/workflow.py`); an
  invalid move returns 409 and every move is written to `audit_log`.

## Secrets

- No `.env` file is tracked; only the empty `.env.example` templates are committed. A scan of
  every tracked file for API-key and database-URL patterns (Gemini, Groq, OpenRouter, JWTs,
  Postgres URLs) found nothing on 2026-11-15.
- The Supabase service role key stays on the backend; the frontend only has the publishable key.
- AI attribution is never written into git; AI use is disclosed in `docs/BUILD_LOG.md`, the
  README and the in-app AI disclosure page.

## Uploads

| Kind | Accepted (checked by file signature, not the name) | Limit |
|---|---|---|
| Guideline | PDF | 10 MB |
| Facts | UTF-8 CSV | 2 MB |
| Content | text (100,000 characters), .txt/.md, PDF, PNG/JPEG, MP4/MOV/WebM (≤ 60 s) | 20 MB PDF and video, 10 MB image |
| Captions | .srt / .vtt | 512 KB |
| Assets | PNG/JPEG | 5 MB |

Files go to a private Supabase Storage bucket and are served only through the API after the
same visibility checks as the content.

## Rate limits

Per user, in memory (`app/api/ratelimit.py`): 30 reviews per 10 minutes (new content, new
versions, re-checks, accepted or edited fixes), 10 guideline uploads or re-verifications and 10
website checks per 10 minutes. Over the limit the API returns 429 with `Retry-After`. A
multi-process deployment would move the counters to Redis or the database.

## AI and privacy

- **Redaction before any AI call** (`app/processing/redaction.py`): email, phone, PAN, Aadhaar,
  card numbers (Luhn-checked), the brand's confidential terms, and names and places when Presidio
  is installed. Flags still point at the original words through an offset map.
- **Prompt injection**: content goes inside `<content>` tags (embedded tags are neutralised) and
  every system prompt says it is data, never instructions. Citation validation then drops any flag
  that cites a source the model was not given or quotes words that are not in the content, so a
  hijacked answer cannot invent flags. The test set has one injection item per brand (`acme-31`,
  `bb-31`); both planted errors were still flagged (2026-11-15).
- **Fictional data only** during the event, including the website check, which reads a fictional
  site served by the backend.

## Open items (need a person)

- Supabase security advisor (2026-11-15): **leaked password protection is disabled**. Turn it on in
  the Supabase dashboard: Authentication → Providers (or Policies) → Password security → "Prevent
  use of leaked passwords".
- Before a public deployment: set `CORS_ORIGINS` to the deployed frontend only, and rotate any key
  that was ever pasted into a file by mistake.
