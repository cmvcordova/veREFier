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


def _surnames(authors) -> set:
    out = set()
    for a in authors:
        parts = normalize_surname(a).split()
        if parts:
            out.add(parts[-1])
    return out


def _author_overlap(ref_authors, cand_authors) -> bool:
    return bool(_surnames(ref_authors) & _surnames(cand_authors))


def _year_ok(ry, cy) -> bool:
    if ry is None or cy is None:
        return True            # year absent on one side is not disqualifying
    return abs(int(ry) - int(cy)) <= 1


def verdict(ref: Ref, cand: Optional[Candidate]) -> str:
    if cand is None:
        return NOT_FOUND
    title_ok = title_similarity(ref.title, cand.title) >= TITLE_THRESHOLD
    author_ok = (not ref.authors) or _author_overlap(ref.authors, cand.authors)
    if title_ok and author_ok and _year_ok(ref.year, cand.year):
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

import json
import urllib.parse
import urllib.request

USER_AGENT = "ref-checker/1.0 (mailto:anonymous@example.com)"


def _http_get(url: str, headers: Optional[dict] = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def resolve_crossref(ref: Ref, fetch=_http_get) -> Optional[Candidate]:
    q = urllib.parse.quote(ref.title or ref.raw)
    url = f"https://api.crossref.org/works?query.bibliographic={q}&rows=5"
    try:
        items = json.loads(fetch(url)).get("message", {}).get("items", [])
    except Exception:
        return None
    if not items:
        return None
    it = max(items, key=lambda x: title_similarity(ref.title, (x.get("title") or [""])[0]))
    title = (it.get("title") or [""])[0]
    authors = [a.get("family", "") for a in it.get("author", []) if a.get("family")]
    parts = it.get("issued", {}).get("date-parts", [[None]])
    year = parts[0][0] if parts and parts[0] else None
    doi = it.get("DOI")
    if not doi:
        return None
    return Candidate(title=title, authors=authors, year=year,
                     identifier_type="doi", identifier=doi, source="crossref")

import xml.etree.ElementTree as ET

_ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})")


def resolve_arxiv(ref: Ref, fetch=_http_get) -> Optional[Candidate]:
    q = urllib.parse.quote(normalize_title(ref.title or ref.raw))
    url = f"http://export.arxiv.org/api/query?search_query=ti:{q}&max_results=5"
    try:
        root = ET.fromstring(fetch(url))
    except Exception:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = root.findall("a:entry", ns)
    if not entries:
        return None
    entry = max(entries, key=lambda e: title_similarity(
        ref.title, (e.findtext("a:title", default="", namespaces=ns) or "").strip()))
    title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
    idtext = entry.findtext("a:id", default="", namespaces=ns) or ""
    m = _ARXIV_ID.search(idtext)
    if not m:
        return None
    authors = [e.findtext("a:name", default="", namespaces=ns)
               for e in entry.findall("a:author", ns)]
    pub = entry.findtext("a:published", default="", namespaces=ns) or ""
    year = int(pub[:4]) if pub[:4].isdigit() else None
    return Candidate(title=title, authors=authors, year=year,
                     identifier_type="arxiv", identifier=m.group(1), source="arxiv")


def resolve_openalex(ref: Ref, fetch=_http_get) -> Optional[Candidate]:
    q = urllib.parse.quote(ref.title or ref.raw)
    url = f"https://api.openalex.org/works?search={q}&per-page=5"
    try:
        results = json.loads(fetch(url)).get("results", [])
    except Exception:
        return None
    if not results:
        return None
    it = max(results, key=lambda x: title_similarity(ref.title, x.get("display_name", "") or ""))
    authors = [a.get("author", {}).get("display_name", "") for a in it.get("authorships", [])]
    doi = it.get("doi")
    if doi:
        ident_type, ident = "doi", doi.replace("https://doi.org/", "")
    else:
        ident_type = "openalex"
        ident = it.get("ids", {}).get("openalex", "").rsplit("/", 1)[-1]
    if not ident:
        return None
    return Candidate(title=it.get("display_name", ""), authors=authors,
                     year=it.get("publication_year"),
                     identifier_type=ident_type, identifier=ident, source="openalex")


def resolve(ref: Ref, fetch_crossref=_http_get, fetch_arxiv=_http_get,
            fetch_openalex=_http_get) -> Optional[Candidate]:
    for fn, fetch in ((resolve_crossref, fetch_crossref),
                      (resolve_arxiv, fetch_arxiv),
                      (resolve_openalex, fetch_openalex)):
        cand = fn(ref, fetch=fetch)
        if cand is not None and verdict(ref, cand) == VERIFIED:
            return cand
    # return the best non-verified candidate (Crossref first) for MISMATCH reporting
    for fn, fetch in ((resolve_crossref, fetch_crossref),
                      (resolve_arxiv, fetch_arxiv),
                      (resolve_openalex, fetch_openalex)):
        cand = fn(ref, fetch=fetch)
        if cand is not None:
            return cand
    return None

import argparse
import sys


def check_ref(ref: Ref, resolver=None) -> dict:
    resolver = resolver or (lambda r: resolve(r))
    cand = resolver(ref)
    v = verdict(ref, cand)
    return {
        "key": ref.key, "claimed_title": ref.title, "verdict": v,
        "identifier_type": cand.identifier_type if cand else None,
        "identifier": cand.identifier if cand else None,
        "source": cand.source if cand else None,
        "matched_title": cand.title if cand else None,
        "title": cand.title if (cand and v == VERIFIED) else ref.title,
        "authors": cand.authors if (cand and v == VERIFIED) else ref.authors,
        "year": cand.year if (cand and v == VERIFIED) else ref.year,
    }


def emit_bib(results) -> str:
    out = []
    for r in results:
        if r["verdict"] != VERIFIED:
            continue
        idline = (f"  doi = {{{r['identifier']}}}," if r["identifier_type"] == "doi"
                  else f"  eprint = {{{r['identifier']}}},")
        authors = " and ".join(r.get("authors") or [])
        out.append(f"@misc{{{r['key']},\n  title = {{{r['title']}}},\n"
                   f"  author = {{{authors}}},\n  year = {{{r.get('year')}}},\n{idline}\n}}")
    return "\n\n".join(out) + ("\n" if out else "")


def emit_report(results) -> str:
    lines = ["# Reference verification report", ""]
    n = {VERIFIED: 0, MISMATCH: 0, NOT_FOUND: 0}
    for r in results:
        n[r["verdict"]] += 1
        tail = (f" -> {r.get('source')}:{r.get('identifier')}" if r.get("identifier") else "")
        warn = (f"  [claimed vs matched: \"{r.get('claimed_title','')}\" / "
                f"\"{r.get('matched_title','')}\"]" if r["verdict"] == MISMATCH else "")
        lines.append(f"- `{r.get('key')}` **{r['verdict']}**{tail}{warn}")
    lines += ["", f"VERIFIED {n[VERIFIED]} | MISMATCH {n[MISMATCH]} | NOT_FOUND {n[NOT_FOUND]}"]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify references behind a resolved identifier.")
    ap.add_argument("input", help="path to a .bib / bibitem / list file ('-' for stdin)")
    ap.add_argument("--format", choices=["bib", "bibitem", "list"], default=None)
    ap.add_argument("--out-bib", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--offline", action="store_true",
                    help="do not hit the network; every ref becomes NOT_FOUND")
    args = ap.parse_args(argv)
    text = sys.stdin.read() if args.input == "-" else open(args.input).read()
    refs = parse(text, args.format)
    resolver = (lambda r: None) if args.offline else None
    results = [check_ref(r, resolver=resolver) for r in refs]
    report = emit_report(results)
    (open(args.report, "w").write(report) if args.report else print(report))
    if args.out_bib:
        open(args.out_bib, "w").write(emit_bib(results))
    return 0 if all(r["verdict"] == VERIFIED for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
