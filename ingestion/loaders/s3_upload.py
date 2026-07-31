import os
from urllib.parse import urlparse

import boto3


def _bucket() -> str:
    return urlparse(os.environ["WAREHOUSE"]).netloc


def upload_raw(local_path: str, relative_key: str) -> None:
    """Upload a local data file to s3://<warehouse-bucket>/raw/<relative_key>."""
    bucket = _bucket()
    key = f"raw/{relative_key.lstrip('/')}"
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    s3.upload_file(local_path, bucket, key)
    print(f"Uploaded {local_path} -> s3://{bucket}/{key}")
