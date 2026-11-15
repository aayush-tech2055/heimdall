"""Original uploads (PDFs, images) in a private Supabase Storage bucket.

The backend reads and writes with the service role key and serves files to the frontend
itself, so the frontend still talks only to the FastAPI API.
"""

from functools import lru_cache

import httpx

from app.config import get_settings

BUCKET = "content"


class StorageError(RuntimeError):
    pass


class Storage:
    def __init__(
        self, supabase_url: str, service_key: str, client: httpx.Client | None = None
    ) -> None:
        if not supabase_url or not service_key:
            raise StorageError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are needed for uploads")
        self._client = client or httpx.Client(timeout=60)
        self._base = f"{supabase_url.rstrip('/')}/storage/v1"
        self._headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
        self._bucket_ready = False

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        r = self._client.get(f"{self._base}/bucket/{BUCKET}", headers=self._headers)
        if r.status_code in (400, 404):
            r = self._client.post(
                f"{self._base}/bucket", headers=self._headers,
                json={"id": BUCKET, "name": BUCKET, "public": False,
                      "file_size_limit": 20 * 1024 * 1024},
            )  # fmt: skip
            if r.is_error and "already exists" not in r.text:
                raise StorageError(f"could not create the storage bucket: {r.status_code} {r.text}")
        elif r.is_error:
            raise StorageError(f"storage unavailable: {r.status_code}")
        self._bucket_ready = True

    def upload(self, path: str, data: bytes, content_type: str) -> str:
        self._ensure_bucket()
        r = self._client.post(
            f"{self._base}/object/{BUCKET}/{path}",
            headers=self._headers | {"Content-Type": content_type, "x-upsert": "true"},
            content=data,
        )
        if r.is_error:
            raise StorageError(f"upload failed: {r.status_code} {r.text[:200]}")
        return path

    def download(self, path: str) -> bytes:
        r = self._client.get(f"{self._base}/object/{BUCKET}/{path}", headers=self._headers)
        if r.is_error:
            raise StorageError(f"download failed: {r.status_code}")
        return r.content


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    return Storage(s.supabase_url, s.supabase_service_role_key)
