"""Guideline uploads in the background.

The upload request only reads and checks the files (so a bad file is refused at once), records a
`guideline_jobs` row and returns. The job then extracts each file's rules in turn, stores them as
`pending` and commits after every file, so rules appear on the Guidelines screen as each file
finishes; the admin can meanwhile work elsewhere (for example import facts). The guideline is
verified once, after the last file.

Jobs of one brand run one at a time (rule codes are numbered per brand), using a lock in this
process; the backend runs as a single process (as the rate limiter already assumes).
"""

import json
import threading
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app.llm.client import LLMClient
from app.processing.documents import PageText
from app.rag.embeddings import Embedder
from app.rag.extraction import extract_rules
from app.rag.rules_store import next_rule_number, store_rules
from app.rag.verification import verify_guidelines

_brand_locks: defaultdict[UUID, threading.Lock] = defaultdict(threading.Lock)


@dataclass(frozen=True)
class GuidelineDoc:
    name: str
    pages: list[PageText]


def create_job(
    conn: psycopg.Connection, brand_id: UUID, docs: list[GuidelineDoc], actor_id: UUID | None
) -> dict:
    """Record a queued job; the caller commits before the background work starts."""
    files = [{"name": d.name, "pages": len(d.pages)} for d in docs]
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            "insert into public.guideline_jobs (brand_id, files, created_by) values (%s, %s, %s) "
            "returning *",
            (brand_id, json.dumps(files), actor_id),
        ).fetchone()


def list_jobs(conn: psycopg.Connection, brand_id: UUID, limit: int = 10) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            "select * from public.guideline_jobs where brand_id = %s "
            "order by created_at desc limit %s",
            (brand_id, limit),
        ).fetchall()


def _set(
    conn: psycopg.Connection, job_id: UUID, *, finished: bool = False, **fields: object
) -> None:
    sets = [f"{k} = %s" for k in fields] + (["finished_at = now()"] if finished else [])
    conn.execute(
        f"update public.guideline_jobs set {', '.join(sets)} where id = %s",
        [*fields.values(), job_id],
    )
    conn.commit()


def run_job(
    conn: psycopg.Connection,
    job_id: UUID,
    brand_id: UUID,
    docs: list[GuidelineDoc],
    *,
    client: LLMClient,
    embedder: Embedder,
    actor_id: UUID | None = None,
) -> None:
    """Extract and store each file's rules (committing after each), then verify once."""
    with _brand_locks[brand_id]:
        _set(conn, job_id, status="running")
        added = 0
        try:
            for done, doc in enumerate(docs, start=1):
                drafts = extract_rules(
                    doc.pages, source_doc=doc.name, client=client,
                    first_number=next_rule_number(conn, brand_id), brand_id=brand_id,
                )  # fmt: skip
                added += len(store_rules(conn, brand_id, drafts, embedder))
                conn.commit()
                _set(conn, job_id, files_done=done, rules_added=added)
            source = docs[0].name if len(docs) == 1 else f"{len(docs)} files"
            verify_guidelines(conn, brand_id, client, source_doc=source, actor_id=actor_id)
            conn.commit()
            _set(conn, job_id, status="done", finished=True)
        except Exception as exc:  # noqa: BLE001 - record any failure on the job, keep earlier files
            conn.rollback()
            message = str(exc) or exc.__class__.__name__
            _set(conn, job_id, status="failed", error=message[:500], finished=True)
