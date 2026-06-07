import json, pathlib
import verify_refs as vr

FIX = pathlib.Path(__file__).parent / "fixtures"

def _stub(path):
    def fetch(url, headers=None):
        return path.read_text()
    return fetch

def test_resolve_crossref_returns_candidate():
    ref = vr.Ref(key="tsne", raw="", title="Visualizing Data using t-SNE",
                 authors=["van der Maaten"], year=2008)
    cand = vr.resolve_crossref(ref, fetch=_stub(FIX / "crossref_tsne.json"))
    assert cand is not None
    assert cand.identifier_type == "doi"
    assert cand.identifier == "10.5555/1953048.2021068"
    assert cand.year == 2008
    assert any("Maaten" in a for a in cand.authors)

def test_resolve_crossref_empty_returns_none():
    ref = vr.Ref(key="x", raw="", title="nope")
    cand = vr.resolve_crossref(ref, fetch=lambda u, headers=None: '{"message":{"items":[]}}')
    assert cand is None

def test_resolve_arxiv_returns_eprint():
    ref = vr.Ref(key="umap", raw="", title="UMAP Uniform Manifold Approximation and Projection",
                 authors=["McInnes"], year=2018)
    cand = vr.resolve_arxiv(ref, fetch=_stub(FIX / "arxiv_umap.xml"))
    assert cand.identifier_type == "arxiv"
    assert cand.identifier == "1802.03426"
    assert cand.year == 2018

def test_resolve_openalex_returns_workid_when_no_doi():
    ref = vr.Ref(key="pythia", raw="", title="Pythia A Suite for Analyzing Large Language Models",
                 authors=["Biderman"], year=2023)
    cand = vr.resolve_openalex(ref, fetch=_stub(FIX / "openalex_pythia.json"))
    assert cand.identifier_type == "openalex"
    assert cand.identifier == "W4385245566"
    assert cand.year == 2023

def test_resolve_cascade_prefers_crossref(monkeypatch):
    ref = vr.Ref(key="tsne", raw="", title="Visualizing Data using t-SNE",
                 authors=["van der Maaten"], year=2008)
    cand = vr.resolve(ref,
        fetch_crossref=_stub(FIX / "crossref_tsne.json"),
        fetch_arxiv=lambda u, headers=None: "<feed></feed>",
        fetch_openalex=lambda u, headers=None: '{"results":[]}')
    assert cand.source == "crossref"
