from __future__ import annotations
import json
import time
import logging
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around LangChain ChatOpenAI with retry/backoff."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.3, max_tokens: int = 2000):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        # ChatOpenAI from langchain_openai supports OpenAI project keys with modern OpenAI>=1.x
        self._llm = ChatOpenAI(model=model, temperature=temperature, max_tokens=max_tokens)

    def _normalize(self, text: str) -> str:
        table = {
            0x2018: ord("'"),  # ‘
            0x2019: ord("'"),  # ’
            0x201C: ord('"'),  # “
            0x201D: ord('"'),  # ”
            0x2013: ord('-'),   # –
            0x2014: ord('-'),   # —
            0x2026: ord('.'),   # … -> . (single dot repeated later)
        }
        normalized = (text or "").translate(table).replace("…", "...")
        try:
            return normalized.encode("utf-8", errors="ignore").decode("utf-8")
        except Exception:
            return normalized

    def generate(self, prompt: str, retries: int = 3, backoff: float = 1.0) -> str:
        last_err: Exception | None = None
        for i in range(retries):
            try:
                safe_prompt = self._normalize(prompt)
                resp = self._llm.invoke(safe_prompt)
                # resp is an AIMessage
                return getattr(resp, "content", str(resp))
            except Exception as e:  # pragma: no cover
                last_err = e
                logger.warning("LLM error (%s/%s): %s", i + 1, retries, e)
                time.sleep(backoff * (i + 1))
        msg = f"LLM generation failed after retries: {last_err}"
        raise RuntimeError(msg)


class SummarizationChain:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.template = PromptTemplate.from_template(
            """
Extract key insights from the call transcript. Return JSON with keys: pain_points (list), commitments (list), timeline_hints (list), budget_cues (list), quotes (list of short quotes).
Transcript:\n{transcript}
"""
        )

    def run(self, transcript: str) -> Dict[str, List[str]]:
        prompt = self.template.format(transcript=transcript)
        out = self.llm.generate(prompt)
        try:
            data = json.loads(out)
            for k in ["pain_points", "commitments", "timeline_hints", "budget_cues", "quotes"]:
                data.setdefault(k, [])
            return data
        except Exception:
            return {"pain_points": [], "commitments": [], "timeline_hints": [], "budget_cues": [], "quotes": []}


class SectionChain:
    def __init__(self, llm: LLMClient, prompt_text: str):
        self.llm = llm
        self.template = PromptTemplate.from_template(prompt_text)

    def run(self, context: Dict[str, Any]) -> str:
        return self.llm.generate(self.template.format(**context))


class QualityAuditChain:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.template = PromptTemplate.from_template(
            """
You are a proposal QA expert. Review the proposal markdown and inputs for clarity, consistency, tone, and grammar.
Return ONLY JSON with keys: grade (0-100), summary (string), suggestions (list of strings), apply_notes (list of inline fixes as markdown search->replace suggestions).

Inputs JSON:\n{inputs_json}
Proposal Markdown:\n{proposal_md}
"""
        )

    def run(self, inputs: Dict[str, Any], proposal_md: str) -> Dict[str, Any]:
        prompt = self.template.format(inputs_json=json.dumps(inputs), proposal_md=proposal_md)
        out = self.llm.generate(prompt)
        try:
            return json.loads(out)
        except Exception:
            return {"grade": 70, "summary": "Basic check complete.", "suggestions": [], "apply_notes": []}


class MainProposalChain:
    def __init__(self, llm: LLMClient, prompts_dir: str):
        self.llm = llm
        self.prompts_dir = prompts_dir
        with open(f"{prompts_dir}/main_prompt.txt", "r", encoding="utf-8") as f:
            self.main_template = f.read()
        self.section_prompts = {
            "Executive Summary": self._read("sections/executive_summary.txt"),
            "Problem & Opportunity": self._read("sections/problem_solution.txt"),
            "Scope of Work & Deliverables": self._read("sections/scope_of_work.txt"),
            "Timeline & Milestones": self._read("sections/timeline.txt"),
            "Pricing & Payment Terms": self._read("sections/pricing.txt"),
            "Terms & Conditions": self._read("sections/terms.txt"),
        }

    def _read(self, rel: str) -> str:
        with open(f"{self.prompts_dir}/{rel}", "r", encoding="utf-8") as f:
            return f.read()

    def generate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self.main_template.format(**inputs)
        out = self.llm.generate(prompt)
        try:
            data = self._ensure_json(out)
            if not isinstance(data, dict) or not data.get("sections"):
                raise ValueError("empty_or_invalid")
            return data
        except Exception:
            # Fallback: synthesize sections one-by-one
            sections_order = [
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
            ]
            built: Dict[str, str] = {}
            for name in sections_order:
                try:
                    built[name] = self.regenerate_section(name, inputs)
                except Exception:
                    built[name] = ""
            md_full = "\n\n".join([f"# {k}\n\n{v}" for k, v in built.items()])
            return {
                "title": inputs.get("project_title", "Proposal"),
                "metadata": {k: inputs.get(k) for k in ["company_name","client_name","brand_tone","language"]},
                "sections": built,
                "markdown_full": md_full,
            }

    def regenerate_section(self, section_name: str, context: Dict[str, Any]) -> str:
        prompt_text = self.section_prompts.get(section_name) or f"Write the section '{section_name}' in markdown. Tone: {{brand_tone}}"
        return SectionChain(self.llm, prompt_text).run(context)

    def _ensure_json(self, text: str) -> Dict[str, Any]:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            # strip markdown fences if present
            cleaned = cleaned.strip("`")
            # remove possible json hint
            cleaned = cleaned.replace("json\n", "").strip()
        try:
            if not cleaned:
                raise ValueError("empty")
            return json.loads(cleaned)
        except Exception:
            fixer = PromptTemplate.from_template(
                """
You will be given a possibly malformed JSON string. Fix it to be valid JSON. Return ONLY the corrected JSON.
Input:\n{text}
"""
            )
            fixed = self.llm.generate(fixer.format(text=cleaned))
            fixed_clean = (fixed or "").strip()
            if fixed_clean.startswith("```"):
                fixed_clean = fixed_clean.strip("`").replace("json\n", "").strip()
            return json.loads(fixed_clean)
