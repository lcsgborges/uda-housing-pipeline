import unicodedata


def normalize_for_search(value: str) -> str:
    """Normaliza texto para comparações sem acento e sem diferença de caixa."""
    decomposed = unicodedata.normalize("NFKD", value)
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return unaccented.casefold()
