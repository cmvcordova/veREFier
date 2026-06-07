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
- `verified.bib` contains ONLY `VERIFIED` entries, each with `doi =` or `eprint =`.
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

## Offline / API down

`--offline` and network failures make every ref `NOT_FOUND` (reason: cannot verify). The tool never
degrades to "assume valid."
