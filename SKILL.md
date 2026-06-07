---
name: ref-checker
description: Use when emitting, assembling, repairing, or checking any bibliography, citation, \cite, \bibitem, BibTeX entry, or reference list — verifies every reference against Crossref/arXiv/OpenAlex and emits only DOI/arXiv/OpenAlex-resolved matches, so citations cannot be hallucinated. Triggers both on explicit "check/verify these refs" requests and as a guardrail whenever you are about to write a citation.
---

# ref-checker

## The one rule

You may NOT write a DOI, arXiv id, or canonical title/author/year from memory. You may only
emit identifier and metadata fields that `verify_refs.py` returned from a live API response.
If the tool did not return `VERIFIED` for a reference, do not put it in a bibliography.

## On-demand: check/repair a bibliography

Run:
    python verify_refs.py path/to/refs.bib --out-bib verified.bib --report report.md

- Auto-detects `.bib`, `\bibitem` blocks, or a plain title-per-line list (override with `--format`).
- `verified.bib` contains ONLY `VERIFIED` entries, each with `doi =`, `eprint =`, or (url tier) `url =`.
- `report.md` lists every ref's verdict: `VERIFIED` / `MISMATCH` / `NOT_FOUND`.
- Exit code is nonzero if any ref is not `VERIFIED` — usable as a CI/pre-commit gate.

## Guardrail: before writing any new citation

When a task has you produce a citation that is not already verified, route it through the tool
(a one-line list is fine):
    printf '%s\n' "Paper Title Here" | python verify_refs.py - --format list

Then:
- `VERIFIED` -> copy the returned identifier + canonical fields verbatim into the bibliography.
- `MISMATCH` -> the title/author/year you had does not match what the identifier resolves to.
  Show the user the claimed-vs-matched titles from the report; do not emit. Ask to correct or drop.
- `NOT_FOUND` -> no authoritative record. Do not invent one. Tell the user it could not be verified.

Never silently emit a `MISMATCH` or `NOT_FOUND`.

## Verification strength & the URL fallback

Every `VERIFIED` ref carries a strength tier, surfaced in the report as `[doi]`/`[arxiv]`/`[url]`:
`doi` (strongest) > `arxiv` > `url` (weakest). The summary line counts each tier, e.g.
`VERIFIED 20 (doi 15 / arxiv 3 / url 2) | MISMATCH 2 | NOT_FOUND 0`.

Some legitimate works genuinely have no DOI or arXiv id (pre-DOI papers: t-SNE/JMLR 2008,
Levina–Bickel/NeurIPS 2004). For these the tool falls back to a stable `url`, but ONLY under a gate:

- The URL is emitted ONLY when an authority returns a record that MATCHES the ref
  (title + author + year, the usual gate) AND that record's own DOI field is null/absent.
  The authority itself is asserting "this work has no DOI"; the tool then emits that record's
  stable URL (`primary_location.landing_page_url`, else the `openalex.org/W...` id URL).
- The URL is always a field of a matched, authority-returned record — never model-generated.
- If NO record matches the ref, that is `NOT_FOUND` (a real failure). A `NOT_FOUND` is never
  turned into a URL.

The `[url]` tag flags weak verifications for human audit: a `[url]` ref deserves a second look
before it goes into a bibliography, whereas `[doi]`/`[arxiv]` are machine-anchored.

## Offline / API down

`--offline` and network failures make every ref `NOT_FOUND` (reason: cannot verify). The tool never
degrades to "assume valid."
