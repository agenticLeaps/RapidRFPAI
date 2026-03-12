"""
AWS S3 utility functions for file operations.
Replaces Google Cloud Storage functions.
"""

import boto3
import os
from botocore.exceptions import ClientError
from typing import Optional, Tuple
import tempfile


def get_s3_client():
    """
    Initialize S3 client with credentials from environment.

    Environment variables required:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - AWS_REGION (optional, defaults to us-east-1)
    """
    return boto3.client(
        's3',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )


def get_bucket_name() -> str:
    """Get the S3 bucket name from environment."""
    return os.getenv('AWS_S3_BUCKET', 'rapidrfp-dev-bucket')


def parse_s3_url(s3_url: str) -> Tuple[str, str]:
    """
    Parse an S3 URL and extract bucket and key.

    Supports formats:
    - s3://bucket-name/key/path
    - https://bucket-name.s3.region.amazonaws.com/key/path
    - https://s3.region.amazonaws.com/bucket-name/key/path

    For legacy gs:// URLs, uses the default bucket.

    Returns:
        Tuple of (bucket, key)
    """
    if s3_url.startswith('s3://'):
        path = s3_url.replace('s3://', '')
        parts = path.split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        return bucket, key

    # Handle legacy gs:// URLs - use default bucket
    if s3_url.startswith('gs://'):
        path = s3_url.replace('gs://', '')
        parts = path.split('/', 1)
        # Ignore the GCS bucket name, use S3 bucket from env
        key = parts[1] if len(parts) > 1 else parts[0]
        return get_bucket_name(), key

    # Handle HTTPS S3 URLs
    if '.s3.' in s3_url and '.amazonaws.com' in s3_url:
        from urllib.parse import urlparse
        parsed = urlparse(s3_url)
        hostname = parsed.hostname
        bucket = hostname.split('.s3.')[0]
        key = parsed.path.lstrip('/')
        return bucket, key

    if s3_url.startswith('https://s3.') and '.amazonaws.com' in s3_url:
        from urllib.parse import urlparse
        parsed = urlparse(s3_url)
        path_parts = parsed.path.lstrip('/').split('/', 1)
        bucket = path_parts[0]
        key = path_parts[1] if len(path_parts) > 1 else ''
        return bucket, key

    raise ValueError(f"Invalid S3 URL format: {s3_url}")


def download_file_from_s3(s3_url: str) -> bytes:
    """
    Download file from S3 URL and return bytes.

    Args:
        s3_url: S3 URL in format s3://bucket/key or https://...

    Returns:
        File contents as bytes
    """
    bucket, key = parse_s3_url(s3_url)
    s3_client = get_s3_client()

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read()
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'NoSuchKey':
            raise FileNotFoundError(f"File not found in S3: {s3_url}")
        raise


def download_file_to_path(s3_url: str, local_path: str) -> str:
    """
    Download file from S3 to a local path.

    Args:
        s3_url: S3 URL in format s3://bucket/key
        local_path: Local file path to save to

    Returns:
        Local file path
    """
    bucket, key = parse_s3_url(s3_url)
    s3_client = get_s3_client()

    try:
        s3_client.download_file(bucket, key, local_path)
        return local_path
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404' or error_code == 'NoSuchKey':
            raise FileNotFoundError(f"File not found in S3: {s3_url}")
        raise


def download_file_from_s3_to_temp(s3_url: str, temp_dir: Optional[str] = None) -> Tuple[str, str]:
    """
    Download file from S3 to a temporary directory.

    Args:
        s3_url: S3 URL in format s3://bucket/key or gs://bucket/key (legacy)
        temp_dir: Optional temporary directory path

    Returns:
        Tuple of (local_file_path, filename)
    """
    bucket, key = parse_s3_url(s3_url)
    filename = key.split('/')[-1] if '/' in key else key

    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()

    local_path = os.path.join(temp_dir, filename)
    download_file_to_path(s3_url, local_path)

    return local_path, filename


def upload_file_to_s3(local_path: str, s3_key: str, content_type: Optional[str] = None) -> str:
    """
    Upload a local file to S3.

    Args:
        local_path: Path to local file
        s3_key: S3 object key (path within bucket)
        content_type: Optional content type

    Returns:
        S3 URL of uploaded file
    """
    bucket = get_bucket_name()
    s3_client = get_s3_client()

    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type

    s3_client.upload_file(local_path, bucket, s3_key, ExtraArgs=extra_args if extra_args else None)

    return f"s3://{bucket}/{s3_key}"


def upload_bytes_to_s3(data: bytes, s3_key: str, content_type: Optional[str] = None) -> str:
    """
    Upload bytes data to S3.

    Args:
        data: Bytes data to upload
        s3_key: S3 object key (path within bucket)
        content_type: Optional content type

    Returns:
        S3 URL of uploaded file
    """
    bucket = get_bucket_name()
    s3_client = get_s3_client()

    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type

    s3_client.put_object(Bucket=bucket, Key=s3_key, Body=data, **extra_args)

    return f"s3://{bucket}/{s3_key}"


def file_exists_in_s3(s3_url: str) -> bool:
    """
    Check if a file exists in S3.

    Args:
        s3_url: S3 URL to check

    Returns:
        True if file exists, False otherwise
    """
    bucket, key = parse_s3_url(s3_url)
    s3_client = get_s3_client()

    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == '404':
            return False
        raise


def generate_presigned_url(s3_url: str, expiration: int = 3600) -> str:
    """
    Generate a presigned URL for downloading a file.

    Args:
        s3_url: S3 URL of the file
        expiration: URL expiration time in seconds (default 1 hour)

    Returns:
        Presigned URL string
    """
    bucket, key = parse_s3_url(s3_url)
    s3_client = get_s3_client()

    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': key},
        ExpiresIn=expiration
    )


def delete_file_from_s3(s3_url: str) -> bool:
    """
    Delete a file from S3.

    Args:
        s3_url: S3 URL of the file to delete

    Returns:
        True if deleted successfully
    """
    bucket, key = parse_s3_url(s3_url)
    s3_client = get_s3_client()

    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False
