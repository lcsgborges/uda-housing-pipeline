from app.modules.ingestion.hashing import sha256_bytes


def test_sha256_bytes_consistente():
    payload = b"abc123"
    first = sha256_bytes(payload)
    second = sha256_bytes(payload)
    assert first == second
    assert len(first) == 64
