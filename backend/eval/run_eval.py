"""Run every test item through the review engine and score it (task 6.9).

    cd backend
    .venv/bin/python -m eval.run_eval                     # both brands, all items
    .venv/bin/python -m eval.run_eval --brand acmelearn --limit 5

Uses separate brands (`eval-<brand>`) so demo data stays clean. On first use for a brand it
extracts the guideline, maps the answer key's rule keys to the extracted rule codes, approves
every rule except the ones listed in the key's `reject`, and imports and approves the facts.
Writes docs/eval/<date>.md. Model answers are cached, so re-runs are cheap.
"""

import argparse
import json
import time
from collections import Counter
from datetime import date
from pathlib import Path

import psycopg

from app.config import get_settings
from app.db import get_pool
from app.llm import get_llm_client
from app.processing.documents import parse_pdf
from app.rag.embeddings import get_embedder
from app.rag.extraction import extract_rules
from app.rag.facts_store import create_facts, list_facts, parse_facts_csv
from app.rag.rules_store import list_rules, next_rule_number, set_rule_status, store_rules
from app.review.claims import CLAIM_POLICY_ID
from app.review.orchestrator import load_brand_context, review_text
from eval.scoring import (
    ActualFlag,
    ExpectedFlag,
    ItemScore,
    Totals,
    evidence_overlaps,
    map_rule_keys,
    score_item,
    totals,
)

ROOT = Path(__file__).resolve().parents[2]
TEST_DATA = ROOT / "test-data"
REPORT_DIR = ROOT / "docs" / "eval"


def setup_brand(
    conn: psycopg.Connection,
    slug: str,
    key_brand: dict,
    today: date,
    *,
    target_slug: str | None = None,
    target_name: str | None = None,
) -> tuple:  # (brand_id, mapping, rules)
    """Prepare a brand from the test data: by default the separate `eval-<slug>` brand;
    `target_slug` prepares an existing brand instead (the demo brand)."""
    brand_id = conn.execute(
        "insert into public.brands (name, slug) values (%s, %s) on conflict (slug) do update "
        "set name = excluded.name returning id",
        (target_name or f"{key_brand['name']} (eval)", target_slug or f"eval-{slug}"),
    ).fetchone()[0]
    conn.commit()  # AI calls are logged from other connections and reference the brand
    rules = list_rules(conn, brand_id)
    if not rules:
        pdf = (TEST_DATA / "brands" / slug / "guidelines.pdf").read_bytes()
        drafts = extract_rules(
            parse_pdf(pdf), source_doc="guidelines.pdf", client=get_llm_client(),
            first_number=next_rule_number(conn, brand_id), brand_id=brand_id,
        )  # fmt: skip
        rules = store_rules(conn, brand_id, drafts, get_embedder())
    mapping = map_rule_keys(
        key_brand["rules"], {r.rule_code: f"{r.text} {' '.join(r.terms)}" for r in rules}
    )
    reject = {mapping[k] for k in key_brand["reject"]}
    approve = [r.rule_code for r in rules if r.rule_code not in reject]
    set_rule_status(conn, brand_id, approve, "approved", None)
    if reject:
        set_rule_status(conn, brand_id, sorted(reject), "rejected", None)
    if not list_facts(conn, brand_id, today):
        facts, errors = parse_facts_csv((TEST_DATA / "brands" / slug / "facts.csv").read_text())
        assert not errors, errors
        create_facts(conn, brand_id, facts, get_embedder(), status="approved", actor_id=None,
                     today=today)  # fmt: skip
    conn.commit()
    return brand_id, mapping, list_rules(conn, brand_id)


def resolve(source: str, mapping: dict[str, str]) -> str:
    return mapping.get(source, source)


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def write_report(path: Path, runs: dict, today: date, started: float) -> None:
    settings = get_settings()
    all_scores = [s for r in runs.values() for s in r["scores"]]
    overall, by_cat = totals(all_scores)
    ret_hit = sum(r["retrieval"][0] for r in runs.values())
    ret_all = sum(r["retrieval"][1] for r in runs.values())
    invalid = sum(r["invalid"] for r in runs.values())
    seconds = [t for r in runs.values() for t in r["seconds"]]
    per_brand = ", ".join(f"{b}: {len(r['scores'])}" for b, r in runs.items())
    lines = [
        f"# Evaluation report, {today.isoformat()}",
        "",
        f"Items: {len(all_scores)} ({per_brand})"
        f" · planted errors: {overall.expected} · flags raised: {overall.flags}",
        f"Models: {', '.join(settings.provider_order)} "
        f"(Gemini `{settings.gemini_model}`, Groq `{settings.groq_model}`, "
        f"OpenRouter `{settings.openrouter_model}`); embeddings `{settings.gemini_embedding_model}`.",
        f"Average review time per item: {sum(seconds) / max(1, len(seconds)):.1f} s "
        f"(total run {time.time() - started:.0f} s, cached answers included).",
        "",
        "## Summary",
        "",
        "| Metric | Value | Target (R2 / R3) |",
        "|---|---|---|",
        f"| Planted errors caught (recall) | {pct(overall.recall)} ({overall.caught}/{overall.expected}) | ≥ 75% / ≥ 85% |",
        f"| … caught with the expected source | {pct(overall.source_recall)} ({overall.caught_with_source}/{overall.expected}) | |",
        f"| Flag precision | {pct(overall.precision)} ({overall.correct}/{overall.flags}) | ≥ 75% / ≥ 85% |",
        f"| Retrieval recall (expected rule retrieved for its unit) | {pct(ret_hit / ret_all) if ret_all else 'n/a'} ({ret_hit}/{ret_all}) | |",
        f"| Flags without a valid source | {invalid} | 0 |",
        "",
        "## By category",
        "",
        "| Category | Recall | Caught / expected | Precision | Correct / flags |",
        "|---|---|---|---|---|",
    ]
    for cat, t in by_cat.items():
        lines.append(
            f"| {cat} | {pct(t.recall) if t.expected else '–'} | {t.caught}/{t.expected} | "
            f"{pct(t.precision) if t.flags else '–'} | {t.correct}/{t.flags} |"
        )
    for brand, r in runs.items():
        t: Totals = totals(r["scores"])[0]
        lines += ["", f"## {brand}", "",
                  f"Recall {pct(t.recall)}, precision {pct(t.precision)}. Dropped by validation: "
                  + (", ".join(f"{k} {v}" for k, v in r["dropped"].most_common()) or "none") + ".",
                  "", "### Missed planted errors", ""]  # fmt: skip
        missed = [
            (s.item_id, e)
            for s in r["scores"]
            for e, c in zip(s.expected, s.caught, strict=True)
            if not c
        ]
        lines += [f"- `{i}` {e.error}: “{e.evidence or '(missing phrase)'}” ({'/'.join(sorted(e.sources))})"
                  for i, e in missed] or ["- none"]  # fmt: skip
        lines += ["", "### Flags that match no planted error", ""]
        fps = [
            (s.item_id, a)
            for s in r["scores"]
            for a, ok in zip(s.actual, s.correct, strict=True)
            if not ok
        ]
        lines += [f"- `{i}` {a.source_id} ({a.category}, {a.layer}): “{a.evidence or '(missing phrase)'}”"
                  for i, a in fps] or ["- none"]  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Heimdall against the answer key.")
    parser.add_argument("--brand", action="append", help="Brand slug (repeatable); default all")
    parser.add_argument("--limit", type=int, help="Only the first N items per brand")
    parser.add_argument("--items", help="Comma-separated item ids")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    started = time.time()
    key = json.loads((TEST_DATA / "answer_key.json").read_text())
    brands = args.brand or list(key["brands"])
    wanted = set(args.items.split(",")) if args.items else None
    pool, client, embedder = get_pool(), get_llm_client(), get_embedder()
    runs: dict = {}
    for slug in brands:
        with pool.connection() as conn:
            brand_id, mapping, rules = setup_brand(conn, slug, key["brands"][slug], args.today)
            ctx = load_brand_context(conn, brand_id)
            valid = {r.rule_code for r in rules if r.status == "approved"}
            valid |= {
                f.fact_code for f in list_facts(conn, brand_id, args.today, status="approved")
            }
            valid.add(CLAIM_POLICY_ID)
        semantic = {r.rule_code for r in rules if r.check_type == "semantic"}
        items = json.loads((TEST_DATA / "brands" / slug / "content.json").read_text())
        items = [i for i in items if wanted is None or i["id"] in wanted][: args.limit]
        scores: list[ItemScore] = []
        retrieval = [0, 0]
        invalid = 0
        dropped: Counter = Counter()
        seconds: list[float] = []
        for n, item in enumerate(items, 1):
            outcome = review_text(item["text"], ctx, pool=pool, client=client, embedder=embedder,
                                  today=args.today)  # fmt: skip
            seconds.append(outcome.seconds)
            dropped.update(reason for _, reason in outcome.dropped)
            expected = [
                ExpectedFlag(e["evidence"], {resolve(s, mapping) for s in [e["source"], *e["alt_sources"]]},
                             e["category"], e["source_type"], e["error"])
                for e in key["items"][item["id"]]["expected"]
            ]  # fmt: skip
            actual = [ActualFlag(f.evidence, f.source_id, f.category, f.layer, f.unit_id)
                      for f in outcome.flags]  # fmt: skip
            invalid += sum(f.source_id not in valid for f in outcome.flags)
            for e in expected:
                code = next(iter(e.sources & semantic), None)
                if e.source_type == "rule" and code and e.evidence:
                    unit = next(
                        (u for u in outcome.units if evidence_overlaps(e.evidence, u.text)), None
                    )
                    if unit:
                        retrieval[1] += 1
                        retrieval[0] += code in outcome.retrieved.get(unit.unit_id, [])
            s = score_item(item["id"], expected, actual, item["text"])
            scores.append(s)
            print(f"[{slug} {n}/{len(items)}] {item['id']}: {sum(s.caught)}/{len(expected)} caught, "
                  f"{sum(s.correct)}/{len(actual)} flags correct ({outcome.seconds:.1f}s)", flush=True)  # fmt: skip
        runs[slug] = {"scores": scores, "retrieval": retrieval, "invalid": invalid,
                      "dropped": dropped, "seconds": seconds}  # fmt: skip

    out = args.out or REPORT_DIR / f"{args.today.isoformat()}.md"
    write_report(out, runs, args.today, started)
    overall, _ = totals([s for r in runs.values() for s in r["scores"]])
    print(f"\nRecall {pct(overall.recall)} · precision {pct(overall.precision)} · "
          f"invalid sources {sum(r['invalid'] for r in runs.values())} → {out}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
