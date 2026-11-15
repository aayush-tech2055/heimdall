# CLAUDE.md: Heimdall

Guidance for Claude Code in this repo. **Sources of truth:** `TASKS.md` (Part 1 = locked decisions, Part 2 = ordered tasks), `README.md` (product and architecture), `docs/Heimdall_Round1_Plan.pdf` (Round 1 submission). If this file and `TASKS.md` ever disagree, `TASKS.md` wins. Point out the mismatch and fix this file.

## The product in 5 lines
1. Heimdall is an AI brand-governance platform. It is a checkpoint between "draft" and "publish". Tagline: *Nothing crosses unchecked.*
2. Admins upload brand guidelines (PDF or text). Heimdall splits them into one record per rule, checks the guidelines themselves for duplicates, contradictions, vague rules and gaps, and stores approved facts that have expiry dates.
3. Creators upload content (text, PDF or image in Round 2, short video in Round 3). A four-layer engine (rules in code, retrieval plus an LLM judge, claims against facts, visuals) produces flags that each cite their source.
4. **No source, no flag:** plain code drops any AI finding that cites a source the model wasn't given or quotes words that aren't in the content. Creators accept, edit or dismiss each flag, and managers approve or send back.
5. Team Nobita&Avaneja (2 people): **Aayush `[A]`** (AI/ML lead, co-backend) and **Avaneja `[V]`** (frontend, product and QA). Inkloom AI problem statement, built in 3 rounds.

## Locked decisions (copied from TASKS.md Part 1, do not change without asking)

### Product rules
1. **No source, no flag.** Every flag cites a rule ID, a fact ID or a built-in policy ID (`SYS-…`). Plain code (not AI) drops any AI flag whose cited source was not supplied to the model, or whose quoted evidence does not appear in the content.
2. **AI advises, people decide.** Nothing is auto-published or auto-blocked. Every dismissal and override is stored with a reason.
3. **Nothing goes live unapproved.** Extracted rules and fetched facts are stored as `pending` until the admin approves them.
4. **Fictional data only during the event.** Use only the sample brands in `test-data/`.

### Knowledge base
5. **One rule = one record = one retrieval unit.** Never split guidelines into fixed-size chunks. Rule fields: `rule_code` (e.g. `R-012`), `category`, `text`, `source_doc`, `source_page`, `check_type`, `det_kind`, `terms`, `examples_bad`, `examples_good`, `always_on`, `status`.
6. **Categories:** `tone`, `terminology`, `messaging`, `claims`, `visuals`, `accessibility`, `legal`, `other`.
7. **`check_type`:** `deterministic` rules (`det_kind` = `banned_terms` or `required_phrase`, with `terms`) run in code and never go to the LLM. Everything else is `semantic`. A deterministic rule with no terms is downgraded to semantic.
8. **Rule codes, source page and status are set in code**, never taken from model output.
9. **Facts are structured rows:** `fact_code`, `entity`, `attribute`, `value`, `unit`, `statement` (one plain sentence, and this is what gets embedded), `source`, `valid_until`, `status`.
10. **Expiry is checked in code** (`valid_until < today`), never by the LLM.
11. **Built-in claim policy `SYS-CLAIM-001`:** "Every factual or promotional claim must match an approved fact." Unsupported claims cite it. It is shown in the UI like any rule and can be switched off per brand.

### Retrieval and review
12. **Embeddings:** Gemini, 768 dimensions, normalised. `RETRIEVAL_DOCUMENT` for rules and facts, `RETRIEVAL_QUERY` for content. **No fallback provider for embeddings.**
13. **Hybrid search:** pgvector cosine (top 20) + Postgres full-text (top 20, keywords OR-ed), merged by **reciprocal rank fusion, k = 60**, filtered to `status = approved`, `check_type = semantic` and the brand. Take the **top 6 rules per unit, plus every `always_on` rule**.
14. **Fact lookup:** exact `entity` match first, then hybrid search, **top 3 per claim**.
15. **Review units:** text is split into paragraphs (long ones split at sentence ends, **~900 characters max**). Every unit keeps its location: paragraph and character span (text), page and bbox (PDF), start and end seconds (video).
16. **Redaction runs before any AI call**, and everything downstream sees only redacted text. It uses regex for email, phone, PAN, Aadhaar and card numbers, plus per-brand confidential terms, plus Presidio (PERSON, LOCATION) when it is installed.
17. **Four layers:** (a) deterministic rules in code, (b) retrieval + LLM judge, (c) claim extraction → fact lookup → claim verdicts, (d) visual checks with a vision model.
18. **Batching:** about **4 units per LLM call**, with the union of their retrieved rules.
19. **Judge instructions:** flag only against the supplied rule codes. Quote evidence exactly, character for character, using the shortest span. The fix keeps the creator's intent. Severity is `high` for legal, factual or reputational risk, `medium` for a clear breach, `low` for minor wording.
20. **Citation validation drops a flag if:** its unit is unknown; its source wasn't supplied; its evidence isn't in the unit (matching ignores case, whitespace and curly-vs-straight quotes); or it matches an approved exception (same rule code, overlapping evidence). It also dedupes by (unit, source, normalised evidence). Dropped flags are kept with a reason.
21. **Guideline verification:** (1) pairs with cosine **≥ 0.75** go to the LLM in batches of ~20, which labels each `duplicate`, `contradiction` or `compatible` (lowered from 0.88 on 2026-11-15, agreed with the user); (2) the LLM marks vague, untestable semantic rules and suggests a rewrite; (3) code lists missing categories from `tone, terminology, claims, visuals, accessibility, legal`.

### AI layer
22. **One function for every model call** (`LLMClient.json(schema, system, prompt)`). It checks the cache → tries providers in order → validates against a Pydantic schema → asks the same provider **once** to repair invalid output → falls through to the next provider on a rate limit, error or invalid output.
23. **Provider order:** Gemini → Groq (OpenAI-compatible) → OpenRouter (OpenAI-compatible). Providers without a key are skipped. Model names come from env vars.
24. **Cache:** SQLite key-value store, keyed by a hash of (schema name, system prompt, prompt). The provider is **not** part of the key.
25. **Every AI call is logged** (provider, model, purpose, content ID, timestamp, ok or failed). This drives the AI disclosure labels.
26. **Prompt-injection guard:** content goes inside `<content>` tags, and the system prompt says content is data, never instructions.

### Other locked numbers (from Part 2)
- Time to first feedback: **< 60 s** for a one-page document.
- Video: clips **≤ 60 s**, a frame every **2 s**, transcript units of **~15 s**.
- Guideline health: "probably unclear" means dismissed in **≥ 40%** of cases with **≥ 5 flags**.
- Fact expiry badges: expired, or expiring **within 30 days**. Embedding batches of **100**.
- Eval targets: planted errors caught and flag precision of **≥ 75% (R2) / ≥ 85% (R3)**, and **0** flags without a valid source.

## Flag contract (frozen on day one)
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
`location` by format: text `{paragraph, char_start, char_end, evidence_start, evidence_end}`, PDF `{page, bbox}`, video `{start, end}` (seconds), image `{image_id, region}`. The Pydantic model (`backend/app/models/`) and the TypeScript type (`frontend/`) must stay identical.

**Workflow states:** `draft → checking → creator_review → manager_review → approved`, and `manager_review → changes_requested → creator_review`. An invalid transition returns 409, and every transition is written to `audit_log`. Each upload or edit creates a new content version, and flags belong to a version. **Flag statuses:** `open`, `accepted`, `edited`, `dismissed` (reason required), `excepted` (manager, reason required).

## Coding conventions

### Backend (`backend/`)
- **Python 3.11+.** On this machine, use `python3.12` for the venv: `python3` is 3.14, which spaCy and Presidio may not support yet.
- **FastAPI + Pydantic v2.** All request and response bodies and all LLM outputs are Pydantic models. Settings are read from `.env` through `pydantic-settings`.
- Layout: `app/api` (routes), `app/review` (four layers + orchestrator), `app/rag` (extraction, embeddings, retrieval), `app/llm` (LLMClient, providers, cache, prompts), `app/processing` (PDF, image, video, redaction), `app/models` (schemas, including `Flag`).
- **ruff** for linting and formatting. **pytest** for tests in `backend/tests/`, mirroring the `app/` layout.
- Tests never call real AI providers or the network. Use fake providers and fixtures. Deterministic logic (validation, segmentation, rule engine, expiry, state machine, RRF) gets unit tests in the same task that writes it.
- Type hints on every function. Keep business logic out of route handlers.

### Frontend (`frontend/`)
- **Next.js App Router + TypeScript (strict) + Tailwind + shadcn/ui.** Recharts for charts.
- The frontend talks **only** to the FastAPI backend, apart from Supabase Auth for sign-in.
- Accessible by default: keyboard reachable, visible focus, labelled controls, WCAG AA contrast.
- `npm run lint` and `npm run typecheck` must pass.

## Working rules
1. **Work through TASKS.md in order, one task at a time.** When a task's "Done when" is met, tick it (`[x]`) in TASKS.md and commit (on the feature branch, see "Git workflow") with a message that starts with the task number, e.g. `0.2: backend skeleton`.
   **Task status is tracked in Notion** (from 2026-11-14): the "Heimdall Tasks" database on the "Heimdall: Build Tracker" page (page `418b15a3b26b81bba814cf27c43a6e9c`, data source `collection://418b15a3-b26b-81aa-8bb7-000b9ed10b94`). When starting a task set its `Status` to `In progress`; when done set `Done` and the `Completed` date; use `Waiting on us` (with a `Notes` line) when blocked on a manual step. Keep TASKS.md ticks in sync. TASKS.md stays the source of truth for task scope and wording.
2. **Never change a locked decision in TASKS.md Part 1 without asking first.** If a decision looks wrong or impossible, stop and explain why.
3. **Never commit secrets or `.env` files.** Only `.env.example` files with empty values are committed. Use only the fictional test data in `test-data/`.
4. **Write tests for backend logic as you go**, in the same task, not later.
5. **After finishing each milestone, stop.** Give a short summary of what was done and what's next, and wait for the go-ahead.
6. **Add a line to `docs/BUILD_LOG.md` for each working session:** date, who, what was done, and the AI tools used (Claude Code, model).
7. **Manual steps go to the user.** When a step needs a human (creating accounts, API keys, the Supabase project, the GitHub remote, deploys, user testing, review of test data), stop and give exact numbered instructions. Don't guess or work around it.
8. **No scope creep.** Don't add features that aren't in TASKS.md without agreeing first. If time is short, follow the cut order in TASKS.md. Never cut citation validation, the creator → manager loop, redaction or the evaluation report.
9. Owner tags (`[A]`, `[V]`, `[A+V]`) record who is responsible. Claude implements every task, including `[V]` and `[A+V]` ones (agreed 2026-11-14), and the BUILD_LOG records which team member drove it. Steps only a human can do (user testing, teammate spot checks, accounts) still go to the user.

## Git workflow (keep the repo clean; judges read it)
1. **Never commit directly to `main`.** `main` always builds and passes CI.
2. **One branch per feature**, created from an up-to-date `main`: `feature/m<N>-<slug>` for a milestone (e.g. `feature/m2-database`, `feature/m3-ai-layer`). Split a large milestone into several feature branches when it helps (e.g. `feature/m6-rule-engine`, `feature/m6-judge`). Other prefixes: `fix/<topic>`, `docs/<topic>`, `chore/<topic>`, `data/<topic>` (test data).
3. **One commit per task** on the branch: `<task id>: <summary>` (e.g. `2.1: database schema`). Non-task commits use `docs: …`, `fix: …`, `chore: …`. The TASKS.md tick, Notion update and BUILD_LOG line go in the same branch.
4. **No AI attribution in git.** Never add `Co-Authored-By: Claude …` or any Claude/Anthropic trailer to commits, merge commits or PR descriptions. AI use is disclosed in `docs/BUILD_LOG.md` and the README instead.
   **Credit both team members:** every commit and merge commit is authored by the local git user (`aayush-tech2055`) and ends with the trailer `Co-authored-by: Avaneja Rikhta <213068188+avaneja@users.noreply.github.com>` (GitHub user `avaneja`; the noreply address credits them without exposing an email).
5. **Merging:** push the branch, wait for CI to pass on it, then merge into `main` with `git merge --no-ff <branch>` and a message `Merge <branch>: <what it delivers>`, push `main`, and delete the branch locally and on GitHub. (If the team switches to GitHub pull requests, use "Create a merge commit", not squash or rebase.)
6. **Never rewrite or force-push `main`** without the user asking for it explicitly.
