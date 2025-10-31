from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import os
import streamlit as st

from ai_proposal_agent.utils import (
    setup_logging,
    clean_transcript,
    render_markdown_to_html,
    export_to_docx,
    export_to_pdf,
    export_html,
    export_html_string_to_pdf,
    slugify,
)
from storage import save_proposal_json, list_proposals, load_proposal, save_export_files
from ai_proposal_agent.chains import LLMClient, MainProposalChain, SummarizationChain, QualityAuditChain
from validators import validate_inputs, sanity_check
import re

BASE = Path(__file__).parent
LOGS = BASE / "logs" / "app.log"
setup_logging(LOGS)


def _fix_inline_table(body: str) -> str:
    # Detect a collapsed pipe table on one or few lines and expand
    if '|' not in body or ('\n' in body and body.count('\n') > 2):
        return body
    s = body.strip()
    # Heuristic: contains header tokens and many pipes but few newlines
    if s.count('|') >= 8 and 'Milestone' in s and 'Date' in s:
        tokens = [t.strip() for t in s.split('|') if t.strip()]
        rows: list[list[str]] = []
        # find header if present
        if len(tokens) >= 2 and tokens[0].lower().startswith('milestone'):
            header = [tokens[0], tokens[1]]
            # skip separator tokens if they look like dashes
            idx = 2
            if idx + 1 < len(tokens) and set(tokens[idx]).issubset({'-'}):
                idx += 2
            # collect pairs
            pairs = []
            while idx + 1 < len(tokens):
                pairs.append([tokens[idx], tokens[idx + 1]])
                idx += 2
            lines = [f"| {header[0]} | {header[1]} |", "| --- | --- |"] + [f"| {a} | {b} |" for a, b in pairs]
            return "\n".join(lines)
    return body


def _dedupe_headings(title: str, body: str) -> str:
    lines = [ln for ln in (body or '').splitlines()]
    out: list[str] = []
    prev_head: str | None = None
    title_norm = (title or '').strip().lower()
    for ln in lines:
        if re.match(r"^#{1,6}\s+", ln):
            text = re.sub(r"^#{1,6}\s+", "", ln).strip().lower()
            if prev_head is not None and text == prev_head:
                # skip immediate duplicate markdown heading
                continue
            prev_head = text
            out.append(ln)
            continue
        # If a plain line exactly equals the last heading text or the title, drop it
        plain = (ln or '').strip().lower()
        if plain and (plain == prev_head or plain == title_norm):
            continue
        out.append(ln)
    return "\n".join(out).strip()


def _normalize_section(title: str, body: str) -> str:
    # Remove duplicate headings and fix known inline table issues
    b = (body or '').lstrip()
    # If the very first non-empty line equals the title (with or without '#'), drop it
    first = b.splitlines()[:1]
    if first:
        head_txt = re.sub(r"^#{1,6}\s+", "", first[0]).strip().lower()
        if head_txt == (title or '').strip().lower():
            b = "\n".join(b.splitlines()[1:])
    # Then de-duplicate any consecutive headings inside
    b = _dedupe_headings(title, b)
    b = _fix_inline_table(b)
    return b.strip()

st.set_page_config(page_title="AI Proposal Generator", layout="wide")
if "OPENAI_API_KEY" in st.secrets:
    key = str(st.secrets["OPENAI_API_KEY"]).strip()
    os.environ["OPENAI_API_KEY"] = key
if "OPENAI_ORG_ID" in st.secrets:
    os.environ["OPENAI_ORG_ID"] = st.secrets["OPENAI_ORG_ID"]
if "OPENAI_PROJECT" in st.secrets:
    os.environ["OPENAI_PROJECT"] = st.secrets["OPENAI_PROJECT"]

if "proposal" not in st.session_state:
    st.session_state.proposal = {
        "sections": {},
        "markdown_full": "",
        "history": [],
        "email": {"subject": "", "body": "", "summary": "", "pitch": ""},
        "proposal_id": None,
    }

st.sidebar.header("Inputs")
company_name = st.sidebar.text_input("Company Name")
client_name = st.sidebar.text_input("Client Name")
project_title = st.sidebar.text_input("Project Title")
goals = st.sidebar.text_area("Goals", height=120)
budget = st.sidebar.text_input("Budget")
timeline = st.sidebar.text_input("Timeline")
brand_tone = st.sidebar.selectbox("Brand Tone", ["Professional", "Warm", "Bold", "Friendly", "Formal", "Concise"], index=0)
language = st.sidebar.text_input("Preferred Language", value="English")
additional_notes = st.sidebar.text_area("Additional Notes", height=100)
privacy_mode = st.sidebar.checkbox("Privacy Mode (do not save transcripts)", value=False)

logo_file = st.sidebar.file_uploader("Logo (png/jpg)", type=["png", "jpg", "jpeg"])
if logo_file is not None:
    st.session_state.proposal["logo_bytes"] = logo_file.getvalue()
    st.session_state.proposal["logo_ext"] = Path(logo_file.name).suffix.lower().replace('.', '')
transcript_text = st.sidebar.text_area("Call Transcript (paste)", height=150)
transcript_file = st.sidebar.file_uploader("Call Transcript File (txt)", type=["txt"]) 
attachments = st.sidebar.file_uploader("Supporting Docs (pdf/docx/txt)", type=["pdf", "docx", "txt"], accept_multiple_files=True)

st.sidebar.subheader("Advanced")
temperature = st.sidebar.slider("Model Temperature", 0.0, 1.0, 0.3, 0.1)
max_tokens = st.sidebar.slider("Max Tokens", 512, 4000, 2000, 128)
model_name = st.sidebar.text_input("Model", value="gpt-4o-mini")
# Runtime API overrides (helps if secrets file has formatting issues)
manual_key = st.sidebar.text_input("Override API Key (session)", type="password")
manual_org = st.sidebar.text_input("OpenAI Org ID (optional)")
manual_project = st.sidebar.text_input("OpenAI Project (optional)")
if manual_key:
    os.environ["OPENAI_API_KEY"] = manual_key.strip()
if manual_org:
    os.environ["OPENAI_ORG_ID"] = manual_org.strip()
if manual_project:
    os.environ["OPENAI_PROJECT"] = manual_project.strip()
current_key = os.environ.get("OPENAI_API_KEY", "")
if current_key:
    st.sidebar.caption(f"Using API key: {current_key[:6]}…{current_key[-4:]} (masked)")

inputs: Dict[str, Any] = {
    "company_name": company_name,
    "client_name": client_name,
    "project_title": project_title,
    "goals": goals,
    "budget": budget,
    "timeline": timeline,
    "brand_tone": brand_tone,
    "language": language,
    "additional_notes": additional_notes,
}

full_transcript = transcript_text or ""
if transcript_file is not None:
    full_transcript += "\n" + (transcript_file.read().decode("utf-8", errors="ignore"))
full_transcript = clean_transcript(full_transcript)

attachments_summary: List[str] = []
for f in attachments or []:
    attachments_summary.append(f"{f.name} ({f.size} bytes)")
attachments_summary_str = "\n".join(attachments_summary) if attachments_summary else "No supporting docs"

llm = LLMClient(model=model_name, temperature=temperature, max_tokens=max_tokens)
main_chain = MainProposalChain(llm, str(BASE / "prompts"))
sum_chain = SummarizationChain(llm)
qa_chain = QualityAuditChain(llm)

st.title("AI Proposal Generator")
st.write(f"Company: {company_name or '-'} | Client: {client_name or '-'} | Tone: {brand_tone}")

valid, errs = validate_inputs(inputs)
if not valid:
    st.info("Please complete required inputs:")
    for e in errs:
        st.write(f"- {e}")

c1, c2, c3 = st.columns([1,1,1])
with c1:
    gen_btn = st.button("Generate Proposal", disabled=not valid)
with c2:
    qc_btn = st.button("Quality Check", disabled=not bool(st.session_state.proposal["markdown_full"]))
with c3:
    save_btn = st.button("Save Draft", disabled=not bool(st.session_state.proposal["sections"]))

if gen_btn:
    transcript_insights = "No call transcript provided"
    if full_transcript.strip():
        try:
            insights = sum_chain.run(full_transcript)
            bullets: List[str] = []
            for k in ("pain_points","commitments","timeline_hints","budget_cues","quotes"):
                bullets.extend(insights.get(k, []))
            transcript_insights = "- " + "\n- ".join(bullets) if bullets else "Transcript reviewed"
        except Exception as e:
            st.warning(f"Transcript insights unavailable: {e}")
            transcript_insights = "Transcript processed; insights temporarily unavailable."
    context = dict(inputs)
    context.update({"transcript_insights": transcript_insights, "attachments_summary": attachments_summary_str})
    try:
        data = main_chain.generate(context)
        sections = data.get("sections", {})
        # normalize each section (dedupe headings + fix tables)
        norm_sections: Dict[str, str] = {}
        for title, body in sections.items():
            b = _normalize_section(title, body)
            # ensure one heading at top if missing
            first_line = (b or "").lstrip().splitlines()[:1]
            if not (first_line and re.match(r"^#{1,6}\\s+", first_line[0])):
                b = f"# {title}\n\n{b}"
            norm_sections[title] = b
        md_full = "\n\n".join([norm_sections[k] for k in norm_sections.keys()])
        st.session_state.proposal["history"].append({"sections": st.session_state.proposal.get("sections", {}).copy()})
        st.session_state.proposal["sections"] = sections
        st.session_state.proposal["markdown_full"] = md_full
    except Exception as e:
        st.error(f"Generation failed: {e}")

if qc_btn:
    inputs_for_qc = dict(inputs)
    if not privacy_mode:
        inputs_for_qc["transcript"] = full_transcript[:1000]
    audit = qa_chain.run(inputs_for_qc, st.session_state.proposal.get("markdown_full", ""))
    st.session_state.proposal.setdefault("qa", audit)

if save_btn:
    slug = slugify(project_title or f"proposal-{client_name}")
    meta = dict(inputs)
    meta.update({"slug": slug})
    if not privacy_mode and full_transcript:
        meta["transcript_saved"] = True
    pid = save_proposal_json(meta, st.session_state.proposal.get("sections", {}), st.session_state.proposal.get("history", []))
    st.session_state.proposal["proposal_id"] = pid
    st.success(f"Saved proposal {pid}")

st.markdown("---")

st.subheader("Editor")
sections = st.session_state.proposal.get("sections", {})
if sections:
    for name in [
        "Cover Page",
        "Executive Summary",
        "Problem & Opportunity",
        "Proposed Solution",
        "Scope of Work & Deliverables",
        "Timeline & Milestones",
        "Pricing & Payment Terms",
        "ROI / Impact / Metrics",
        "Risks & Mitigations",
        "Terms & Conditions",
        "Next Steps & CTA",
        "Appendix",
    ]:
        current = sections.get(name, "")
        updated = st.text_area(name, value=current, height=200, key=f"edit_{name}")
        sections[name] = updated
    st.session_state.proposal["sections"] = sections
    composed: list[str] = []
    for title, body in sections.items():
        b = _normalize_section(title, body)
        first_line = (b or "").lstrip().splitlines()[:1]
        if not (first_line and re.match(r"^#{1,6}\\s+", first_line[0])):
            b = f"# {title}\n\n{b}"
        composed.append(b)
    st.session_state.proposal["markdown_full"] = "\n\n".join(composed)
else:
    st.info("Generate a proposal to start editing.")

st.subheader("Preview")
html = render_markdown_to_html(st.session_state.proposal.get("markdown_full", ""))
# Inject logo preview at top of the page if available
if st.session_state.proposal.get("logo_bytes"):
    import base64
    ext = st.session_state.proposal.get("logo_ext", "png")
    b64 = base64.b64encode(st.session_state.proposal["logo_bytes"]).decode("ascii")
    logo_img = f"<img src='data:image/{ext};base64,{b64}' style='height:60px;margin-bottom:16px'/>"
    html = html.replace("<div class='doc-page'>", f"<div class='doc-page'>{logo_img}", 1)
st.components.v1.html(html, height=800, scrolling=True)

st.markdown("---")

colA, colB = st.columns([1,1])
with colA:
    st.subheader("Section Controls")
    target_section = st.selectbox("Section", [
        "Executive Summary",
        "Problem & Opportunity",
        "Proposed Solution",
        "Scope of Work & Deliverables",
        "Timeline & Milestones",
        "Pricing & Payment Terms",
        "ROI / Impact / Metrics",
        "Risks & Mitigations",
        "Terms & Conditions",
        "Next Steps & CTA",
        "Appendix",
    ])
    if st.button("Regenerate Section", disabled=not bool(st.session_state.proposal.get("sections"))):
        context = dict(inputs)
        context.update({
            "brand_tone": brand_tone,
            "goals": goals,
            "budget": budget,
            "timeline": timeline,
            "transcript_insights": "Derived from prior",
        })
        regenerated = main_chain.regenerate_section(target_section, context)
        st.session_state.proposal["history"].append({"section": target_section, "previous": st.session_state.proposal["sections"].get(target_section, "")})
        st.session_state.proposal["sections"][target_section] = regenerated
        # Normalize all sections and ensure a single heading per section
        normalized_blocks: list[str] = []
        for k, v in st.session_state.proposal["sections"].items():
            b = _normalize_section(k, v)
            first_line = (b or "").lstrip().splitlines()[:1]
            if not (first_line and re.match(r"^#{1,6}\s+", first_line[0])):
                b = f"# {k}\n\n{b}"
            normalized_blocks.append(b)
        st.session_state.proposal["markdown_full"] = "\n\n".join(normalized_blocks)
        st.success(f"Regenerated {target_section}")

with colB:
    st.subheader("Quality")
    audit: Optional[Dict[str, Any]] = st.session_state.proposal.get("qa")
    if audit:
        st.metric("Quality Grade", audit.get("grade", 0))
        st.write("Suggestions:")
        for s in audit.get("suggestions", []):
            st.write(f"- {s}")
    else:
        st.info("Run Quality Check to see suggestions.")

st.markdown("---")

st.subheader("Copy to Google Docs")
disabled_export = not bool(st.session_state.proposal.get("sections"))
if not disabled_export:
    # Build exact HTML (including logo) used in the preview
    html_preview = render_markdown_to_html(st.session_state.proposal.get("markdown_full", ""))
    if st.session_state.proposal.get("logo_bytes"):
        import base64
        ext = st.session_state.proposal.get("logo_ext", "png")
        b64 = base64.b64encode(st.session_state.proposal["logo_bytes"]).decode("ascii")
        logo_img = f"<img src='data:image/{ext};base64,{b64}' style='height:60px;margin-bottom:16px'/>"
        html_preview = html_preview.replace("<div class='doc-page'>", f"<div class='doc-page'>{logo_img}", 1)
    import json as _json
    payload = _json.dumps({"html": html_preview})
    st.components.v1.html(
        f"""
        <button id='copyBtn' style='padding:10px 14px;border-radius:6px;border:1px solid #e5e7eb;background:#0b3d91;color:#fff;cursor:pointer;'>Copy to clipboard</button>
        <span id='msg' style='margin-left:10px;color:#16a34a;'></span>
        <script>
        const data = {payload};
        const btn = document.getElementById('copyBtn');
        const msg = document.getElementById('msg');
        btn.onclick = async () => {{
          try {{
            const blob = new Blob([data.html], {{type: 'text/html'}});
            const item = new ClipboardItem({{'text/html': blob}});
            await navigator.clipboard.write([item]);
            msg.textContent = 'Copied! Open Google Docs and paste (Ctrl/Cmd+V).';
          }} catch (e) {{
            try {{
              await navigator.clipboard.writeText(data.html);
              msg.textContent = 'Copied as plain text. If styling is missing, try another browser.';
            }} catch (err) {{
              msg.textContent = 'Copy failed. Allow clipboard permissions and retry.';
            }}
          }}
        }};
        </script>
        """.replace("{payload}", payload), height=80)
else:
    st.info("Generate a proposal to enable copying.")

st.markdown("---")

if st.button("Create Email", disabled=not bool(st.session_state.proposal.get("sections"))):
        prompt = (
            "Create a JSON with keys subject, body, summary, pitch for this proposal. "
            "Subject 7-10 words. Body 2-4 short paragraphs. One-sentence elevator pitch. One-paragraph summary.\n"
            f"Company: {company_name}\nClient: {client_name}\nTitle: {project_title}\nTone: {brand_tone}\n" 
        )
        resp = llm.generate(prompt)
        try:
            email = json.loads(resp)
        except Exception:
            email = {"subject": f"Proposal: {project_title}", "body": "Please find attached.", "summary": "", "pitch": ""}
        st.session_state.proposal["email"] = email
        st.success("Email ready below")

st.subheader("Email (Copy-Paste)")
email = st.session_state.proposal.get("email", {})
st.text_input("Subject", value=email.get("subject", ""))
st.text_area("Body", value=email.get("body", ""), height=160)
st.text_area("One-page summary", value=email.get("summary", ""), height=140)
st.text_input("Elevator pitch", value=email.get("pitch", ""))

st.markdown("---")

st.subheader("Saved Proposals")
items = list_proposals()
if items:
    sel = st.selectbox("Open", options=[i[0] for i in items])
    if st.button("Load", disabled=not bool(sel)):
        data = load_proposal(sel)
        st.session_state.proposal["sections"] = data.get("sections", {})
        # Normalize loaded content to avoid duplicate headings
        blocks: list[str] = []
        for k, v in data.get("sections", {}).items():
            b = _normalize_section(k, v)
            first_line = (b or "").lstrip().splitlines()[:1]
            if not (first_line and re.match(r"^#{1,6}\s+", first_line[0])):
                b = f"# {k}\n\n{b}"
            blocks.append(b)
        st.session_state.proposal["markdown_full"] = "\n\n".join(blocks)
        st.session_state.proposal["proposal_id"] = data.get("id")
        st.success(f"Loaded {sel}")
else:
    st.write("No saved proposals yet.")
