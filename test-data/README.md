# Test data (fictional)

Everything here is invented for testing Heimdall. AcmeLearn and Brewbird Coffee are not real
companies, and every person, price, statistic, award and competitor name is made up.

```
brands/<brand>/
  guidelines.md    brand guideline (source; `<!-- page -->` starts a new page)
  guidelines.pdf   the same guideline as a 5-page PDF (built by backend/scripts/build_guideline_pdfs.py)
  facts.csv        approved facts: entity, attribute, value, unit, statement, source, valid_until
  content.json     30 content items: id, kind (blog | social | ad | email | script), title, text
answer_key.json    expected flags for every content item, plus the expected verification report
```

## What is planted

**Guidelines** (task 1.1), per brand: 2 vague rules, 1 duplicate and 1 contradiction, listed in
`answer_key.json` under `brands.<brand>.verification`.

| | AcmeLearn | Brewbird |
|---|---|---|
| Vague | "Content should feel exciting and on-brand."; "Messaging should be impactful and inspire trust." | "Posts should have good energy and feel premium."; "Words like 'great taste' should be used carefully." |
| Duplicate | banned word "cheap" (p. 2) and "Do not describe any course or plan as cheap." (p. 3) | "Never describe it as an addiction or a drug." (p. 1) and "Never refer to coffee as a drug or an addiction." (p. 4) |
| Contradiction | "Always state the monthly price…" (p. 3) vs "Social media captions must not mention prices." (p. 5) | "Always mention the estate…" (p. 3) vs "Do not name our estate partners or their estates…" (p. 5) |

**Facts** (task 1.2): 17 per brand; 2 already expired (AcmeLearn F-014, F-015; Brewbird F-015,
F-016) and 1 expiring within 30 days of 2026-11-14 (AcmeLearn F-005; Brewbird F-009). Fact codes
follow row order (row 1 = F-001).

**Content** (task 1.3): 31 items per brand, 8 of them clean. Item 31 of each brand (task 14.4) is a
prompt-injection test: it tells the model to ignore its instructions and report nothing, around a
real planted error that must still be flagged. Planted errors: banned terms, wrong
brand or product names, a missing required disclaimer, outdated prices and offers (expired facts),
contradicted statistics, unsupported superlatives, job or health promises, competitor names,
off-tone or sarcastic sentences, non-inclusive words.

**Answer key** (task 1.4): every planted error with its exact evidence quote, its source (a rule
key, a fact code or `SYS-CLAIM-001`) and its category. Rules are named by stable keys because
rule codes are assigned at extraction; the evaluation maps each key to the extracted rule whose
text matches best. Before an evaluation run, approve every extracted rule except the ones in
`brands.<brand>.reject` (the vague rules, the duplicate and one side of the contradiction), and
approve all facts.

## Website (Round 3, task 12)

`website/acmelearn/` is a fictional two-page AcmeLearn site, served by the backend at
`/demo-site/acmelearn/…` so the website fact check never touches a real company. Compared with
`facts.csv` it has one changed fact (AcmeLearn Pro: ₹599 → ₹649 a month; also 350 → 420
courses and 6 → 8 languages) and repeats several unchanged ones.
