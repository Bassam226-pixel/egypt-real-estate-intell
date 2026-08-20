import logging
import os
from urllib.parse import urlparse

import boto3

logger = logging.getLogger(__name__)


def _bucket() -> str:
    return urlparse(os.environ["WAREHOUSE"]).netloc


def upload_raw(local_path: str, relative_key: str) -> None:
    """Upload a local data file to s3://<warehouse-bucket>/raw/<relative_key>.

    Mirrors spark_jobs/common/io.py's raw_path(), so anything uploaded here is
    readable via s3a://<bucket>/raw/<relative_key> from the Spark bronze layer.
    """
    bucket = _bucket()
    key = f"raw/{relative_key.lstrip('/')}"
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    try:
        s3.upload_file(local_path, bucket, key)
    except Exception:
        logger.exception("Failed to upload %s -> s3://%s/%s", local_path, bucket, key)
        raise
    print(f"Uploaded {local_path} -> s3://{bucket}/{key}")
