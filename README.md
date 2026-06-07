# ref-checker

A dependency-free Claude skill (and CLI) that gates every reference behind a live-API-verified
identifier (DOI preferred; arXiv / OpenAlex accepted), so bibliographies cannot be hallucinated.

## Use as a CLI
    python verify_refs.py refs.bib --out-bib verified.bib --report report.md

## Use as a Claude skill
Copy this directory where your agent loads skills. See `SKILL.md`.

## Test
    python -m pytest tests/ -v   # fully offline; network is stubbed

Python 3, standard library only.

## License
MIT — see LICENSE
