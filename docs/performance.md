# Performance (task 14.5)

Target: a one-page document gets first feedback in **under 60 seconds**.

Measured on 2026-11-15 on a MacBook, backend on localhost, Supabase in Singapore (session pooler),
free-tier models (Gemini `gemini-3.5-flash-lite` first). "First feedback" is the time from the
upload request until the content reaches `creator_review` with its flags saved, as seen by the
client polling once a second.

| Document | Size | Model answers | First feedback | Flags |
|---|---|---|---|---|
| Half a page, new text | 1,050 characters, 6 paragraphs | not cached | **28.6 s** (review itself 22.3 s) | 13 |
| One full page, new text | 2,928 characters, 22 paragraphs | not cached | **31.9 s** | 35 |
| Half a page, re-check | 1,050 characters | cached | 13.8 s | 13 |
| One test item (eval average) | ~150 characters | mostly cached | 3–6 s | – |

**Target met** with margin: about 30 s for a full page. Why it is fast enough:

- Layers (b) judge and (c) claims run in parallel, each with two workers; layer (a) runs in code.
- Units go to the judge four at a time and claims eight at a time, so a page is a handful of calls.
- Every model answer and embedding is cached (SQLite), so a re-check or a demo re-run is cheap.
- Most of the cached re-check time is database round trips to the Singapore region.

When it is slower: the free tiers rate-limit under load (Groq allows about 3 calls a minute with
real prompts; Gemini free quotas are per model and per day). `LLMClient` then waits up to 30 s and
retries the provider chain, so a busy minute can push a page past a minute. Videos take longer
(speech to text plus on-screen text and frame checks); a 7-second test clip took about 25 s.
