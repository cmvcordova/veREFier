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

from dataclasses import dataclass, field
from typing import Optional, List

TITLE_THRESHOLD = 0.90


@dataclass
class Ref:
    key: Optional[str]
    raw: str
    title: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None


@dataclass
class Candidate:
    title: str
    authors: List[str]
    year: Optional[int]
    identifier_type: str   # "doi" | "arxiv" | "openalex"
    identifier: str
    source: str            # "crossref" | "arxiv" | "openalex"


def _author_overlap(ref_authors, cand_authors) -> bool:
    r = {normalize_surname(a).split()[-1] for a in ref_authors if a.strip()}
    c = {normalize_surname(a).split()[-1] for a in cand_authors if a.strip()}
    return bool(r & c)


def _year_ok(ry, cy) -> bool:
    if ry is None or cy is None:
        return True            # year absent on one side is not disqualifying
    return abs(int(ry) - int(cy)) <= 1


def verdict(ref: Ref, cand: Optional[Candidate]) -> str:
    if cand is None:
        return NOT_FOUND
    title_ok = title_similarity(ref.title, cand.title) >= TITLE_THRESHOLD
    if title_ok and _author_overlap(ref.authors, cand.authors) and _year_ok(ref.year, cand.year):
        return VERIFIED
    return MISMATCH
