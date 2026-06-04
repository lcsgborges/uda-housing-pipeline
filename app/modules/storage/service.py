from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings


@dataclass
class StoredObject:
    uri: str
    size_bytes: int


class ObjectStorage:
    def store(self, *, key: str, content: bytes) -> StoredObject:
        raise NotImplementedError

    def read(self, uri: str) -> bytes:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorage):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store(self, *, key: str, content: bytes) -> StoredObject:
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StoredObject(uri=f"file://{path}", size_bytes=len(content))

    def read(self, uri: str) -> bytes:
        if uri.startswith("file://"):
            return Path(uri.removeprefix("file://")).read_bytes()
        return Path(uri).read_bytes()


class RustFSS3ObjectStorage(ObjectStorage):
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ):
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=_build_endpoint_url(endpoint=endpoint, secure=secure),
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            self.client.create_bucket(Bucket=self.bucket)

    def store(self, *, key: str, content: bytes) -> StoredObject:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=_guess_content_type(key),
        )
        return StoredObject(
            uri=f"s3://{self.bucket}/{key}",
            size_bytes=len(content),
        )

    def read(self, uri: str) -> bytes:
        bucket, key = _parse_s3_uri(uri)
        response = self.client.get_object(Bucket=bucket, Key=key)
        try:
            return response["Body"].read()
        finally:
            response["Body"].close()


def build_object_storage() -> ObjectStorage:
    settings = get_settings()
    backend = settings.storage_backend.lower()
    if backend == "rustfs":
        return RustFSS3ObjectStorage(
            endpoint=settings.rustfs_endpoint,
            access_key=settings.rustfs_access_key,
            secret_key=settings.rustfs_secret_key,
            bucket=settings.rustfs_bucket,
            secure=settings.rustfs_secure,
        )
    return LocalObjectStorage(settings.documents_dir)


def _build_endpoint_url(*, endpoint: str, secure: bool) -> str:
    if endpoint.startswith(("http://", "https://")):
        return endpoint
    scheme = "https" if secure else "http"
    return f"{scheme}://{endpoint}"


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    # Formats: s3://bucket/path.pdf or rustfs://bucket/path.pdf.
    if "://" not in uri:
        raise ValueError(f"URI de storage inválida: {uri}")
    scheme, without_scheme = uri.split("://", 1)
    if scheme not in {"s3", "rustfs"}:
        raise ValueError(f"Scheme de storage não suportado: {scheme}")
    parts = without_scheme.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"URI de storage inválida: {uri}")
    return parts[0], parts[1]


def _guess_content_type(key: str) -> str:
    lowered = key.lower()
    if lowered.endswith(".pdf"):
        return "application/pdf"
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        return "image/jpeg"
    return "application/octet-stream"
