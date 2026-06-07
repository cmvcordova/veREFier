"""ref-checker: verify references against Crossref/arXiv/OpenAlex; emit only matches."""
from __future__ import annotations

VERIFIED = "VERIFIED"
MISMATCH = "MISMATCH"
NOT_FOUND = "NOT_FOUND"

import re
import unicodedata
from difflib import SequenceMatcher

_LATEX = re.compile(r"\\[a-zA-Z]+|[{}$]")
_NONWORD = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")


def _fold_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def normalize_title(s: str) -> str:
    s = _LATEX.sub(" ", s)
    s = _fold_accents(s).lower()
    s = _NONWORD.sub(" ", s)
    return _WS.sub(" ", s).strip()


def normalize_surname(s: str) -> str:
    return _WS.sub(" ", _NONWORD.sub(" ", _fold_accents(s).lower())).strip()


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()
