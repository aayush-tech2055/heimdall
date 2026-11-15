# Heimdall: final report

**Team Nobita&Avaneja** · Inkloom AI brand-governance problem statement · Newton School of
Technology, Rishihood University

Heimdall is a checkpoint between "draft" and "publish". A brand admin turns the brand's guideline
into approved rules and keeps a sheet of approved facts; every piece of content a creator writes
(text, PDF, image or a short video) is checked against them before a manager approves it. Every
flag cites the exact rule, fact or policy behind it, quotes the words that break it, and suggests a
fix. People make every decision.

## 1. What we built

**Admin: the brand's knowledge.** Upload a guideline PDF or paste text. Heimdall splits it into
one rule per instruction with its page, marks exact word lists and required lines to be checked in
code, and checks the guideline itself: duplicate rules, contradicting rules, vague rules (with a
testable rewrite) and missing categories. Nothing is used until the admin approves it. Facts
(entity, attribute, value, source, expiry date) are typed in or imported from CSV; expired and
soon-to-expire facts are badged. A website check reads the brand's pages, finds facts that are new
or changed, and waits for the admin; an accepted change keeps its fact code, so everything that
cited it stays linked. An asset library holds logos and approved text such as disclaimers.

**Creator: checking and fixing.** Paste text or upload a text file, PDF, image or a clip of up to
60 seconds. The review shows the content with every problem highlighted (page boxes for PDFs,
regions for images, a timeline for video), and a card per flag: severity, category, the cited
source (hover to read it), whether code or AI found it and which model, the explanation and a
suggested fix. The creator accepts the fix (a new version, checked again), edits it, or dismisses
the flag with a reason, then submits for approval once no high-severity flag is open.

**Manager: deciding.** A queue of content waiting for approval; the review shows only unresolved
and dismissed flags with their reasons. The manager approves, sends back with a comment, or
approves an exception, which is remembered so the same wording is not flagged again.

**Insights.** Flags over time and by category, the most-broken rules, time to approval, how often
content is sent back, and guideline health: a rule dismissed in at least 40% of its (at least 5)
flags is marked "probably unclear", with the most common reasons, so the admin can rewrite it.

### How a review works

1. The content is split into units: paragraphs (long ones at sentence ends), PDF text blocks with
   their boxes, or 15-second stretches of speech plus on-screen text for video.
2. Sensitive data is masked **before any AI call**: email, phone, PAN, Aadhaar and card numbers,
   the brand's confidential terms, and names and places.
3. Four layers run:
   (a) banned words and required lines, **in code**;
   (b) each unit's six most relevant approved rules (pgvector + full-text search, merged by
   reciprocal rank fusion) plus always-on rules go to an AI judge, four units per call;
   (c) claims are extracted, matched to approved facts (exact entity first, then hybrid search) and
   judged supported, contradicted or unsupported; expiry is decided in code;
   (d) images and video frames go to a vision model with the visual rules and asset descriptions.
4. **Citation validation, in plain code**, drops any AI flag whose source was not given to the model
   or whose quote is not in the content, plus exceptions, duplicates and the brand's own required
   text. Dropped flags are kept with the reason.
5. Every model call goes through one client: cache → Gemini → Groq → OpenRouter, one repair
   attempt for malformed output, and a wait-and-retry when every free tier is busy.

## 2. Evidence of testing

**Test set.** Two fictional brands (AcmeLearn, an online-learning platform, and Brewbird Coffee),
each with a 5-page guideline containing 2 vague rules, a duplicate and a contradiction; 17 facts
(2 expired); 31 content items (8 clean, 1 prompt-injection test) with 56 planted errors in total;
and an answer key with the exact quote, source and category of each.

**Evaluation** (`backend/eval/run_eval.py`, reports in [`eval/`](eval/)):

| Run | Recall | Precision | Retrieval recall | Flags without a valid source |
|---|---|---|---|---|
| Round 2 baseline | 98% | 63% | 95% | 0 |
| After fixing the worst category (claims) | 98% | 79% | 95% | 0 |
| Round 3 re-run | 96% | 75% | 95% | 0 |

The baseline's main error was the brand's own required disclaimer being flagged as a claim; making
validation drop AI flags inside required text, and tightening two prompts, raised claims precision
from 52% to 76%. The Round 3 re-run differs by about four points, which we attribute to the free
"lite" model answering a few changed prompts differently ([comparison](eval/comparison.md)).
Guideline verification found all 8 planted problems with `gemini-3.5-flash`; the lite model found
the vague rules and Brewbird's duplicate and contradiction but missed AcmeLearn's in one run.

**Automated tests.** 231 unit tests (no network) and 56 database tests against Supabase, each
rolled back. They cover citation validation, segmentation, redaction offsets, the rule engine,
expiry, retrieval fusion, the AI client's cache, fallback and repair, the workflow state machine,
row-level security with two creators, a manager, an admin and a second brand, and one end-to-end
API test of the whole creator → manager loop. CI runs ruff, pytest, ESLint and the TypeScript
check on every push.

**Live checks** (recorded in the build log): a PDF flyer (banned word and contradicted statistic
with page boxes; a palette breach found by the vision model in its image); a synthetic video ad
(issues in the speech and on screen, each with its time range); the website check on a fictional
site (all three planted changes, nothing unchanged reported); a review with Gemini switched off
(Groq took over and still flagged the contradicted statistic).

**Performance** ([details](performance.md)): a new one-page document gets first feedback in
**32 seconds** (target 60); a cached re-check takes 14 seconds.

**User testing:** not yet done; see section 6.

## 3. The three Round 3 improvements

1. **Short video review**: speech to text (Groq Whisper) in 15-second units, on-screen text from
   distinct frames, visual checks on the frames, caption checks, and a player with flags on a
   timeline.
2. **Website fact import and the asset library**: a fact check against the brand's own pages with a
   diff done in code and admin approval (codes kept), plus approved assets that feed the image checks
   and become the fix for a missing disclaimer.
3. **Insights and guideline health**: trends, the most-broken rules, approval time and send-back
   rate, and the "probably unclear" rule list; accuracy re-measured on the same test set.

## 4. Privacy, security and accessibility

- **Privacy.** Masking runs before every AI call, and flags still point at the creator's original
  words through an offset map. Only fictional data is used during the event, because free AI tiers
  may train on submitted data. The AI disclosure page lists each service, what it receives and how
  often it was called.
- **Security** ([details](security.md)). Sign-in with Supabase Auth; every API route checks role and
  brand; row-level security on every table; uploads checked by file signature and size; per-user
  rate limits on costly endpoints; prompt-injection resistance by design (content in tags, plus
  citation validation) and tested; no secrets in the repository.
- **Accessibility** ([details](accessibility.md)). Heimdall checks content for contrast, alt text,
  readability and captions, and its own interface passes axe-core (WCAG 2.1 AA) with **0
  violations** on all 15 screens, with full keyboard access and no meaning carried by colour alone.

## 5. Known limitations

- **Free tiers set the ceiling.** Precision is 75–79% against the 85% Round 3 target; the stronger
  Gemini model allows only 20 requests a day for free, and the lite model varies between runs.
  Heavy use can hit rate limits, which slows reviews rather than failing them.
- Generic sentences are sometimes flagged as unsupported claims, and tone flags can be nitpicky.
- Speech to text writes names as they sound ("Acme Learn"), which can trip the brand-name rule.
- Fixes cannot be applied inside PDFs, images or videos; the creator uploads a corrected file.
- The contrast check assumes a white page; only raster images inside PDFs are checked visually.
- Rate limits are in memory (one backend process); a multi-server deployment needs a shared store.
- The interface has no dark mode. Not yet deployed or tested with outside users.

## 6. Still to do (needs people)

- Deploy (Vercel and Render or Railway) and add the demo link.
- User testing with 3–5 people outside the team, and fixing the top three issues.
- A teammate spot-check of 10 answer-key items; the demo video; rehearsal.

## 7. Roadmap

A stronger model for guideline verification and the judge when budget allows; a per-brand
confidence threshold learned from dismissals (guideline health already collects them); regenerating
fixed PDFs; brand-wide approval policies; deployment with shared rate limits.
