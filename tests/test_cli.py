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
