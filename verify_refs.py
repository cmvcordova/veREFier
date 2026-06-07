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

_BIB_ENTRY = re.compile(r"@\w+\s*\{\s*([^,]+),(.*?)\}\s*(?=@|\Z)", re.DOTALL)
_FIELD = re.compile(r"(\w+)\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n?", re.DOTALL)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _split_authors(s: str) -> List[str]:
    return [a.strip() for a in re.split(r"\s+and\s+", s) if a.strip()]


def parse_bib(text: str) -> List[Ref]:
    refs = []
    for key, body in _BIB_ENTRY.findall(text):
        fields = {k.lower(): v.strip() for k, v in _FIELD.findall(body)}
        year = int(fields["year"]) if fields.get("year", "").strip().isdigit() else None
        refs.append(Ref(key=key.strip(), raw=body.strip(),
                        title=re.sub(r"[{}]", "", fields.get("title", "")),
                        authors=_split_authors(fields.get("author", "")),
                        year=year, doi=fields.get("doi") or None))
    return refs


def parse_bibitems(text: str) -> List[Ref]:
    refs = []
    for m in re.finditer(r"\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem\{|\\end\{thebibliography\}|$)",
                         text, re.DOTALL):
        key, raw = m.group(1), m.group(2).strip()
        ym = _YEAR.search(raw)
        # title heuristic: text inside the first ``...'' quotes
        tm = re.search(r"``(.+?)''", raw) or re.search(r'"(.+?)"', raw)
        refs.append(Ref(key=key, raw=raw,
                        title=tm.group(1) if tm else raw[:80],
                        authors=[], year=int(ym.group(0)) if ym else None, doi=None))
    return refs


def parse_list(text: str) -> List[Ref]:
    return [Ref(key=None, raw=line.strip(), title=line.strip())
            for line in text.splitlines() if line.strip()]


def detect_format(text: str) -> str:
    if "\\bibitem" in text:
        return "bibitem"
    if re.search(r"@\w+\s*\{", text):
        return "bib"
    return "list"


def parse(text: str, fmt: Optional[str] = None) -> List[Ref]:
    fmt = fmt or detect_format(text)
    return {"bib": parse_bib, "bibitem": parse_bibitems, "list": parse_list}[fmt](text)
