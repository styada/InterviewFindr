# AGENTS.md — `app/storage/`

## What lives here

Object-storage wrapper for MinIO (S3-compatible).
- `s3.py` — thin client: `put_object`, `get_object`, `presigned_url`, `bucket_exists`, `ensure_bucket`.

## Conventions

- The bucket name comes from settings (`MINIO_BUCKET`); the wrapper auto-creates it on first use when `APP_ENV != "production"`.
- All resume/cover-letter artifacts are addressed by `minio://<bucket>/<key>`; the path is stored in `TailoredArtifact.resume_pdf_path` etc.
- `presigned_url()` is used for the assisted-apply download links (24h expiry).
