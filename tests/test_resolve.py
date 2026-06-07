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

def test_resolve_crossref_picks_best_title_match_not_first():
    ref = vr.Ref(key="tsne", raw="", title="Visualizing Data using t-SNE",
                 authors=["van der Maaten"], year=2008)
    cand = vr.resolve_crossref(ref, fetch=_stub(FIX / "crossref_tsne_ranked.json"))
    assert cand.identifier == "10.5555/1953048.2021068"

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

def test_strength_of_orders_tiers():
    assert vr.strength_of("doi") == 3
    assert vr.strength_of("arxiv") == 2
    assert vr.strength_of("url") == 1
    assert vr.strength_of("openalex") == 0
    assert vr.strength_of(None) == 0

def test_resolve_openalex_returns_workid_when_no_doi():
    ref = vr.Ref(key="pythia", raw="", title="Pythia A Suite for Analyzing Large Language Models",
                 authors=["Biderman"], year=2023)
    cand = vr.resolve_openalex(ref, fetch=_stub(FIX / "openalex_pythia.json"))
    # no doi and no primary_location -> falls back to the openalex.org landing URL
    assert cand.identifier_type == "url"
    assert cand.identifier == "https://openalex.org/W4385245566"
    assert cand.year == 2023

def test_resolve_openalex_no_doi_returns_landing_url():
    ref = vr.Ref(key="tsne", raw="", title="Visualizing Data using t-SNE",
                 authors=["van der Maaten"], year=2008)
    cand = vr.resolve_openalex(ref, fetch=_stub(FIX / "openalex_nodoi_url.json"))
    assert cand.identifier_type == "url"
    assert cand.identifier == "https://www.jmlr.org/papers/v9/vandermaaten08a.html"

def test_resolve_cascade_prefers_crossref(monkeypatch):
    ref = vr.Ref(key="tsne", raw="", title="Visualizing Data using t-SNE",
                 authors=["van der Maaten"], year=2008)
    cand = vr.resolve(ref,
        fetch_crossref=_stub(FIX / "crossref_tsne.json"),
        fetch_arxiv=lambda u, headers=None: "<feed></feed>",
        fetch_openalex=lambda u, headers=None: '{"results":[]}')
    assert cand.source == "crossref"

def test_extract_arxiv_id_forms():
    assert vr.extract_arxiv_id("see arXiv:1802.03426 for details") == "1802.03426"
    assert vr.extract_arxiv_id("10.48550/arXiv.2508.07119") == "2508.07119"
    assert vr.extract_arxiv_id("no id here") is None

def test_parse_bibitem_populates_arxiv_field():
    bi = r"\bibitem{umap} L.~McInnes et al., ``UMAP,'' \emph{arXiv:1802.03426}, 2018."
    assert vr.parse_bibitems(bi)[0].arxiv == "1802.03426"

def test_resolve_arxiv_by_id_returns_candidate():
    ref = vr.Ref(key="pythia", raw="", title="Pythia: A Suite for Analyzing Large Language Models Across Training and Scaling",
                 authors=["Biderman"], year=2023, arxiv="2304.01373")
    cand = vr.resolve_arxiv_by_id(ref, fetch=_stub(FIX / "arxiv_id_pythia.xml"))
    assert cand is not None and cand.identifier_type == "arxiv" and cand.identifier == "2304.01373"
    assert cand.year == 2023 and any("Biderman" in a for a in cand.authors)

def test_resolve_arxiv_by_id_none_when_no_id():
    ref = vr.Ref(key="x", raw="", title="t", arxiv=None)
    assert vr.resolve_arxiv_by_id(ref, fetch=lambda u, headers=None: "<feed></feed>") is None

def test_cascade_uses_arxiv_id_first_and_verifies():
    ref = vr.Ref(key="pythia", raw="", title="Pythia: A Suite for Analyzing Large Language Models Across Training and Scaling",
                 authors=["Biderman"], year=2023, arxiv="2304.01373")
    cand = vr.resolve(ref,
        fetch_arxiv_id=_stub(FIX / "arxiv_id_pythia.xml"),
        fetch_crossref=lambda u, headers=None: '{"message":{"items":[]}}',
        fetch_arxiv=lambda u, headers=None: "<feed></feed>",
        fetch_openalex=lambda u, headers=None: '{"results":[]}')
    assert cand.source == "arxiv" and cand.identifier == "2304.01373"
    assert vr.verdict(ref, cand) == vr.VERIFIED

def test_cascade_arxiv_id_wrong_id_is_caught():
    # anti-hallucination: a human-supplied id that resolves to a DIFFERENT paper must NOT verify
    ref = vr.Ref(key="pythia", raw="", title="Pythia: A Suite for Analyzing Large Language Models",
                 authors=["Biderman"], year=2023, arxiv="1234.56789")
    wrong = "<feed xmlns='http://www.w3.org/2005/Atom'><entry><id>http://arxiv.org/abs/1234.56789</id><title>Some Unrelated Paper About Cats</title><author><name>Nobody</name></author><published>2012-01-01T00:00:00Z</published></entry></feed>"
    cand = vr.resolve_arxiv_by_id(ref, fetch=lambda u, headers=None: wrong)
    assert vr.verdict(ref, cand) == vr.MISMATCH
