"""S3 artifact upload for model bundles."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def upload_bundle_dir(local_dir: Path, *, bucket: str | None = None, prefix: str = "") -> str:
    """Upload bundle directory to S3; returns s3 URI."""
    bucket = bucket or os.environ.get("MODEL_S3_BUCKET")
    if not bucket:
        raise RuntimeError("MODEL_S3_BUCKET not set")

    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 required for S3 upload: pip install boto3") from exc

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    model_key = local_dir.parent.name
    version = local_dir.name
    base_prefix = prefix or os.environ.get("MODEL_S3_PREFIX", "gravity-models")
    remote_prefix = f"{base_prefix}/{model_key}/{version}"

    for path in local_dir.rglob("*"):
        if path.is_file():
            key = f"{remote_prefix}/{path.relative_to(local_dir).as_posix()}"
            s3.upload_file(str(path), bucket, key)
            logger.info("Uploaded s3://%s/%s", bucket, key)

    uri = f"s3://{bucket}/{remote_prefix}/"
    logger.info("Bundle uploaded to %s", uri)
    return uri


def sync_bundles_from_s3(local_root: Path, *, bucket: str | None = None) -> int:
    """Download all bundles under prefix to local MODEL_BUNDLE_ROOT."""
    bucket = bucket or os.environ.get("MODEL_S3_BUCKET")
    if not bucket:
        raise RuntimeError("MODEL_S3_BUCKET not set")
    import boto3

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    prefix = os.environ.get("MODEL_S3_PREFIX", "gravity-models")
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    local_root.mkdir(parents=True, exist_ok=True)
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            rel = key[len(prefix) :].lstrip("/")
            dest = local_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(dest))
            count += 1
    logger.info("Synced %d files to %s", count, local_root)
    return count
