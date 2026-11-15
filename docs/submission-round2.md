# Round 2 submission package

**Team Nobita&Avaneja** · Heimdall · *Nothing crosses unchecked.*

| Item | Where |
|---|---|
| Deployed demo | *To be added after deployment (task 10.1).* Until then it runs locally: see [Getting started](../README.md#getting-started); demo logins are in `db/seed.json` |
| Repository | https://github.com/aayush-tech2055/heimdall |
| Architecture | [README › Architecture](../README.md#architecture) and [Final report › How a review works](final-report.md#how-a-review-works) |
| APIs, models and datasets | below |
| Testing evidence | [evaluation reports](eval/) and [before/after comparison](eval/comparison.md), [performance](performance.md), [accessibility](accessibility.md), [security](security.md); user-testing notes *to be added (task 10.4)* |
| Each member's contribution | [`BUILD_LOG.md`](BUILD_LOG.md) |
| Setup | [README › Getting started](../README.md#getting-started) |

## APIs, models and datasets

| Kind | Name | Use |
|---|---|---|
| API | Google Gemini (`gemini-3.5-flash-lite`, `gemini-embedding-001`) | main model for text and images; embeddings |
| API | Groq (`openai/gpt-oss-120b`, `whisper-large-v3`) | fallback model; speech to text |
| API | OpenRouter (`nvidia/nemotron-3.5-super-vl:free`) | second fallback |
| Platform | Supabase | Postgres with pgvector, Auth, Storage |
| Dataset | Our own fictional test set (`test-data/`) | 2 brands, 10 guideline pages, 34 facts, 62 content items, answer key, fictional website |
| Libraries | see [README › AI and tool disclosure](../README.md#ai-and-tool-disclosure) | |

No real company, customer or personal data was used.

## The three Round 3 improvements (task 10.6)

1. **Short video review** with speech, on-screen text and frame checks, and flags on a timeline.
2. **Website fact import with admin approval**, plus an **asset library** of approved logos and text.
3. **Insights and guideline health**, with accuracy re-measured on the same test set.

All three are built; see [Final report › 3](final-report.md#3-the-three-round-3-improvements).
