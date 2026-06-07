import verify_refs as vr

def test_check_ref_builds_result_verified():
    ref = vr.Ref(key="tsne", raw="", title="Visualizing Data using t-SNE",
                 authors=["van der Maaten"], year=2008)
    cand = vr.Candidate(title="Visualizing Data using t-SNE", authors=["van der Maaten"],
                        year=2008, identifier_type="doi", identifier="10.5555/x", source="crossref")
    res = vr.check_ref(ref, resolver=lambda r: cand)
    assert res["verdict"] == vr.VERIFIED
    assert res["identifier"] == "10.5555/x"

def test_emit_bib_includes_only_verified():
    results = [
        {"key": "a", "verdict": vr.VERIFIED, "identifier_type": "doi",
         "identifier": "10.1/x", "title": "T A", "authors": ["X"], "year": 2020},
        {"key": "b", "verdict": vr.NOT_FOUND, "identifier_type": None,
         "identifier": None, "title": "Fake", "authors": [], "year": None},
    ]
    bib = vr.emit_bib(results)
    assert "10.1/x" in bib and "@misc{a" in bib
    assert "fake" not in bib.lower()

def test_emit_report_lists_all_verdicts():
    results = [
        {"key": "a", "verdict": vr.VERIFIED, "identifier": "10.1/x", "source": "crossref",
         "matched_title": "T A"},
        {"key": "b", "verdict": vr.MISMATCH, "identifier": "10.2/y", "source": "crossref",
         "matched_title": "Different Paper"},
    ]
    rep = vr.emit_report(results)
    assert "VERIFIED" in rep and "MISMATCH" in rep and "Different Paper" in rep

def test_emit_bib_arxiv_uses_eprint():
    results = [{"key": "u", "verdict": vr.VERIFIED, "identifier_type": "arxiv",
               "identifier": "1802.03426", "title": "UMAP", "authors": ["McInnes"], "year": 2018}]
    assert "eprint = {1802.03426}" in vr.emit_bib(results)

def test_emit_bib_url_tier_uses_url_field():
    results = [{"key": "tsne", "verdict": vr.VERIFIED, "identifier_type": "url",
               "identifier": "https://www.jmlr.org/papers/v9/vandermaaten08a.html",
               "title": "Visualizing Data using t-SNE", "authors": ["van der Maaten"], "year": 2008}]
    bib = vr.emit_bib(results)
    assert "url = {https://www.jmlr.org/papers/v9/vandermaaten08a.html}" in bib
    assert "doi" not in bib and "eprint" not in bib

def test_check_ref_carries_strength():
    ref = vr.Ref(key="tsne", raw="", title="Visualizing Data using t-SNE")
    cand = vr.Candidate(title="Visualizing Data using t-SNE", authors=[], year=2008,
                        identifier_type="url", identifier="https://x", source="openalex")
    res = vr.check_ref(ref, resolver=lambda r: cand)
    assert res["strength"] == 1
    assert res["identifier_type"] == "url"

def test_emit_report_shows_url_tier_and_tier_counts():
    results = [
        {"key": "tsne", "verdict": vr.VERIFIED, "identifier_type": "url", "strength": 1,
         "identifier": "https://x", "source": "openalex", "matched_title": "t-SNE"},
        {"key": "umap", "verdict": vr.VERIFIED, "identifier_type": "doi", "strength": 3,
         "identifier": "10.1/x", "source": "crossref", "matched_title": "UMAP"},
    ]
    rep = vr.emit_report(results)
    assert "[url]" in rep and "[doi]" in rep
    assert "doi 1" in rep and "url 1" in rep
