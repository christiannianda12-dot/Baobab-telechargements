"""Normalisation de noms (équipes, championnats) : insensible à la casse, aux accents, à la ponctuation."""

import re
import unicodedata


def norm_key(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.strip().casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()
