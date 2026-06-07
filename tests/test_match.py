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

def test_title_similarity_high_for_near_identical():
    a = "visualizing data using t sne"
    b = "visualizing data using t-sne"
    assert vr.title_similarity(a, b) >= 0.9

def test_title_similarity_low_for_different():
    assert vr.title_similarity("attention is all you need",
                               "diffusion maps") < 0.5
