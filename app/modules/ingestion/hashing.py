import hashlib


def sha256_bytes(content: bytes) -> str:
    """Calcula o hash SHA-256 hexadecimal de um conteúdo em bytes."""
    return hashlib.sha256(content).hexdigest()
