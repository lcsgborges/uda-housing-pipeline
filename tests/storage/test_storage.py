import pytest
from botocore.exceptions import ClientError

from app.modules.storage import service as storage_service
from app.modules.storage.service import (
    LocalObjectStorage,
    ObjectStorage,
    RustFSS3ObjectStorage,
    _build_endpoint_url,
    _guess_content_type,
    _parse_s3_uri,
    build_object_storage,
)


@pytest.mark.parametrize("scheme", ["rustfs", "s3"])
def test_parse_s3_uri(scheme):
    bucket, key = _parse_s3_uri(f"{scheme}://uda-documents/mrv/doc.pdf")

    assert bucket == "uda-documents"
    assert key == "mrv/doc.pdf"


def test_parse_s3_uri_rejeita_scheme_invalido():
    with pytest.raises(ValueError):
        _parse_s3_uri("ftp://bucket/file.pdf")


def test_parse_s3_uri_rejeita_uri_sem_bucket_ou_key():
    with pytest.raises(ValueError):
        _parse_s3_uri("s3://bucket")

    with pytest.raises(ValueError):
        _parse_s3_uri("bucket/file.pdf")


def test_build_endpoint_url_para_rustfs_local_sem_tls():
    assert _build_endpoint_url(endpoint="rustfs:9000", secure=False) == "http://rustfs:9000"


def test_build_endpoint_url_preserva_url_com_scheme():
    assert _build_endpoint_url(endpoint="https://rustfs:9000", secure=False) == "https://rustfs:9000"
    assert _build_endpoint_url(endpoint="rustfs:9000", secure=True) == "https://rustfs:9000"


def test_guess_content_type_por_extensao():
    assert _guess_content_type("arquivo.pdf") == "application/pdf"
    assert _guess_content_type("imagem.png") == "image/png"
    assert _guess_content_type("foto.jpeg") == "image/jpeg"
    assert _guess_content_type("dados.bin") == "application/octet-stream"


def test_local_object_storage_grava_e_le(tmp_path):
    storage = LocalObjectStorage(tmp_path)

    stored = storage.store(key="mrv/doc.pdf", content=b"conteudo")

    assert stored.size_bytes == 8
    assert stored.uri.startswith("file://")
    assert storage.read(stored.uri) == b"conteudo"
    assert storage.read(stored.uri.removeprefix("file://")) == b"conteudo"


class _Body:
    def __init__(self, data: bytes):
        self.data = data
        self.closed = False

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        self.closed = True


class _FakeS3Client:
    def __init__(self, missing_bucket: bool = False):
        self.missing_bucket = missing_bucket
        self.created_bucket = None
        self.objects = {}
        self.last_body = None

    def head_bucket(self, Bucket):
        if self.missing_bucket:
            raise ClientError({"Error": {"Code": "NoSuchBucket"}}, "HeadBucket")

    def create_bucket(self, Bucket):
        self.created_bucket = Bucket
        self.missing_bucket = False

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs

    def get_object(self, Bucket, Key):
        body = _Body(self.objects[(Bucket, Key)]["Body"])
        self.last_body = body
        return {"Body": body}


def test_rustfs_storage_cria_bucket_grava_e_le(monkeypatch):
    fake_client = _FakeS3Client(missing_bucket=True)
    monkeypatch.setattr(storage_service.boto3, "client", lambda *args, **kwargs: fake_client)

    storage = RustFSS3ObjectStorage(
        endpoint="rustfs:9000",
        access_key="key",
        secret_key="secret",
        bucket="uda",
        secure=False,
    )
    stored = storage.store(key="mrv/doc.pdf", content=b"pdf")

    assert fake_client.created_bucket == "uda"
    assert stored.uri == "s3://uda/mrv/doc.pdf"
    assert stored.size_bytes == 3
    assert fake_client.objects[("uda", "mrv/doc.pdf")]["ContentType"] == "application/pdf"
    assert storage.read(stored.uri) == b"pdf"
    assert fake_client.last_body.closed is True


def test_rustfs_storage_propaga_erro_de_bucket(monkeypatch):
    class ForbiddenClient(_FakeS3Client):
        def head_bucket(self, Bucket):
            raise ClientError({"Error": {"Code": "403"}}, "HeadBucket")

    monkeypatch.setattr(storage_service.boto3, "client", lambda *args, **kwargs: ForbiddenClient())

    with pytest.raises(ClientError):
        RustFSS3ObjectStorage(
            endpoint="rustfs:9000",
            access_key="key",
            secret_key="secret",
            bucket="uda",
            secure=False,
        )


def test_build_object_storage_escolhe_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(
        storage_service,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "storage_backend": "local",
                "documents_dir": tmp_path,
            },
        )(),
    )

    assert isinstance(build_object_storage(), LocalObjectStorage)


def test_object_storage_base_rejeita_uso_direto():
    storage = ObjectStorage()

    with pytest.raises(NotImplementedError):
        storage.store(key="doc.pdf", content=b"pdf")

    with pytest.raises(NotImplementedError):
        storage.read("file:///tmp/doc.pdf")


def test_build_object_storage_escolhe_rustfs(monkeypatch):
    sentinel = object()

    monkeypatch.setattr(
        storage_service,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "storage_backend": "rustfs",
                "rustfs_endpoint": "rustfs:9000",
                "rustfs_access_key": "key",
                "rustfs_secret_key": "secret",
                "rustfs_bucket": "uda",
                "rustfs_secure": False,
            },
        )(),
    )
    monkeypatch.setattr(storage_service, "RustFSS3ObjectStorage", lambda **kwargs: sentinel)

    assert build_object_storage() is sentinel
