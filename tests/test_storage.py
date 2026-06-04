import pytest

from app.modules.storage.service import _build_endpoint_url, _parse_s3_uri


@pytest.mark.parametrize("scheme", ["rustfs", "s3"])
def test_parse_s3_uri(scheme):
    bucket, key = _parse_s3_uri(f"{scheme}://uda-documents/mrv/doc.pdf")

    assert bucket == "uda-documents"
    assert key == "mrv/doc.pdf"


def test_parse_s3_uri_rejeita_scheme_invalido():
    with pytest.raises(ValueError):
        _parse_s3_uri("ftp://bucket/file.pdf")


def test_build_endpoint_url_para_rustfs_local_sem_tls():
    assert _build_endpoint_url(endpoint="rustfs:9000", secure=False) == "http://rustfs:9000"
