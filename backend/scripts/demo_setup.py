"""Give the seeded demo brand a ready knowledge base (for local testing and demo mode).

    cd backend && .venv/bin/python -m scripts.demo_setup

For the AcmeLearn demo brand (from db/seed.json): extracts its guideline if it has no rules,
approves every rule except the planted vague, duplicate and contradicting ones (which it
rejects, as an admin would after reading the verification report), and imports and approves
the facts sheet. Safe to re-run.
"""

import json
from datetime import date

from app.db import get_pool
from app.rag.facts_store import list_facts
from eval.run_eval import TEST_DATA, setup_brand
from scripts.seed import DEFAULT_CONFIG, load_config


def main() -> int:
    config = load_config(DEFAULT_CONFIG)
    key = json.loads((TEST_DATA / "answer_key.json").read_text())
    slug = config.brand.slug
    if slug not in key["brands"]:
        print(f"No test data for brand {slug!r}")
        return 1
    today = date.today()
    with get_pool().connection() as conn:
        brand_id, _, rules = setup_brand(
            conn, slug, key["brands"][slug], today, target_slug=slug, target_name=config.brand.name
        )
        facts = list_facts(conn, brand_id, today)
    approved = [r.rule_code for r in rules if r.status == "approved"]
    rejected = [r.rule_code for r in rules if r.status == "rejected"]
    print(f"{config.brand.name}: {len(approved)} rules approved, {len(rejected)} rejected "
          f"({', '.join(rejected)}), {len(facts)} facts approved.")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
