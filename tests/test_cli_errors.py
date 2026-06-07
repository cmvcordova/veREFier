import verify_refs as vr

def test_main_missing_file_returns_2_no_traceback(capsys):
    rc = vr.main(["/no/such/path/refs.bib"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error" in err.lower()
