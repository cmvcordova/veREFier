import verify_refs as vr

def test_module_exposes_verdict_constants():
    assert vr.VERIFIED == "VERIFIED"
    assert vr.MISMATCH == "MISMATCH"
    assert vr.NOT_FOUND == "NOT_FOUND"

def test_normalize_title_strips_latex_and_punctuation():
    assert vr.normalize_title(r"{UMAP}: Uniform \emph{Manifold} Approximation!") == \
        "umap uniform manifold approximation"

def test_normalize_surname_accent_folds():
    assert vr.normalize_surname("Böhm") == "bohm"
    assert vr.normalize_surname("van der Maaten") == "van der maaten"

def test_surnames_bibtex_family_comma_given_order():
    # BibTeX "Family, Given" -> surname is BEFORE the comma, not the last token
    assert vr._surnames(["Bhaskar, Dhananjay"]) == {"bhaskar"}
    assert vr._surnames(["Zelnik-Manor, Lihi"]) == {"manor"}
    assert vr._surnames(["van der Maaten, Laurens"]) == {"maaten"}

def test_surnames_given_family_order_unchanged():
    # no comma -> last token (API family fields / "Given Family" lists)
    assert vr._surnames(["Dhananjay Bhaskar"]) == {"bhaskar"}
    assert vr._surnames(["Bhaskar"]) == {"bhaskar"}

def test_author_overlap_across_comma_and_bare_family_formats():
    # ref in BibTeX "Family, Given" must overlap a candidate's bare family names
    ref_authors = ["Bhaskar, Dhananjay", "Krishnaswamy, Smita"]
    cand_authors = ["Bhaskar", "Krishnaswamy"]
    assert vr._author_overlap(ref_authors, cand_authors)

def test_verdict_verified_with_bibtex_comma_authors():
    ref = _ref(title="Diffusion maps", authors=["Coifman, Ronald R.", "Lafon, St\\'ephane"], year=2006)
    cand = _cand(title="Diffusion maps", authors=["Coifman", "Lafon"], year=2006)
    assert vr.verdict(ref, cand) == vr.VERIFIED

def test_title_similarity_high_for_near_identical():
    a = "visualizing data using t sne"
    b = "visualizing data using t-sne"
    assert vr.title_similarity(a, b) >= 0.9

def test_title_similarity_low_for_different():
    assert vr.title_similarity("attention is all you need",
                               "diffusion maps") < 0.5

def _ref(**kw):
    base = dict(key="x", raw="", title="", authors=[], year=None, doi=None)
    base.update(kw); return vr.Ref(**base)

def _cand(**kw):
    base = dict(title="", authors=[], year=None, identifier_type="doi",
                identifier="10.x/y", source="crossref")
    base.update(kw); return vr.Candidate(**base)

def test_verdict_verified_on_full_match():
    ref = _ref(title="Visualizing Data using t-SNE",
               authors=["van der Maaten", "Hinton"], year=2008)
    cand = _cand(title="Visualizing Data using t-SNE",
                 authors=["van der Maaten", "Hinton"], year=2008)
    assert vr.verdict(ref, cand) == vr.VERIFIED

def test_verdict_mismatch_on_wrong_author():
    ref = _ref(title="Diffusion maps", authors=["Smith"], year=2006)
    cand = _cand(title="Diffusion maps", authors=["Coifman", "Lafon"], year=2006)
    assert vr.verdict(ref, cand) == vr.MISMATCH

def test_verdict_mismatch_on_wrong_year():
    ref = _ref(title="Diffusion maps", authors=["Coifman"], year=1999)
    cand = _cand(title="Diffusion maps", authors=["Coifman"], year=2006)
    assert vr.verdict(ref, cand) == vr.MISMATCH

def test_verdict_year_within_one_ok():
    ref = _ref(title="Pythia", authors=["Biderman"], year=2023)
    cand = _cand(title="Pythia", authors=["Biderman"], year=2022)
    assert vr.verdict(ref, cand) == vr.VERIFIED

def test_verdict_not_found_when_no_candidate():
    ref = _ref(title="A totally fabricated paper", authors=["Nobody"], year=2020)
    assert vr.verdict(ref, None) == vr.NOT_FOUND

def test_verdict_mismatch_on_wrong_title_same_doi():
    # the anti-hallucination case: a DOI that resolves to a DIFFERENT paper
    ref = _ref(title="Attention is all you need", authors=["Vaswani"], year=2017)
    cand = _cand(title="Diffusion maps", authors=["Vaswani"], year=2017)
    assert vr.verdict(ref, cand) == vr.MISMATCH

def test_verdict_verified_title_only_when_ref_has_no_authors():
    ref = _ref(title="Visualizing Data using t-SNE", authors=[], year=None)
    cand = _cand(title="Visualizing Data using t-SNE",
                 authors=["van der Maaten", "Hinton"], year=2008)
    assert vr.verdict(ref, cand) == vr.VERIFIED

def test_verdict_still_mismatch_when_ref_authors_present_and_wrong():
    ref = _ref(title="Diffusion maps", authors=["Nobody"], year=2006)
    cand = _cand(title="Diffusion maps", authors=["Coifman", "Lafon"], year=2006)
    assert vr.verdict(ref, cand) == vr.MISMATCH

def test_verdict_no_crash_when_author_normalizes_to_empty():
    # an author token that is all LaTeX/punctuation (e.g. "{\&}") survives the
    # truthiness filter but normalizes to "" -> .split()[-1] must not IndexError
    ref = _ref(title="Diffusion maps", authors=[r"\&"], year=2006)
    cand = _cand(title="Diffusion maps", authors=["Coifman"], year=2006)
    assert vr.verdict(ref, cand) == vr.MISMATCH
