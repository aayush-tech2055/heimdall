"""Demo mode (task 10.2): pre-run the demo content so a live demo answers from the cache,
and check that the fallback providers work without Gemini.

    cd backend
    .venv/bin/python -m scripts.demo_prerun                  # warm the cache for the demo brand
    .venv/bin/python -m scripts.demo_prerun --fallback-check # review one item with Gemini off

Warming runs every test item of the demo brand through the full pipeline (no content rows are
created). The fallback check uses a fresh, in-memory model cache and only Groq and OpenRouter
for chat; embeddings still come from Gemini's cache (they have no fallback by design).
"""

import argparse
import json
import time
from datetime import date

from app.config import get_settings
from app.db import get_pool
from app.llm import get_llm_client
from app.llm.cache import SQLiteCache
from app.llm.call_log import MemoryCallLogger
from app.llm.client import LLMClient
from app.llm.providers import build_providers
from app.rag.embeddings import get_embedder
from app.review.orchestrator import load_brand_context, review_text
from eval.run_eval import TEST_DATA
from scripts.seed import DEFAULT_CONFIG, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fallback-check", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)

    config = load_config(DEFAULT_CONFIG)
    items = json.loads((TEST_DATA / "brands" / config.brand.slug / "content.json").read_text())
    pool = get_pool()
    with pool.connection() as conn:
        brand_id = conn.execute(
            "select id from public.brands where slug = %s", (config.brand.slug,)
        ).fetchone()[0]
        ctx = load_brand_context(conn, brand_id)
    if not ctx.rules:
        print("The demo brand has no approved rules: run python -m scripts.demo_setup first")
        return 1

    if args.fallback_check:
        settings = get_settings().model_copy(update={"llm_provider_order": "groq,openrouter"})
        log = MemoryCallLogger()
        client = LLMClient(build_providers(settings), SQLiteCache(":memory:"), log)
        item = (
            next(i for i in items if i["id"] == "acme-03")
            if any(i["id"] == "acme-03" for i in items)
            else items[0]
        )
        outcome = review_text(item["text"], ctx, pool=pool, client=client, embedder=get_embedder(),
                              today=date.today())  # fmt: skip
        used = sorted({(r.provider, r.ok) for r in log.records})
        print(f"Fallback check on {item['id']} without Gemini: {len(outcome.flags)} flags "
              f"in {outcome.seconds:.1f}s; calls by (provider, ok): {used}")  # fmt: skip
        for f in outcome.flags:
            print(f"  {f.source_id} {f.layer}: {f.evidence!r}")
        return 0 if any(p != "gemini" and ok for p, ok in used) else 1

    client, embedder = get_llm_client(), get_embedder()
    started = time.time()
    for n, item in enumerate(items[: args.limit], 1):
        outcome = review_text(item["text"], ctx, pool=pool, client=client, embedder=embedder,
                              today=date.today())  # fmt: skip
        print(f"[{n}/{len(items[: args.limit])}] {item['id']}: {len(outcome.flags)} flags, "
              f"{outcome.seconds:.1f}s", flush=True)  # fmt: skip
    print(f"Cache warm for {config.brand.name} in {time.time() - started:.0f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
