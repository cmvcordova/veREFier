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
