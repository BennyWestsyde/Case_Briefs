from DataClasses import CaseBriefData, Label, Opinion, Subject
from pathlib import Path

import re

from protocols import CitationResolver


def tex_escape(input: str) -> str:
    """Escape special characters for LaTeX."""
    replacements: dict[str, str | int | None] = {
        "{": "\\{",
        "}": "\\}",
        "$": "\\$",
        "%": "\\%",
        "#": "\\#",
        "_": "\\_",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
        "&": "\\&",
    }
    return (
        str.translate(input, str.maketrans(replacements))
        .replace("\n", r"\\" + "\n")
        .replace(". ", r".\ ")
        .replace("...", r"\ldots")
    )


def tex_unescape(input: str) -> str:
    """Unescape special characters for LaTeX (inverse of tex_escape)."""
    s = input
    # First undo multi-char macros
    s = s.replace(r"\textasciitilde{}", "~")
    s = s.replace(r"\textasciicircum{}", "^")
    # Then undo single-char escapes
    s = s.replace(r"\{", "{")
    s = s.replace(r"\}", "}")
    s = s.replace(r"\$", "$")
    s = s.replace(r"\%", "%")
    s = s.replace(r"\#", "#")
    s = s.replace(r"\_", "_")
    s = s.replace(r"\&", "&")
    # Finally, line breaks and sequences
    s = s.replace(r"\\" + "\n", "\n")
    s = s.replace(r".\ ", ". ")
    s = s.replace(r"\ldots", "...")
    return s


class RegexLatexCodec:
    def __init__(self, master_tex_path: Path | None = None):
        """Initialize codec with the master LaTeX document path for dynamic referencing"""
        self.master_tex_path = master_tex_path

    CITE_RX = re.compile(r"CITE\((.*?)\)")
    CITE_TX = re.compile(r"\\hyperref\[case:(.*?)\]\{\\textit\{(.*?)\}\}")
    CASE_TX = re.compile(
        r"\\NewBrief{subject=\{(.*?)\},\n\s*plaintiff=\{(.*?)\},\n\s*defendant=\{(.*?)\},\n\s*citation=\{(.*?)\},\n\s*course=\{(.*?)\},\n\s*facts=\{(.*?)\},\n\s*procedure=\{(.*?)\},\n\s*issue=\{(.*?)\},\n\s*holding=\{(.*?)\},\n\s*principle=\{(.*?)\},\n\s*reasoning=\{(.*?)\},\n\s*opinions=\{(.*?)\},\n\s*label=\{case:(.*?)\},\n\s*notes=\{(.*?)\}",
        re.DOTALL,
    )

    def _replace_cites(self, text: str, cite: CitationResolver) -> str:
        return self.CITE_RX.sub(lambda m: cite.cite_label(m.group(1)), text)

    def _replace_cites_back(self, text: str) -> str:
        return re.sub(self.CITE_TX, r"CITE(\1)", text)

    def _get_master_tex_reference(self, output_file_path: Path) -> str:
        """Calculate the correct relative path to the master LaTeX file"""
        if self.master_tex_path is None:
            # Fallback to hardcoded path if not set
            return "../tex_src/CaseBriefs.tex"

        try:
            # Calculate relative path from the output file to the master file
            relative_path = self.master_tex_path.relative_to(output_file_path.parent)
            return str(relative_path)
        except ValueError:
            # If relative path calculation fails, use absolute path approach
            try:
                # Try to create a relative path using os.path.relpath
                import os

                rel_path = os.path.relpath(
                    str(self.master_tex_path), str(output_file_path.parent)
                )
                return rel_path
            except Exception:
                # Ultimate fallback
                return str(self.master_tex_path)

    def to_tex(
        self,
        data: CaseBriefData,
        cite: CitationResolver,
        output_file_path: Path | None = None,
    ) -> str:
        subjects = ", ".join(str(s) for s in data.subjects)
        opinions = "\n".join(f"{op.author}: {op.text}" for op in data.opinions)

        def esc_and_cite(s: str) -> str:
            return self._replace_cites(tex_escape(s), cite)

        # Determine the correct path to the master document
        if output_file_path is not None and self.master_tex_path is not None:
            master_ref = self._get_master_tex_reference(output_file_path)
        else:
            master_ref = "../tex_src/CaseBriefs.tex"  # Default relative path from Cases/ to tex_src/

        return f"""\
\\documentclass[{master_ref}]{{subfiles}}
\\usepackage{{lawbrief}}
\\begin{{document}}
\\NewBrief{{subject={{{subjects}}},
  plaintiff={{{esc_and_cite(data.plaintiff)}}},
  defendant={{{esc_and_cite(data.defendant)}}},
  citation={{{esc_and_cite(data.citation)}}},
  course={{{data.course}}},
  facts={{{esc_and_cite(data.facts)}}},
  procedure={{{esc_and_cite(data.procedure)}}},
  issue={{{esc_and_cite(data.issue)}}},
  holding={{{esc_and_cite(data.holding)}}},
  principle={{{esc_and_cite(data.principle)}}},
  reasoning={{{esc_and_cite(data.reasoning)}}},
  opinions={{{esc_and_cite(opinions)}}},
  label={{case:{data.label}}},
  notes={{{esc_and_cite(data.notes)}}}
}}
\\end{{document}}
""".strip()

    def from_tex(self, tex: str) -> CaseBriefData:
        """Convert LaTeX content back to a CaseBrief object."""
        match = self.CASE_TX.search(tex)

        def unesc_and_recite(s: str):
            return tex_unescape(self._replace_cites_back(tex_unescape(s)))

        if match:
            subjects = [
                Subject(s.strip()) for s in match.group(1).split(",") if s.strip()
            ]
            plaintiff = tex_unescape(match.group(2).strip())
            defendant = tex_unescape(match.group(3).strip())
            citation = tex_unescape(match.group(4).strip())
            course = match.group(5).strip()
            facts = unesc_and_recite(match.group(6).strip())
            procedure = unesc_and_recite(match.group(7).strip())
            issue = unesc_and_recite(
                match.group(8).strip()
            )  # .replace(r'\\'+'\n', '\n').replace(r"\\$", "$")
            holding = tex_unescape(match.group(9).strip())
            principle = tex_unescape(match.group(10).strip())
            reasoning = tex_unescape(match.group(11).strip())
            opinions = [
                Opinion(
                    o.strip().split(":")[0].strip(), o.strip().split(":")[1].strip()
                )
                for o in unesc_and_recite(match.group(12)).splitlines()
                if o.strip()
            ]
            label = Label(match.group(13).strip())
            notes = unesc_and_recite(match.group(14).strip())
        else:
            raise RuntimeError(
                f"Failed to parse case brief. The file may not be in the correct format."
            )

        return CaseBriefData(
            subjects=subjects,
            plaintiff=plaintiff,
            defendant=defendant,
            citation=citation,
            course=course,
            facts=facts,
            procedure=procedure,
            issue=issue,
            holding=holding,
            principle=principle,
            reasoning=reasoning,
            opinions=opinions,
            label=label,
            notes=notes,
        )
