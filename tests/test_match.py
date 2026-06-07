import verify_refs as vr

def test_module_exposes_verdict_constants():
    assert vr.VERIFIED == "VERIFIED"
    assert vr.MISMATCH == "MISMATCH"
    assert vr.NOT_FOUND == "NOT_FOUND"
