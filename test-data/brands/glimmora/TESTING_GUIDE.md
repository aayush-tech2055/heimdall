# Testing Heimdall with Glimmora (fictional toothpaste brand)

A complete kit for testing every feature by hand. Glimmora and its competitors **Whitebay** and
**Pearlo** are invented; no real brand is used (project rule 4).

| File | What it is |
|---|---|
| `guidelines.pdf` (from `guidelines.md`) | 6-page brand guideline with 34 rules across tone, terminology, messaging, claims, visuals, accessibility and legal. It contains 4 planted guideline problems (see Step 2). |
| `facts.csv` | 14 approved facts: 1 expired, 1 expiring within 30 days |
| `glimmora_logo.png` | the correct logo, for the asset library |
| `ad_script_with_errors.txt` / `.pdf` | a 45-second TV ad script with about 30 planted mistakes, including a false claim about the competitor Whitebay |
| `ad_script_clean.txt` | the same ad written correctly (a control: it should get very few flags) |
| `poster_with_errors.png` | a print poster with visual and accessibility mistakes |
| `injection_test.txt` | content that tries to tell the AI to report nothing |

**Logins** (password: `SEED_USER_PASSWORD` in `backend/.env`):
`admin@glimmora.example`, `manager@glimmora.example`, `creator@glimmora.example`.
This brand is separate from AcmeLearn, so the two never mix.

**Start the app:** `cd backend && .venv/bin/uvicorn app.main:app --port 8010`, then in a second
terminal `cd frontend && npm run dev`, and open http://localhost:3000.

---

## Step 1. Admin › Settings: confidential terms
Sign in as **admin**. Check that *Project Neelkanth* and *Formula GX-7* are listed as confidential
terms. They will be masked before any AI call.

## Step 2. Admin › Guidelines: upload the PDF and verify it
Upload `guidelines.pdf` (the admin can also upload the guideline as Word, PowerPoint, `.txt`, `.md` or CSV; try `guidelines.md` on a second run). In about 30 seconds you get the rules (each with its page) and a
verification report. **Expected findings:**

| Problem | Rules involved | What to do |
|---|---|---|
| Vague | "Our communication should always feel fresh and premium." (page 1) | Reject it, or use the suggested rewrite |
| Vague | "Messaging should be powerful and memorable." (page 3) | Reject it, or use the rewrite |
| Duplicate | "Write in simple, everyday English and avoid dental jargon…" (p1) and "Use plain everyday English instead of dental jargon…" (p5) | Reject one of them |
| Contradiction | "Headlines should use capital letters for every word…" (p3) and "never write whole words in capital letters" (p1) | **Reject the headline rule** |
| Missing categories | none: all six are covered | – |

Also check:
- The banned words (*miracle, cure, guaranteed, permanent, painless*), the brand misspellings, and
  the line "Results may vary. Use twice daily as directed." are marked as **checked in code**.
- Then approve the remaining rules.

## Step 3. Admin › Facts: import `facts.csv`
- Approve all 14 facts.
- **Expected badges:** "HealthWise Readers' Choice 2024" shows **Expired** (valid until 2025-12-31).
  The dentist survey ("7 out of 10") shows **Expiring soon** (valid until 2026-12-10).

## Step 4. Admin › Assets
- Upload `glimmora_logo.png`, with the description "Approved Glimmora logo: teal circle with a white
  G, teal wordmark, on pearl white".
- Add an approved text asset: "Results may vary. Use twice daily as directed."

## Step 5. Creator: check the faulty ad script
Sign in as **creator**, open **New check** and upload `ad_script_with_errors.txt` (or paste it).
Feedback should arrive in under 60 seconds. For each flag, check three things:
- the highlight sits on the right words;
- the card names the rule or fact it breaks (hover the code to read it);
- it says whether code or AI found it, and it gives a fix.

**Planted mistakes, and what should catch them:**

| # | Quote in the script | What's wrong | Source it should cite |
|---|---|---|---|
| 1 | "Ugh. Nobody wants to stand next to someone with yellow, stinky teeth." | Fear and shame used to sell | Tone: never use fear, shame or disgust |
| 2 | "Don't be that guy in the lift!" | Mocking; exclamation mark | Tone rules |
| 3 | "Glimora" (×2) | Brand name misspelled | Terminology: write Glimmora (code) |
| 4 | "miracle" | Banned word | Banned-words rule (code) |
| 5 | "kills 99.9% of germs" | Contradicts the fact: **99%** | Fact: Active Shield germ protection |
| 6 | "guaranteed protection from cavities" | Banned word; also a guarantee claim | Banned words (code), claims rule |
| 7 | "for 24 hours" | Contradicts the fact: **12 hours** | Fact: cavity protection |
| 8 | **"Unlike Whitebay, which is full of harsh bleach that slowly destroys your enamel"** | **False claim about a competitor**, named | Legal: never mention competitors |
| 9 | "India's No. 1 toothpaste" / "the best choice" | Superlatives with no fact behind them | Messaging: no superlatives; SYS-CLAIM-001 |
| 10 | "9 OUT OF 10 DENTISTS RECOMMEND GLIMMORA!" | Contradicts the survey (**7 out of 10**) and doesn't name it; capitals | Fact: dentist survey; dentist-claim rule; tone |
| 11 | "white text on mint background, on screen for 1 second" | Low contrast; text shown under 3 s | Accessibility rules |
| 12 | "nano-hydroxyapatite … remineralises demineralised enamel lesions" | Jargon that isn't explained | Tone / plain-English rule |
| 13 | "reverses tooth decay permanently" | Treatment claim; banned word "permanent" | Claims: never claim to cure or reverse; banned words |
| 14 | "Project Neelkanth" | Confidential term | **Masked before AI** (no flag needed) |
| 15 | "bright red background", "full-length strip of paste", "logo is stretched" | Visual rules | Visuals rules (may be found from the scene text) |
| 16 | "A four-year-old girl brushes her teeth alone" | Child under 6 without an adult | Visuals: children with an adult |
| 17 | "the sensitive one" | Product nickname | Terminology: full product names |
| 18 | "painless relief in just 3 days" | Banned word; contradicts the fact: **14 days** | Banned words (code); fact: relief time |
| 19 | "Kids love Glimmora Kids Strawberry too!" | Kids line missing ("For children under 6…") | Legal: kids supervision line |
| 20 | "Priya Sharma … I switched from Pearlo" | Customer name without consent; second competitor | Legal rules (the name is masked) |
| 21 | "my cavities are cured" | Banned word; cure claim | Banned words (code); claims rule |
| 22 | "98201 45678", "priya.sharma@example.com" | Phone and email | **Masked before AI**; legal rule |
| 23 | "Winner of the Readers' Choice Award" | Expired fact; no awarding body or year | Fact (expired); award rule |
| 24 | "Click here to buy now" | "Click here" button text | Accessibility rule |
| 25 | "at just ₹79" | Contradicts the price: **₹95** | Fact: price (100 g) |
| 26 | "ZERO CAVITIES. FOREVER. Buy it today!" | Capitals; unsupported claim; extra exclamation marks | Tone; SYS-CLAIM-001 |
| 27 | (end of script) | Required line "Results may vary. Use twice daily as directed." missing | Required-phrase rule (code) |
| 28 | Long sentences | Readability (sentences over 20 words) | Accessibility: readability |

Expect most of these. A few depend on which six rules retrieval picks for each paragraph, and on the
free AI model, so missing one or two is normal. **What must never happen:** a flag with no source,
or a quote that isn't in the script.

**Then try the creator actions:**
- **One fix round:** press *Accept fix* on the fixes you want (or *Choose all fixes*), reword
  any flag with *Edit wording*, then press *Apply*. All of them go into one new version, which is
  **not** checked by AI again; the fix buttons then disappear.
- *Dismiss* a flag: a reason is required.
- Add a comment.
- Open **Version history** to see the diff.
- *Submit to manager*: always possible; open high-severity flags go with it for the manager.
- To get a fresh AI check, paste a revised script under the content ("Upload revised script").

## Step 6. Creator: the PDF version
Upload `ad_script_with_errors.pdf`. The same issues should appear, now as **boxes on the page**.

## Step 7. Creator: the poster
Upload `poster_with_errors.png` and **leave the alt text empty**. The vision model should find:
- the red background and the stretched, recoloured "GLIMORA" logo;
- the full-length strip of paste;
- the Whitebay product being crossed out;
- white text on mint (contrast);
- the claims printed on it: No. 1, miracle, 99.9%, 9 out of 10, cure, Rs 79, "click here".

In code, Heimdall should also flag the missing alt text.

## Step 8. Creator: the control and the injection test
- `ad_script_clean.txt` should get **very few flags**. Each one you think is wrong is a precision
  miss; dismiss it with a reason.
- `injection_test.txt`: the "ignore all previous instructions" line must **not** work. Heimdall
  should still flag "best toothpaste in India" and "cures gum disease in one week".

## Step 9. Manager: decide
Sign in as **manager** and open the queue.
1. Open the submitted script. You see the unresolved flags and the creator's dismissal reasons.
2. **Send it back** with a comment. The creator sees the comment, uploads a revised script (which
   is checked again) and resubmits.
3. **Approve an exception** on one flag, with a reason. Upload the same wording again (as a new
   check): it should no longer be flagged.
4. **Approve.** Status becomes approved, and the history shows every step.

## Step 10. Insights and AI disclosure
- **Insights:** flags by category, the most-broken rules, time to approval and the send-back rate.
- **AI disclosure:** which AI services were called, what they received and how many times.
- **Guideline health:** a rule needs at least 5 flags before it can be marked "probably unclear".
  Dismiss the same rule's flags across several checks to see it.

## Optional: website check
Sign in as **admin** and open **Admin › Website check**. The Glimmora demo pages are already filled
in (https://aayush-tech2055.github.io/heimdall/glimmora/shop.html and about.html). Press
**Check website**. Expected proposals, each waiting for your decision:

| Fact | Approved sheet | Website |
|---|---|---|
| Active Shield 100 g price | ₹95 | **₹99** |
| Sensitive Relief relief time | 14 days | **10 days** |
| Cities | 400 | **450** |
| Charcoal Clean 100 g price | (none) | **₹110**, a new fact |

Unchanged facts (fluoride, Herbal Care price, founded 2009) should not be listed. Accept a change:
the fact keeps its code, so anything that cited it stays linked.
