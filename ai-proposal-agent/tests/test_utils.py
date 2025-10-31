from __future__ import annotations
from ai_proposal_agent import utils  # type: ignore
from pathlib import Path

def test_slugify():
    assert utils.slugify("Hello World!").startswith("hello-world")


def test_clean_transcript():
    txt = " a\n\n b \n"
    assert utils.clean_transcript(txt) == "a\nb"


def test_export_docx_bytes(tmp_path: Path):
    content = {"Executive Summary": "Hello", "Pricing & Payment Terms": "$$$"}
    meta = {"project_title": "X", "company_name": "Co", "client_name": "Cli"}
    data = utils.export_to_docx(content, meta, None)
    p = tmp_path / "x.docx"
    p.write_bytes(data)
    assert p.exists() and p.stat().st_size > 0


def test_export_pdf_bytes(tmp_path: Path):
    content = {"A": "Alpha", "B": "Beta"}
    meta = {"project_title": "X", "company_name": "Co", "client_name": "Cli"}
    data = utils.export_to_pdf(content, meta)
    p = tmp_path / "x.pdf"
    p.write_bytes(data)
    assert p.exists() and p.stat().st_size > 0
