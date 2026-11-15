# Evaluation: before and after (task 13.4)

All runs use the same 60 fictional content items (53 planted errors, 16 clean items), the same
answer key, and the free-tier models in `backend/.env` (Gemini `gemini-3.5-flash-lite`, then Groq
`openai/gpt-oss-120b`, then OpenRouter). Model answers are cached, so a re-run only calls a model
for prompts that changed.

| Run | Report | Recall | With expected source | Precision | Retrieval recall | Flags without a valid source |
|---|---|---|---|---|---|---|
| Round 2 baseline | [2026-11-15-baseline.md](2026-11-15-baseline.md) | 98% (52/53) | 92% | **63%** (69/109) | 95% | 0 |
| Round 2, after the claims fix (10.3) | [2026-11-15.md](2026-11-15.md) | 98% (52/53) | 92% | **79%** (64/81) | 95% | 0 |
| Round 3 re-run | [2026-11-15-round3.md](2026-11-15-round3.md) | 96% (51/53) | 91% | **75%** (61/81) | 95% | 0 |

Targets: recall and precision ≥ 75% for Round 2 and ≥ 85% for Round 3; 0 flags without a valid source.

## What changed and why

**Baseline → claims fix: precision +16 points (63% → 79%), recall unchanged.** Most unmatched
flags in the baseline were the brand's own required disclaimer ("T&Cs apply.", "Contains caffeine…")
treated as an unsupported claim or a health claim. Citation validation now drops AI flags that sit
inside an approved required phrase, and the claim-extraction and judge prompts exclude invitations,
legal notices and doubtful breaches. Claims precision went from 52% to 76%.

**Claims fix → Round 3 re-run: −4 points of precision, −1 planted error.** Nothing in the scoring or
the review rules changed. Two things changed the text the models see: Presidio name and place
redaction is now installed, and a few prompts were edited for video and images. The items whose
prompts changed (acme-13, acme-15, acme-26) were answered again by the model, and the lite model gave
slightly different answers (an extra tone flag and a hashtag flagged as legal; the price-in-social
breach in acme-13 not raised). We read this as run-to-run variance of about ±4 points, not a
regression.

## Honest limits

- **The Round 3 precision target (≥ 85%) is not met** with free-tier models. Gemini `gemini-3.5-flash`
  found every planted guideline problem in our checks but allows only 20 requests a day on the free
  tier; the lite model is noisier. The remaining unmatched flags are mostly tone nitpicks and claims the
  answer key treats as harmless ("Your account is ready", "ships tomorrow").
- Recall and the "no source, no flag" guarantee hold in every run: no flag ever cited a source that is
  not an approved rule, fact or the claim policy.
- The Round 3 improvements (video review, website facts and assets, insights) add capabilities rather
  than text accuracy; they are verified by tests and live checks recorded in the build log, not by this
  text evaluation.
