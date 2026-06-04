import logging

from app.core.config import get_settings


def configure_logging() -> None:
    """Configura o logging global conforme o nível definido no ambiente."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
