"""Supabase Storage client (mock transport, no network)."""

import httpx
import pytest

from app.storage import Storage, StorageError


def storage(handler) -> Storage:
    return Storage(
        "https://p.supabase.co", "svc", httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_creates_the_bucket_once_then_uploads_and_downloads():
    calls = []

    def handler(r: httpx.Request) -> httpx.Response:
        calls.append((r.method, r.url.path))
        assert r.headers["authorization"] == "Bearer svc"
        if r.url.path == "/storage/v1/bucket/content":
            return httpx.Response(404, json={"error": "not found"})
        if r.method == "GET":
            return httpx.Response(200, content=b"%PDF-data")
        return httpx.Response(200, json={"Key": "content/x"})

    s = storage(handler)
    s.upload("brand/v1/a.pdf", b"%PDF", "application/pdf")
    s.upload("brand/v2/a.pdf", b"%PDF", "application/pdf")
    assert s.download("brand/v1/a.pdf") == b"%PDF-data"
    assert calls == [
        ("GET", "/storage/v1/bucket/content"),
        ("POST", "/storage/v1/bucket"),
        ("POST", "/storage/v1/object/content/brand/v1/a.pdf"),
        ("POST", "/storage/v1/object/content/brand/v2/a.pdf"),
        ("GET", "/storage/v1/object/content/brand/v1/a.pdf"),
    ]


def test_errors_are_clear():
    with pytest.raises(StorageError, match="needed"):
        Storage("", "")
    s = storage(lambda r: httpx.Response(200 if "bucket" in r.url.path else 500, text="boom"))
    with pytest.raises(StorageError, match="upload failed: 500"):
        s.upload("x", b"1", "text/plain")
