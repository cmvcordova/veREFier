"""veREFier: verify references against Crossref/arXiv/OpenAlex; emit only matches."""
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


_STRENGTH = {"doi": 3, "arxiv": 2, "url": 1}


def strength_of(identifier_type) -> int:
    """Verification-strength tier: doi (3) > arxiv (2) > url (1) > else (0)."""
    return _STRENGTH.get(identifier_type, 0)

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
    arxiv: Optional[str] = None


@dataclass
class Candidate:
    title: str
    authors: List[str]
    year: Optional[int]
    identifier_type: str   # "doi" | "arxiv" | "url"
    identifier: str
    source: str            # "crossref" | "arxiv" | "openalex"


def _surnames(authors) -> set:
    out = set()
    for a in authors:
        # BibTeX "Family, Given" puts the surname BEFORE the comma; "Given Family"
        # order (and most APIs' bare family field) put it last. Detect the comma on
        # the raw string, since normalize_surname strips it, then take the last token
        # of the surname part (handles multi-word surnames consistently on both sides).
        head = a.split(",", 1)[0] if "," in a else a
        parts = normalize_surname(head).split()
        if parts:
            out.add(parts[-1])
    return out


def _author_overlap(ref_authors, cand_authors) -> bool:
    return bool(_surnames(ref_authors) & _surnames(cand_authors))


def _year_ok(ry, cy) -> bool:
    if ry is None or cy is None:
        return True            # year absent on one side is not disqualifying
    return abs(int(ry) - int(cy)) <= 1


# Words too common to discriminate one title from another. "not"/"no"/"non" are kept
# significant on purpose — they flip meaning ("all" vs "not all").
_STOP = {"a", "an", "the", "of", "for", "to", "in", "on", "and", "or", "with", "via",
         "using", "from", "by", "as", "at", "is", "are", "be", "that", "this"}
_TOKEN_FUZZ = 0.85   # two tokens count as the same word above this char-ratio (spelling variants)


def _sig_tokens(s: str):
    return [t for t in normalize_title(s).split() if t not in _STOP]


def _titles_agree(a: str, b: str) -> bool:
    """Char-ratio >= TITLE_THRESHOLD is necessary but NOT sufficient: it rewards shared
    boilerplate, so a single swapped *significant* word (t-SNE/UMAP, GPT-3/GPT-4, all/not-all,
    method-for-X/Y) still scores 0.92-0.98. Additionally require every significant word on
    EACH side to have a (fuzzy) partner on the other — a swapped/added content word then has
    no partner and the titles disagree. Fuzzy token matching keeps spelling variants
    (visualising/visualizing) agreeing. This matters most on the stated-DOI path: without it a
    DOI pointing at the wrong paper would VERIFY and its metadata would overwrite the ref's."""
    if title_similarity(a, b) < TITLE_THRESHOLD:
        return False
    ta, tb = _sig_tokens(a), _sig_tokens(b)
    if not ta or not tb:
        return True   # nothing beyond the char ratio to compare (e.g. all-stopword title)
    covered = lambda xs, ys: all(any(title_similarity(x, y) >= _TOKEN_FUZZ for y in ys) for x in xs)
    return covered(ta, tb) and covered(tb, ta)


def verdict(ref: Ref, cand: Optional[Candidate]) -> str:
    if cand is None:
        return NOT_FOUND
    title_ok = _titles_agree(ref.title, cand.title)
    author_ok = (not ref.authors) or _author_overlap(ref.authors, cand.authors)
    if title_ok and author_ok and _year_ok(ref.year, cand.year):
        return VERIFIED
    return MISMATCH

_BIB_START = re.compile(r"@(\w+)\s*\{")
_FIELD = re.compile(r"(\w+)\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n?", re.DOTALL)


def _iter_bib_entries(text: str):
    """Yield (key, body) per BibTeX entry, delimiting each by BALANCED braces.

    The previous regex terminated an entry only at a ``}`` followed by ``@``/EOF,
    so a ``% comment`` (or any non-``@`` text) between entries made it swallow the
    next entry — silently merging and DROPPING references. Counting braces from the
    entry's opening ``{`` is robust to inter-entry comments and stray ``@`` (e.g. an
    email), and to nested field braces. ``@comment``/``@string``/``@preamble`` are skipped.
    """
    pos = 0
    for m in _BIB_START.finditer(text):
        if m.start() < pos:
            continue  # a brace/`@` inside an already-consumed entry body
        if m.group(1).lower() in ("comment", "string", "preamble"):
            continue
        open_brace = m.end() - 1
        depth, j = 0, open_brace
        while j < len(text):
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            continue  # unbalanced entry; skip rather than swallow the rest of the file
        pos = j + 1
        inner = text[open_brace + 1:j]
        comma = inner.find(",")
        if comma < 0:
            continue
        yield inner[:comma].strip(), inner[comma + 1:]
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


_ARXIV_IN_TEXT = re.compile(r"(?:arxiv[:.]?\s*)?(\d{4}\.\d{4,5})", re.IGNORECASE)


def extract_arxiv_id(text: str) -> Optional[str]:
    """Find an arXiv id in free text: ``arXiv:XXXX.XXXXX``, a bare ``XXXX.XXXXX``,
    or a ``10.48550/arXiv.XXXX.XXXXX`` DOI. Returns the bare ``XXXX.XXXXX`` or None."""
    if not text:
        return None
    m = _ARXIV_IN_TEXT.search(text)
    return m.group(1) if m else None


def _split_authors(s: str) -> List[str]:
    return [a.strip() for a in re.split(r"\s+and\s+", s) if a.strip()]


_FIELD_NAME = re.compile(r"(\w+)\s*=\s*")


def _parse_fields(body: str) -> dict:
    """Extract ``name = {value}`` / ``name = "value"`` / ``name = bareword`` fields,
    reading brace values by BALANCED braces. The old ``_FIELD`` regex used a non-greedy
    ``(.+?)}`` that stopped at the FIRST closing brace, so a value with a nested group
    (e.g. ``title = {{scDEED}: a statistical ...}``) was truncated to ``scDEED`` — which
    then mis-searched APIs and false-MISMATCHed. Balanced reading keeps the full value."""
    fields, i, n = {}, 0, len(body)
    while True:
        m = _FIELD_NAME.search(body, i)
        if not m:
            break
        name, j = m.group(1).lower(), m.end()
        if j >= n:
            break
        if body[j] == "{":
            depth, k = 0, j
            while k < n:
                if body[k] == "{":
                    depth += 1
                elif body[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            fields[name], i = body[j + 1:k], k + 1
        elif body[j] == '"':
            k = body.find('"', j + 1)
            if k < 0:
                break
            fields[name], i = body[j + 1:k], k + 1
        else:
            k = j
            while k < n and body[k] not in ",\n":
                k += 1
            fields[name], i = body[j:k].strip(), k + 1
    return fields


def parse_bib(text: str) -> List[Ref]:
    refs = []
    for key, body in _iter_bib_entries(text):
        fields = {k: v.strip() for k, v in _parse_fields(body).items()}
        year = int(fields["year"]) if fields.get("year", "").strip().isdigit() else None
        arxiv = (extract_arxiv_id(fields.get("eprint", ""))
                 or extract_arxiv_id(fields.get("doi", ""))
                 or extract_arxiv_id(body))
        refs.append(Ref(key=key.strip(), raw=body.strip(),
                        title=re.sub(r"[{}]", "", fields.get("title", "")),
                        authors=_split_authors(fields.get("author", "")),
                        year=year, doi=fields.get("doi") or None, arxiv=arxiv))
    return refs


_INITIAL = re.compile(r"^[A-Z](\.[A-Z])*\.?$")


def parse_authors_from_bibitem(raw: str) -> List[str]:
    """Extract author surnames from the text before the first ``...'' title quote.

    Network-free, stdlib only. Returns [] for quote-less/empty input.
    """
    if not raw:
        return []
    idx = raw.find("``")
    if idx < 0:
        return []
    head = raw[:idx]
    head = head.replace("~", " ")
    head = re.sub(r"\\emph\{[^}]*\}", " ", head)   # drop \emph{...}
    head = re.sub(r"\\[a-zA-Z]+", " ", head)        # drop other latex commands
    head = re.sub(r"[{}]", " ", head)                # drop stray braces
    head = re.sub(r"\bet\s+al\.?", " ", head)       # drop "et al."
    chunks = re.split(r",|\band\b", head)
    authors: List[str] = []
    for chunk in chunks:
        tokens = chunk.split()
        surname = [t for t in tokens if not _INITIAL.match(t)]
        name = " ".join(surname).strip(" .,;:")
        if name:
            authors.append(name)
    return authors


def parse_bibitems(text: str) -> List[Ref]:
    refs = []
    for m in re.finditer(r"\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem\{|\\end\{thebibliography\}|$)",
                         text, re.DOTALL):
        key, raw = m.group(1), m.group(2).strip()
        ym = _YEAR.search(raw)
        # title heuristic: text inside the first ``...'' quotes
        tm = re.search(r"``(.+?)''", raw, re.DOTALL) or re.search(r'"(.+?)"', raw, re.DOTALL)
        title = re.sub(r"\s+", " ", tm.group(1)).strip() if tm else re.sub(r"\s+", " ", raw[:80]).strip()
        title = title.rstrip(",.;: ")
        refs.append(Ref(key=key, raw=raw,
                        title=title,
                        authors=parse_authors_from_bibitem(raw),
                        year=int(ym.group(0)) if ym else None, doi=None,
                        arxiv=extract_arxiv_id(raw)))
    return refs


def parse_list(text: str) -> List[Ref]:
    return [Ref(key=None, raw=line.strip(), title=line.strip(),
                arxiv=extract_arxiv_id(line))
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
import ssl
import urllib.parse
import urllib.request

USER_AGENT = "veREFier/1.0 (mailto:anonymous@example.com)"

try:
    import certifi as _certifi
    _SSL_CTX = ssl.create_default_context(cafile=_certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


def _http_get(url: str, headers: Optional[dict] = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as r:
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


def _arxiv_entry_to_candidate(entry, ns, arxiv_id=None) -> Optional[Candidate]:
    """Turn a single Atom <entry> into a Candidate. If ``arxiv_id`` is given it is
    used as the identifier; otherwise it is parsed from the entry's <id>."""
    title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
    if arxiv_id is None:
        idtext = entry.findtext("a:id", default="", namespaces=ns) or ""
        m = _ARXIV_ID.search(idtext)
        if not m:
            return None
        arxiv_id = m.group(1)
    authors = [e.findtext("a:name", default="", namespaces=ns)
               for e in entry.findall("a:author", ns)]
    pub = entry.findtext("a:published", default="", namespaces=ns) or ""
    year = int(pub[:4]) if pub[:4].isdigit() else None
    return Candidate(title=title, authors=authors, year=year,
                     identifier_type="arxiv", identifier=arxiv_id, source="arxiv")


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
    return _arxiv_entry_to_candidate(entry, ns)


def resolve_arxiv_by_id(ref: Ref, fetch=_http_get) -> Optional[Candidate]:
    """Look a ref up directly via the authoritative arXiv ``id_list`` endpoint."""
    if not ref.arxiv:
        return None
    url = f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(ref.arxiv)}"
    try:
        root = ET.fromstring(fetch(url))
    except Exception:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", ns)
    if entry is None:
        return None
    return _arxiv_entry_to_candidate(entry, ns, arxiv_id=ref.arxiv)


def resolve_doi_by_id(ref: Ref, fetch=_http_get) -> Optional[Candidate]:
    """Dereference the ref's STATED DOI and build a candidate from THAT exact record.

    The title-search resolvers ignore the DOI a ref already carries, so a wrong/fabricated
    DOI that happens to share a title with the real paper would be silently "corrected"
    and pass — the tool would never tell you your bibliography points at the wrong DOI.
    Looking the stated DOI up directly makes it authoritative: if it resolves to a
    different paper than the ref claims, ``verdict`` returns MISMATCH and the report shows
    what the DOI actually points to. Returns None if the DOI does not resolve via Crossref
    (e.g. a DataCite-only DOI), so the caller can fall back to a title search."""
    if not ref.doi:
        return None
    doi = ref.doi.strip()
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
    try:
        m = json.loads(fetch(url)).get("message", {})
    except Exception:
        return None
    if not m or not m.get("title"):
        return None
    title = re.sub(r"<[^>]+>", "", (m.get("title") or [""])[0])
    authors = [a.get("family", "") for a in m.get("author", []) if a.get("family")]
    parts = m.get("issued", {}).get("date-parts", [[None]])
    year = parts[0][0] if parts and parts[0] else None
    return Candidate(title=title, authors=authors, year=year,
                     identifier_type="doi", identifier=doi, source="crossref")


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
        # The authority asserts this work has no DOI. Emit its stable landing URL
        # (a field of the matched record), never a fabricated identifier.
        ident_type = "url"
        landing = (it.get("primary_location") or {}).get("landing_page_url") or ""
        oa = it.get("ids", {}).get("openalex", "") or ""  # full https://openalex.org/W... URL
        ident = landing or (oa if oa.startswith("http") else (f"https://openalex.org/{oa}" if oa else ""))
    if not ident:
        return None
    return Candidate(title=it.get("display_name", ""), authors=authors,
                     year=it.get("publication_year"),
                     identifier_type=ident_type, identifier=ident, source="openalex")


def resolve(ref: Ref, fetch_crossref=_http_get, fetch_arxiv=_http_get,
            fetch_openalex=_http_get, fetch_arxiv_id=_http_get) -> Optional[Candidate]:
    # A ref's OWN stated identifier is authoritative: look it up directly and judge the ref
    # against the record it actually resolves to. A stated id that points at a different
    # paper must surface as MISMATCH, NOT be silently overridden by a title search that
    # finds the right paper elsewhere. Only when no stated id resolves do we title-search.
    if ref.arxiv:
        cand = resolve_arxiv_by_id(ref, fetch=fetch_arxiv_id)
        if cand is not None:
            return cand
    if ref.doi:
        cand = resolve_doi_by_id(ref, fetch=fetch_crossref)
        if cand is not None:
            return cand
    chain = [(resolve_crossref, fetch_crossref),
             (resolve_arxiv, fetch_arxiv),
             (resolve_openalex, fetch_openalex)]
    for fn, fetch in chain:
        cand = fn(ref, fetch=fetch)
        if cand is not None and verdict(ref, cand) == VERIFIED:
            return cand
    # Return the best-similarity non-verified candidate for MISMATCH reporting,
    # but only when it is similar enough to be meaningful (>= _MISMATCH_MIN_SIM).
    # A low-similarity result means the title search found something unrelated —
    # common for grey literature, @misc/URL-only entries, or unusual titles.
    # Those should surface as NOT_FOUND, not MISMATCH.  The stated-identifier
    # paths above already handle genuine wrong-DOI/wrong-arXiv cases.
    _MISMATCH_MIN_SIM = 0.60
    best_cand, best_sim = None, 0.0
    for fn, fetch in chain:
        cand = fn(ref, fetch=fetch)
        if cand is not None:
            sim = title_similarity(ref.title, cand.title)
            if sim > best_sim:
                best_sim, best_cand = sim, cand
    if best_cand is not None and best_sim >= _MISMATCH_MIN_SIM:
        return best_cand
    return None

import argparse
import sys


def check_ref(ref: Ref, resolver=None) -> dict:
    resolver = resolver or (lambda r: resolve(r))
    cand = resolver(ref)
    v = verdict(ref, cand)
    return {
        "key": ref.key, "claimed_title": ref.title, "verdict": v,
        "has_identifier": bool(ref.doi or ref.arxiv),
        "identifier_type": cand.identifier_type if cand else None,
        "strength": strength_of(cand.identifier_type) if cand else 0,
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
        it = r["identifier_type"]
        idline = (f"  doi = {{{r['identifier']}}}," if it == "doi"
                  else f"  url = {{{r['identifier']}}}," if it == "url"
                  else f"  eprint = {{{r['identifier']}}},")
        authors = " and ".join(r.get("authors") or [])
        out.append(f"@misc{{{r['key']},\n  title = {{{r['title']}}},\n"
                   f"  author = {{{authors}}},\n  year = {{{r.get('year')}}},\n{idline}\n}}")
    return "\n\n".join(out) + ("\n" if out else "")


def emit_report(results) -> str:
    lines = ["# Reference verification report", ""]
    n = {VERIFIED: 0, MISMATCH: 0, NOT_FOUND: 0, "GREY_LIT": 0}
    tiers = {"doi": 0, "arxiv": 0, "url": 0}
    for r in results:
        v = r["verdict"]
        # Entries with no doi/arxiv field (URL-only, @misc, @manual, software,
        # grey literature) cannot be meaningfully verified against academic
        # databases.  Any non-VERIFIED result for such an entry is expected and
        # does not indicate an error — report it as GREY_LIT instead.
        grey = (v != VERIFIED and not r.get("has_identifier"))
        if grey:
            n["GREY_LIT"] += 1
        else:
            n[v] += 1
        tier = (r.get("identifier_type") if v == VERIFIED else None)
        if tier in tiers:
            tiers[tier] += 1
        tag = f" [{tier}]" if tier else ""
        tail = (f" -> {r.get('source')}:{r.get('identifier')}" if r.get("identifier") else "")
        warn = (f"  [claimed vs matched: \"{r.get('claimed_title','')}\" / "
                f"\"{r.get('matched_title','')}\"]" if v == MISMATCH and not grey else "")
        label = "GREY_LIT (url-only)" if grey else v
        lines.append(f"- `{r.get('key')}` **{label}**{tag}{tail}{warn}")
    lines += ["", (f"VERIFIED {n[VERIFIED]} "
                   f"(doi {tiers['doi']} / arxiv {tiers['arxiv']} / url {tiers['url']}) | "
                   f"MISMATCH {n[MISMATCH]} | NOT_FOUND {n[NOT_FOUND]} | "
                   f"GREY_LIT {n['GREY_LIT']}")]
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
    if args.input == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(args.input) as f:
                text = f.read()
        except OSError as e:
            print(f"error: cannot read {args.input}: {e}", file=sys.stderr)
            return 2
    refs = parse(text, args.format)
    resolver = (lambda r: None) if args.offline else None
    results = [check_ref(r, resolver=resolver) for r in refs]
    report = emit_report(results)
    if args.report:
        with open(args.report, "w") as f:
            f.write(report)
    else:
        print(report)
    if args.out_bib:
        with open(args.out_bib, "w") as f:
            f.write(emit_bib(results))
    return 0 if all(r["verdict"] == VERIFIED for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
