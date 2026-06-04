from datetime import UTC, datetime


def utc_now() -> datetime:
    """Retorna UTC sem timezone para compatibilidade com colunas DateTime atuais."""
    return datetime.now(UTC).replace(tzinfo=None)
