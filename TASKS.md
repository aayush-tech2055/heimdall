# Heimdall: build tasks

The complete, ordered task list for building Heimdall, from an empty folder to the Round 3 submission.
Read `README.md` first for what Heimdall is. This file is **how** it gets built.

**Owners:** `[A]` Aayush Ruparelia (AI/ML lead, co-backend) · `[V]` Avaneja Rikhta (frontend, product and QA, co-backend and AI) · `[A+V]` both.

**How to use this file**
- Work milestone by milestone, top to bottom. Inside a milestone, tasks with different owners can run in parallel.
- A task is done only when its **Done when** line is true. Tick the box `[x]` when it is.
- Don't add features that aren't listed here without agreeing first. Scope is what makes this buildable by two people.

---

## Part 1: Locked technical decisions

These were decided during planning. Follow them unless the team explicitly changes one, and update this section if that happens.

### Product rules
1. **No source, no flag.** Every flag cites a rule ID, a fact ID or a built-in policy ID (`SYS-…`). Plain code (not AI) drops any AI flag whose cited source was not supplied to the model, or whose quoted evidence does not appear in the content.
2. **AI advises, people decide.** Nothing is auto-published or auto-blocked. Every dismissal and override is stored with a reason.
3. **Nothing goes live unapproved.** Extracted rules and fetched facts are stored as `pending` until the admin approves them.
4. **Fictional data only during the event.** Free AI tiers may use submitted data for training. Use the sample brands in `test-data/` only.

### Knowledge base
5. **One rule = one record = one retrieval unit.** Guidelines are never split into fixed-size chunks. Each rule has: `rule_code` (e.g. `R-012`), `category`, `text`, `source_doc`, `source_page`, `check_type`, `det_kind`, `terms`, `examples_bad`, `examples_good`, `always_on`, `status`.
6. **Categories:** `tone`, `terminology`, `messaging`, `claims`, `visuals`, `accessibility`, `legal`, `other`.
7. **`check_type`:** `deterministic` rules (exact matching: `det_kind` = `banned_terms` or `required_phrase`, with `terms`) run in code and never go to the LLM. Everything else is `semantic`. A "deterministic" rule with no terms is downgraded to semantic.
8. **Rule codes, source page and status are set in code**, never trusted from the model's output.
9. **Facts are structured rows**, not text: `fact_code`, `entity`, `attribute`, `value`, `unit`, `statement` (one plain sentence), `source`, `valid_until`, `status`. The `statement` is what gets embedded.
10. **Expiry is checked in code** (`valid_until < today`), never by the LLM.
11. **Built-in claim policy:** `SYS-CLAIM-001`: "Every factual or promotional claim must match an approved fact." Unsupported claims cite this, so they still have a source. It is shown in the UI like any rule and can be switched off per brand.

### Retrieval and review
12. **Embeddings:** Gemini embeddings, 768 dimensions, normalised. Use `RETRIEVAL_DOCUMENT` for rules and facts and `RETRIEVAL_QUERY` for content. **No fallback provider for embeddings**, because vectors from different models can't be mixed.
13. **Hybrid search:** pgvector cosine similarity (top 20) + Postgres full-text search (top 20, keywords OR-ed), merged with **reciprocal rank fusion (k = 60)**, filtered to `status = approved`, `check_type = semantic` and the brand. Take the top 6 rules per unit, plus every `always_on` rule.
14. **Fact lookup:** exact `entity` match first, then hybrid search, top 3 per claim.
15. **Review units:** text is split into paragraphs (long ones at sentence ends, ~900 characters max). Every unit keeps its location: paragraph and character span for text, page and bounding box for PDFs, start and end seconds for video.
16. **Redaction runs before any AI call.** Everything after redaction sees only redacted text. Regex for email, phone, PAN, Aadhaar and card numbers, plus per-brand confidential terms, plus Presidio (PERSON, LOCATION) when installed.
17. **The four layers:** (a) deterministic rules in code, (b) retrieval + LLM judge, (c) claim extraction → fact lookup → claim verdicts, (d) visual checks with a vision model.
18. **Batching:** send about 4 units per LLM call, with the union of their retrieved rules.
19. **Judge instructions:** flag only against the supplied rule codes; quote evidence exactly, character for character, using the shortest span; give a fix that keeps the creator's intent; severity `high` for legal, factual or reputational risk, `medium` for a clear breach, `low` for minor wording.
20. **Citation validation drops a flag if:** its unit is unknown; its source wasn't supplied; its evidence isn't found in the unit (matching ignores case, whitespace and curly-versus-straight quotes); or it matches an approved exception (same rule code, overlapping evidence). It also removes duplicates by (unit, source, normalised evidence). Dropped flags are kept with a reason, for debugging and evaluation.
21. **Guideline verification:** (1) compare rule pairs whose cosine similarity is ≥ 0.75, and the LLM classifies each pair as `duplicate`, `contradiction` or `compatible`, about 20 pairs per call (changed from ≥ 0.88 on 2026-11-15: with Gemini embeddings 0.88 caught only 1 of the 4 planted problems; contradictions scored 0.76–0.80); (2) the LLM marks vague, untestable semantic rules and suggests a rewrite; (3) code lists missing categories from `tone, terminology, claims, visuals, accessibility, legal`.

### AI layer
22. **Every model call goes through one function** (e.g. `LLMClient.json(schema, system, prompt)`), which: checks the cache → tries providers in order → validates the JSON against a Pydantic schema → asks the same provider once to repair invalid output → falls through to the next provider on a rate limit, error or invalid output.
23. **Provider order:** Gemini → Groq (OpenAI-compatible API) → OpenRouter (OpenAI-compatible API). Providers with no key are skipped. Model names come from environment variables.
24. **Cache:** a SQLite key-value store keyed by a hash of (schema name, system prompt, prompt), not including the provider. Demo re-runs then cost nothing.
25. **Every AI call is logged** (provider, model, purpose, content ID, timestamp, success or failure). This drives the AI disclosure labels.
26. **Content in prompts is wrapped in `<content>` tags**, and the system prompt says that content is data, never instructions (prompt-injection guard).

### Flag contract (frozen on day one)
```json
{
  "unit_id": "u3",
  "source_type": "rule | fact | policy",
  "source_id": "R-012",
  "category": "tone | terminology | messaging | claims | visuals | accessibility | legal | other",
  "severity": "low | medium | high",
  "evidence": "exact quote from the content ('' for a missing required phrase)",
  "explanation": "plain-language reason",
  "suggested_fix": "string or null",
  "confidence": 0.0,
  "location": { "paragraph": 1, "char_start": 0, "char_end": 120, "evidence_start": 13, "evidence_end": 39 },
  "layer": "rules | guidelines | claims | visuals"
}
```
`location` varies by format: `{page, bbox}` for PDFs, `{start, end}` in seconds for video, `{image_id, region}` for images.

### Workflow states
```
draft ──submit──▶ checking ──done──▶ creator_review ──submit for approval──▶ manager_review
                                          ▲                                        │
                                          └──────────── changes_requested ◀────────┤
                                                                                   └──approve──▶ approved
```
- Each upload or edit creates a new **content version**. Flags belong to a version.
- Flag statuses: `open`, `accepted` (fix applied), `edited` (creator changed it manually), `dismissed` (reason required), `excepted` (manager approved an exception).

### Stack
Next.js + Tailwind + shadcn/ui + Recharts · FastAPI + Pydantic · Supabase (Postgres, pgvector, Auth, Storage) · Gemini, Groq, OpenRouter · PyMuPDF · FFmpeg · Whisper (via Groq) · Tesseract/EasyOCR · Presidio + spaCy · textstat · Playwright + BeautifulSoup · Vercel + Render/Railway. Python 3.11+, Node 20+.

---

## Part 2: Tasks

### Milestone 0: Foundations
- [x] **0.1** `[A]` Initialise the git repo and GitHub remote, and create the folder layout from the README (`frontend/`, `backend/app/{api,review,rag,llm,processing,models}`, `backend/tests/`, `db/`, `test-data/`, `docs/`). Add `.gitignore` (Python, Node, `.env*`, cache files, `.DS_Store`).
  *Done when:* the repo is on GitHub with the structure and README; the first commit is dated inside the build window.
- [x] **0.2** `[A]` Backend skeleton: FastAPI app, `pyproject.toml` or `requirements.txt`, a settings module reading `.env`, `GET /health`, and pytest + ruff set up.
  *Done when:* `uvicorn` starts, `/health` returns 200, and `pytest` runs.
- [x] **0.3** `[V]` Frontend skeleton: Next.js (App Router, TypeScript), Tailwind, shadcn/ui, a layout shell and an empty page for each role.
  *Done when:* `npm run dev` shows the shell with navigation to the admin, creator and manager pages.
- [x] **0.4** `[A]` Create the Supabase project, enable `vector`, and get the Gemini, Groq and OpenRouter API keys. Write `backend/.env.example` and `frontend/.env.example`.
  *Done when:* both example env files list every variable, and real values sit only in local `.env` files.
- [x] **0.5** `[A+V]` Freeze the flag contract: a Pydantic `Flag` model in `backend/app/models/` and a matching TypeScript type in `frontend/`.
  *Done when:* both exist, match Part 1 exactly, and are committed.
- [x] **0.6** `[A]` CI: a GitHub Actions workflow that runs ruff and pytest (backend) and lint + typecheck (frontend) on every push.
  *Done when:* CI is green on `main`.
- [x] **0.7** `[A+V]` Start `docs/BUILD_LOG.md`: date, who, what was done, and any AI tools or templates used. Update it every working day (needed for the contribution and disclosure requirements).

### Milestone 1: Test data (starts in parallel with M0)
- [x] **1.1** `[V]` Create 2 fictional brands in `test-data/brands/<brand>/`: a brand guideline (a 3–5 page PDF plus the same content as `.md`) covering tone, terminology, claims, visuals, accessibility and legal, including **2 deliberately vague rules, 1 contradiction and 1 duplicate** (to test guideline verification).
- [x] **1.2** `[V]` A facts sheet per brand as `facts.csv` (entity, attribute, value, unit, statement, source, valid_until), with at least 15 facts, **2 of them already expired**.
- [x] **1.3** `[V]` 30–40 pieces of sample content per brand (blog posts, social captions, ad scripts) with **planted errors**: banned terms, a missing disclaimer, an outdated price, an unsupported superlative, a contradicted statistic, an off-tone sentence. Include some content with no errors.
- [ ] **1.4** `[V]` An answer key, `test-data/answer_key.json`: for each content item, the expected flags (unit text, rule or fact code, category). Clean items have an empty list.
  *Done when:* every planted error appears in the answer key, and a teammate has spot-checked 10 items.

### Milestone 2: Database
- [x] **2.1** `[A]` `db/schema.sql` with these tables (all keyed to `brand_id`):
  `brands`, `profiles` (user ID → role: admin, creator or manager, plus brand), `rules` (+ `embedding vector(768)`, generated `tsvector`, HNSW and GIN indexes), `facts` (same), `assets` (Round 3), `approved_exceptions`, `contents` (title, format, status, creator), `content_versions` (number, storage path, extracted text), `review_units` (version, unit_id, text, location JSON), `flags` (version + the flag contract fields + status + resolution note), `comments` (version, author, body, optional flag ID), `audit_log` (actor, action, entity, before/after JSON, timestamp), `ai_calls` (provider, model, purpose, content version, ok, latency, timestamp), `brand_settings` (confidential terms, claim policy on/off).
  *Done when:* the schema runs cleanly on a fresh Supabase project.
- [x] **2.2** `[A]` Row-level security policies: creators see only their own content, managers and admins see their brand, and only admins write rules and facts.
  *Done when:* a test with two users confirms a creator cannot read another creator's content.
- [x] **2.3** `[A]` A seed script that loads one test brand plus users with each role.

### Milestone 3: AI layer
- [x] **3.1** `[A]` `llm/` module: the `LLMClient.json()` behaviour from decisions 22–26 (Gemini, Groq and OpenRouter providers; schema in the prompt; strip code fences; repair once; fallback; SQLite cache; per-call logging to `ai_calls`).
  *Done when:* unit tests with fake providers prove that a cache hit makes no call, that a rate limit falls through to the next provider, that invalid JSON is repaired once, and that the error is clear when every provider fails.
- [x] **3.2** `[A]` `Embedder`: Gemini embeddings, batches of 100, normalised, cached, with retry and backoff on rate limits.
- [x] **3.3** `[A]` `prompts.py`: one place for every prompt (rule extraction, pair check, vagueness check, judge, claim extraction, claim verification, fact extraction).

### Milestone 4: Guideline ingestion and verification
- [x] **4.1** `[A]` Parsing: PDF to pages with PyMuPDF; pasted text to page-sized parts split on paragraphs.
- [x] **4.2** `[A]` Rule extraction: one LLM call per page, then codes, page, source and `pending` status set in code (decisions 5–8).
  *Done when:* on a test brand guide, every rule appears once with the correct page.
- [x] **4.3** `[A]` Embed and store rules as `pending`.
- [x] **4.4** `[A]` Guideline verification (decision 21), returning a report of duplicates, contradictions, vague rules and missing categories.
  *Done when:* it finds the planted vague rules, contradiction and duplicate from task 1.1.
- [x] **4.5** `[A]` API: `POST /brands/{id}/guidelines` (upload → extract → verify → report), `GET /brands/{id}/rules?status=`, `PATCH /rules/{code}` (edit text or category), `POST /rules/approve` (bulk approve or reject).
- [x] **4.6** `[V]` Admin screen: upload guidelines, view extracted rules grouped by category with their page, the verification report at the top (each issue linked to its rules), edit a rule, approve or reject in bulk.

### Milestone 5: Facts
- [x] **5.1** `[A]` Fact store: add (approved immediately when an admin types it in), edit, import CSV, embed statements, entity-plus-hybrid search (decision 14).
- [x] **5.2** `[A]` API: `GET/POST/PATCH /brands/{id}/facts`, `POST /brands/{id}/facts/import`.
- [x] **5.3** `[V]` Admin facts screen: a table with search, expiry badges (expired, expiring within 30 days), add, edit and CSV import.

### Milestone 6: Review engine for text (core of Round 2)
- [x] **6.1** `[A]` Segmentation for text: units with paragraph and character span (decision 15).
- [x] **6.2** `[A]` Redaction (decision 16) with per-brand confidential terms from `brand_settings`.
- [x] **6.3** `[A]` Layer (a), the rule engine: banned terms (whole-word, case-insensitive, flag every occurrence with its span) and required phrases (checked across the whole document; if missing, one flag with empty evidence).
- [x] **6.4** `[A]` Layer (b): hybrid retrieval (decision 13) plus the batched judge (decisions 18–19).
- [x] **6.5** `[A]` Layer (c): claim extraction (keep only claims that are real quotes) → fact lookup → verdicts. Expired supported facts are flagged as outdated, contradicted claims cite the fact, unsupported claims cite `SYS-CLAIM-001`, and a "contradicted" verdict that cites no real fact is dropped.
- [x] **6.6** `[A]` Citation validation (decision 20), including absolute evidence offsets for text.
- [x] **6.7** `[A]` Orchestrator `review_content(version_id)`: units → redact → (a), (b), (c) → validate → sort by position, then severity → save units, flags and dropped flags → set status to `creator_review`. Runs as a FastAPI background task.
- [x] **6.8** `[A]` API: `POST /contents` (upload text or file → new version → start the review), `GET /contents/{id}` (status, versions), `GET /versions/{id}/flags`.
  *Done when:* uploading a test blog post returns cited flags within 60 seconds, and every flag passes validation.
- [x] **6.9** `[A]` Evaluation script `backend/eval/run_eval.py`: runs every test item, compares the flags with the answer key, and reports recall, precision, retrieval recall (was the expected rule in the retrieved top-k?) and flags without a valid source (must be 0), per category. It writes `docs/eval/<date>.md`.

### Milestone 7: Creator and manager workflow
- [x] **7.1** `[A]` The workflow state machine from Part 1, enforced in the API (an invalid transition returns 409). Every transition is written to `audit_log`.
- [x] **7.2** `[A]` Flag actions: `POST /flags/{id}/accept` (apply the fix to the text and create a new version), `/edit`, `/dismiss` (reason required). Re-running the review on the new version keeps resolved flags resolved.
- [x] **7.3** `[A]` Manager actions: `POST /contents/{id}/approve`, `/request-changes` (comment required), `POST /flags/{id}/except` (reason required, creates an `approved_exceptions` row).
- [x] **7.4** `[A]` Comments: `GET/POST /versions/{id}/comments`, optionally tied to a flag.
- [x] **7.5** `[V]` Sign-in with Supabase Auth, and routing by role.
- [x] **7.6** `[V]` Creator upload screen: paste text or upload a file, choose a brand, and see the processing state.
- [x] **7.7** `[V]` Creator review screen: the content with highlighted evidence spans (colour by severity), a flag list beside it (category, severity, source chip that shows the rule or fact text on hover, explanation, suggested fix), Accept / Edit / Dismiss-with-reason, and "Submit for approval" once no high-severity flags are open (or each one has a reason).
- [x] **7.8** `[V]` Manager queue and review screen: a list of content waiting for review; the content with only unresolved and dismissed flags plus their reasons; comments; approve, request changes or approve an exception.
- [x] **7.9** `[V]` Version history: a list of versions, a diff between versions, and the flags per version.
  *Done when (M7):* a full loop works in the browser: admin sets rules → creator uploads → fixes → submits → manager sends back → creator fixes → manager approves, with every step in the audit log.

### Milestone 8: PDF and images
- [x] **8.1** `[A]` PDF content: units from text blocks with page and bounding box; images inside the PDF are extracted for layer (d).
- [x] **8.2** `[A]` Layer (d), visual checks: the vision model gets the image plus approved visual rules and asset descriptions, and returns flags (wrong logo version, colours outside the palette, off-brand imagery, missing alt text where it applies). Evidence is a region description; the source must be a visual rule.
- [x] **8.3** `[A]` Accessibility checks in code: WCAG contrast ratio for text colours when available, alt text present for images, readability score per unit (textstat) against the brand's target.
- [x] **8.4** `[V]` PDF viewer in the creator and manager screens with flag highlights by page and box, and an image viewer with a flag list.

### Milestone 9: Privacy and AI disclosure
- [ ] **9.1** `[A]` Presidio integration (optional when not installed) plus a confidential-terms editor in the brand settings API.
- [ ] **9.2** `[V]` An "AI used" label on every AI-generated flag and fix (provider and model, from `ai_calls`), and a disclosure page listing each service, what data is sent, and the redaction rules.
- [ ] **9.3** `[V]` Brand settings screen: confidential terms, claim policy on/off, readability target.

### Milestone 10: Round 2 submission
- [ ] **10.1** `[A]` Deploy: frontend to Vercel, backend to Render or Railway, environment secrets set, seeded with a test brand.
- [ ] **10.2** `[A]` Demo mode: pre-run the demo content so results come from the cache; check that fallback works by disabling the Gemini key.
- [x] **10.3** `[A]` Run the evaluation (6.9) and save the report; fix the worst category.
- [ ] **10.4** `[V]` User testing with 3–5 people outside the team, using a script of tasks; record what confused them and fix the top 3 issues.
- [ ] **10.5** `[A+V]` Submission package: deployed demo link, repo access, architecture diagram, **list of APIs, models and datasets used**, testing evidence (eval report + user testing notes), each member's contribution (from `BUILD_LOG.md`), updated README with real setup steps.
- [ ] **10.6** `[A+V]` Name the **three Round 3 improvements** in the submission (video review; website import + asset library; insights + guideline health with measured accuracy gains).

### Milestone 11: Round 3, improvement 1: video
- [ ] **11.1** `[A]` FFmpeg: extract audio, and sample frames every 2 s (clips up to 60 s).
- [ ] **11.2** `[A]` Speech-to-text with Groq Whisper (segments with timestamps), then units in ~15 s windows.
- [ ] **11.3** `[A]` OCR of on-screen text per frame, with timestamps (deduplicate repeated text).
- [ ] **11.4** `[A]` Run the existing layers on transcript and OCR units, and layer (d) on frames; every flag has `{start, end}`.
- [ ] **11.5** `[A]` Caption checks: captions exist, and caption text matches the transcript.
- [ ] **11.6** `[V]` Video player with flags on a timeline; clicking a flag jumps to its timestamp.

### Milestone 12: Round 3, improvement 2: website facts and asset library
- [ ] **12.1** `[A]` Scraper: Playwright for a list of company URLs, cleaned text per page.
- [ ] **12.2** `[A]` Fact extraction from pages, then a **diff in code** against approved facts by (entity, attribute) with normalised values: `new` or `changed` with old value → new value.
- [ ] **12.3** `[A]` Approval: approved changes are written; changed facts **keep their fact code** so old citations stay valid.
- [ ] **12.4** `[A]` Assets: upload logos, disclaimers, product descriptions and templates with a description; used by layer (d) and by fixes (a missing disclaimer → insert the approved text).
- [ ] **12.5** `[V]` Admin screens: "Check website" with a reviewable list of changes (accept or reject each), and an asset library.

### Milestone 13: Round 3, improvement 3: insights and guideline health
- [ ] **13.1** `[A]` Insight queries: flags by category, severity, rule and creator over time; the most broken rules; average time to approval; how often content is sent back.
- [ ] **13.2** `[A]` Guideline health: dismissal rate per rule; rules dismissed in at least 40% of cases (with at least 5 flags) are marked "probably unclear", with the most common dismissal reasons.
- [ ] **13.3** `[V]` Insights dashboard (Recharts): trends, top broken rules, guideline health list linking to each rule's edit screen.
- [ ] **13.4** `[A]` Re-run the evaluation and compare with the Round 2 report; record the accuracy gain.

### Milestone 14: Hardening
- [ ] **14.1** `[A]` Tests: unit tests for validation, segmentation, rule engine, expiry, the workflow state machine and permissions; one end-to-end API test of the full loop.
- [ ] **14.2** `[V]` Error and empty states on every screen (AI unavailable, upload failed, no rules approved yet).
- [ ] **14.3** `[V]` Accessibility audit of Heimdall's own interface: keyboard navigation, focus states, contrast, labels (axe or Lighthouse ≥ 90).
- [ ] **14.4** `[A]` Security pass: no secrets in the repo, RLS verified, file type and size limits, rate limiting on review endpoints, prompt-injection test content in the test set.
- [ ] **14.5** `[A]` Performance: a one-page document gets first feedback in under 60 s; record timings.

### Milestone 15: Round 3 submission
- [ ] **15.1** `[V]` Demo video (3–5 minutes): the full loop, guideline verification, a video review, a website fact change, the insights dashboard.
- [ ] **15.2** `[A+V]` Final report: what was built, evidence of testing and of the three improvements (eval before and after), privacy, security and accessibility explanation, **known limitations**, roadmap.
- [ ] **15.3** `[A+V]` Final README: setup, architecture, screenshots, the complete AI and tool disclosure.
- [ ] **15.4** `[A+V]` Rehearse: both members can explain any part of the system and the evaluation numbers.

---

## Scope rules if time runs short

Cut in this order, so the core loop is always protected:
1. Insights charts (keep the guideline health list)
2. Asset library
3. Website fact import
4. Video on-screen text OCR (keep the transcript)
5. Video entirely

Never cut: citation validation, the creator → manager loop, redaction, the evaluation report.
