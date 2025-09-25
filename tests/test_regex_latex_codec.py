import re
from pathlib import Path

import pytest

from DataClasses import Label
from RegexLatexCodec import RegexLatexCodec, tex_escape, tex_unescape


class DummyCiter:
    def __init__(self):
        self.calls = []

    def cite_label(self, label: str) -> str:
        self.calls.append(label)
        return "\\hyperref[case:{0}]{{\\textit{{{0}}}}}".format(label)


def test_tex_escape_unescape_idempotent():
    # avoid HTML-like tokens to purely test LaTeX escaping/unescaping
    s = "text with {curly} $dollar$ %percent% #hash _under ~tilde ^caret & and new\nline"
    esc = tex_escape(s)
    unesc = tex_unescape(esc)
    assert s == unesc.replace("\\\\\n", "\n")


def test_to_tex_includes_master_relative_path(tmp_tree, sample_brief):
    codec = RegexLatexCodec(master_tex_path=tmp_tree["master"])  # write/tex_src/CaseBriefs.tex
    out_path = tmp_tree["write"] / "Cases" / f"{sample_brief.filename}.tex"
    dummy = DummyCiter()
    tex = codec.to_tex(sample_brief, cite=dummy, output_file_path=out_path)

    # Ensure correct relative reference to master appears
    assert re.search(r"\\documentclass\[\.\./tex_src/CaseBriefs\.tex\]\{subfiles\}", tex)

    # ensure cites were replaced and escaped
    assert "CITE(" not in tex
    assert "\\hyperref[case:AnotherCase]{\\textit{AnotherCase}}" in tex
    assert "\\$symbols\\$" in tex
    assert "\\%percent\\%" in tex


def test_round_trip_from_tex(tmp_tree, sample_brief):
    codec = RegexLatexCodec(master_tex_path=tmp_tree["master"])  # used for path only
    out_path = tmp_tree["write"] / "Cases" / f"{sample_brief.filename}.tex"
    dummy = DummyCiter()
    tex = codec.to_tex(sample_brief, cite=dummy, output_file_path=out_path)
    obj = codec.from_tex(tex)

    assert obj.label == sample_brief.label
    assert obj.plaintiff == sample_brief.plaintiff
    assert obj.defendant == sample_brief.defendant
    assert obj.citation == sample_brief.citation
    assert obj.course == sample_brief.course
    assert obj.facts.startswith("Alice sued Bob.")  # after unescape and recite
    assert any(s.name == "Torts" for s in obj.subjects)
    assert any(op.author == "Judge A" for op in obj.opinions)


def test_from_tex_invalid_raises():
    codec = RegexLatexCodec()
    with pytest.raises(RuntimeError):
        codec.from_tex("\\documentclass{article}\n\\begin{document}\nNo Brief Here\n\\end{document}")
