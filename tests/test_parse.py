import verify_refs as vr

BIB = r"""
@article{tsne, title={Visualizing Data using {t-SNE}},
  author={van der Maaten, Laurens and Hinton, Geoffrey}, year={2008}, doi={10.5555/x}}
"""

BIBITEM = r"\bibitem{phate} K.~R. Moon et al., ``Visualizing structure,'' \emph{Nat.}, 2019."

def test_parse_bib_extracts_fields():
    refs = vr.parse_bib(BIB)
    assert len(refs) == 1
    r = refs[0]
    assert r.key == "tsne"
    assert "Visualizing Data using" in r.title
    assert any("Maaten" in a for a in r.authors)
    assert r.year == 2008
    assert r.doi == "10.5555/x"

COMMENTED_BIB = r"""
% === first group ===
@article{a, title={First Paper}, author={Smith, Jane}, year={2001}, doi={10.1/a}}

% === second group ===
@article{b, title={Second Paper}, author={Doe, John}, year={2002}, doi={10.2/b}}
@inproceedings{c, title={Third Paper}, author={Roe, Amy}, year={2003}}
"""

def test_parse_bib_not_broken_by_comments_between_entries():
    # regression: a `% comment` between entries must NOT make the parser swallow/drop
    # the next entry, nor mis-pair a key with a later entry's title
    refs = vr.parse_bib(COMMENTED_BIB)
    by_key = {r.key: r for r in refs}
    assert set(by_key) == {"a", "b", "c"}            # none dropped
    assert by_key["a"].title == "First Paper"        # key not mis-paired with a later title
    assert by_key["b"].title == "Second Paper"
    assert by_key["c"].title == "Third Paper"
    assert by_key["a"].doi == "10.1/a" and by_key["b"].doi == "10.2/b"

def test_parse_bib_skips_string_and_handles_at_in_comment():
    bib = ("% see foo@example.com for contact\n"
           "@string{nat = {Nature}}\n"
           "@article{x, title={Real Paper}, author={A, B}, year={2020}, doi={10.x/y}}\n")
    refs = vr.parse_bib(bib)
    assert [r.key for r in refs] == ["x"]
    assert refs[0].title == "Real Paper"

def test_parse_bibitems_extracts_key_and_raw():
    refs = vr.parse_bibitems(BIBITEM)
    assert len(refs) == 1
    assert refs[0].key == "phate"
    assert refs[0].year == 2019
    assert "Visualizing structure" in refs[0].raw

MULTILINE = (r"\bibitem{umap} L.~McInnes, J.~Healy, J.~Melville, ``UMAP: Uniform manifold "
             "approximation and\n  projection,'' \\emph{arXiv:1802.03426}, 2018.")

def test_parse_bibitem_title_spans_linebreak():
    refs = vr.parse_bibitems(MULTILINE)
    assert len(refs) == 1
    assert refs[0].title == "UMAP: Uniform manifold approximation and projection"
    assert refs[0].year == 2018


def test_parse_list_one_per_line():
    refs = vr.parse_list("Diffusion maps\nAttention is all you need\n")
    assert [r.title for r in refs] == ["Diffusion maps", "Attention is all you need"]

def test_detect_format():
    assert vr.detect_format(BIB) == "bib"
    assert vr.detect_format(BIBITEM) == "bibitem"
    assert vr.detect_format("just a title line") == "list"


def test_parse_bibitem_extracts_author_surnames():
    bi = (r"\bibitem{umap} L.~McInnes, J.~Healy, J.~Melville, "
          "``UMAP: Uniform manifold approximation and projection,'' \\emph{arXiv:1802.03426}, 2018.")
    refs = vr.parse_bibitems(bi)
    surs = " ".join(refs[0].authors).lower()
    assert "mcinnes" in surs and "healy" in surs and "melville" in surs


def test_parse_bibitem_authors_handle_etal_and_initials():
    bi = r"\bibitem{phate} K.~R. Moon et al., ``Visualizing structure,'' \emph{Nat.}, 2019."
    refs = vr.parse_bibitems(bi)
    assert any("moon" in a.lower() for a in refs[0].authors)


def test_parse_bibitem_authors_and_separator():
    bi = r"\bibitem{jl} W.~B. Johnson and J.~Lindenstrauss, ``Extensions,'' \emph{Contemp. Math.}, 1984."
    refs = vr.parse_bibitems(bi)
    surs = " ".join(refs[0].authors).lower()
    assert "johnson" in surs and "lindenstrauss" in surs


def test_umap_bibitem_rejects_rpackage_author():
    bi = (r"\bibitem{umap} L.~McInnes, J.~Healy, J.~Melville, "
          "``UMAP: Uniform Manifold Approximation and Projection,'' \\emph{arXiv:1802.03426}, 2018.")
    ref = vr.parse_bibitems(bi)[0]
    rpkg = vr.Candidate(title="umap: Uniform Manifold Approximation and Projection",
                        authors=["Konopka"], year=2018, identifier_type="doi",
                        identifier="10.32614/cran.package.umap", source="crossref")
    paper = vr.Candidate(title="UMAP: Uniform Manifold Approximation and Projection",
                         authors=["McInnes", "Healy", "Melville"], year=2018,
                         identifier_type="arxiv", identifier="1802.03426", source="arxiv")
    assert vr.verdict(ref, rpkg) == vr.MISMATCH
    assert vr.verdict(ref, paper) == vr.VERIFIED
