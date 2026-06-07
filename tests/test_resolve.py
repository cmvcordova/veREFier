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
