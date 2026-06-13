# veREFier

A dependency-free Claude skill (and CLI) that gates every reference behind a live-API-verified
identifier (DOI preferred; arXiv / OpenAlex accepted), so bibliographies cannot be hallucinated.

## Use as a CLI
    python verify_refs.py refs.bib --out-bib verified.bib --report report.md

## Use as a Claude skill
Copy this directory where your agent loads skills. See `SKILL.md`.

## Test
    python -m pytest tests/ -v   # fully offline; network is stubbed

Python 3, standard library only.

## How it works

Each reference is parsed (`.bib`, `\bibitem`, or one-title-per-line), resolved against a live
authority, then judged by a single match gate. **The order matters**: a reference's *own* stated
identifier is authoritative and is checked *first* — so a wrong DOI is caught, not silently
"corrected" by a title search that happens to find the right paper.

```
                       ┌────────────────────────────────────────────┐
   reference  ───────▶ │  resolve(): pick ONE candidate record       │
 (title, authors,      └────────────────────────────────────────────┘
  year, + maybe                         │
  a stated DOI/arXiv)                   ▼
        ┌──────────────────────────────────────────────────────────────────┐
        │ 1. STATED id present?  (authoritative — judged as-is, no override) │
        │      • arXiv id  → arXiv  id_list lookup                           │
        │      • DOI       → Crossref /works/{doi}                           │
        │    resolves to a record? ──▶ use THAT record  (even if it differs) │
        └──────────────────────────────────────────────────────────────────┘
                                        │  no stated id (or it didn't resolve)
                                        ▼
        ┌──────────────────────────────────────────────────────────────────┐
        │ 2. TITLE search cascade — first VERIFIED candidate wins:           │
        │      Crossref  ▶  arXiv  ▶  OpenAlex                               │
        │    (OpenAlex emits a stable URL when the work genuinely has no DOI)│
        └──────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
        ┌──────────────────────────────────────────────────────────────────┐
        │  verdict(ref, candidate):                                          │
        │    title_sim ≥ 0.90   AND   author-surname overlap   AND  year ±1  │
        │         ├─ all pass ............................ VERIFIED          │
        │         ├─ candidate found, gate fails ......... MISMATCH          │
        │         └─ no candidate ........................ NOT_FOUND         │
        └──────────────────────────────────────────────────────────────────┘
```

Only `VERIFIED` rows are emitted to `--out-bib`. `--report` lists every verdict, and the process
exits non-zero if any reference is not `VERIFIED` (usable as a CI / pre-commit gate).

**Verification strength** is labelled per row: `doi` (strongest) > `arxiv` > `url` (weakest). A
`url` tier means an authority asserted the work has no DOI and we emitted its stable landing URL —
a field of a matched record, never a fabricated id. `[url]` rows deserve a second look.

### The one rule
You may only emit an identifier or canonical title/author/year that a live API returned. If a
reference is not `VERIFIED`, it does not go into a bibliography.

## License
MIT — see LICENSE
