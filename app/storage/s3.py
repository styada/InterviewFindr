"""Object storage wrapper.

Plan 1 ships a local-filesystem implementation that maps
`minio://<bucket>/<key>` style keys to a directory under `var/storage/`. This
keeps tests and the dev environment working without a running MinIO service.
A future task will swap in the real `minio` SDK behind the same API.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_ROOT = Path(os.environ.get("INTERVIEWFINDR_STORAGE_ROOT", "var/storage"))


def _resolve(key: str) -> Path:
    clean = key.lstrip("/")
    path = (_ROOT / clean).resolve()
    if not path.is_relative_to(_ROOT.resolve()):
        raise ValueError(f"storage key escapes root: {key!r}")
    return path


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Persist bytes at `key`; return the canonical `key` for storage in the DB."""
    path = _resolve(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    log.debug("put_object %s (%d bytes, %s)", key, len(data), content_type)
    return key


def get_object(key: str) -> bytes:
    """Return the bytes stored at `key`."""
    return _resolve(key).read_bytes()


def object_exists(key: str) -> bool:
    return _resolve(key).exists()


def ensure_bucket(_bucket: str) -> None:
    _ROOT.mkdir(parents=True, exist_ok=True)


def local_url(key: str) -> str:
    """Return a relative URL the FastAPI app can serve (used by the apply kit)."""
    return f"/storage/{key.lstrip('/')}"
