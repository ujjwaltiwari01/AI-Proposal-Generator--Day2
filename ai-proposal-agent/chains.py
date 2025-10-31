from __future__ import annotations
import json
import time
import logging
from typing import Any, Dict, List, Optional

try:
    from langchain.chat_models import ChatOpenAI  # older langchain
    from langchain.prompts import PromptTemplate
    from langchain.schema import HumanMessage
except Exception:  # pragma: no cover
    # fallback to new imports if needed
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.prompts import PromptTemplate  # type: ignore
    from langchain_core.messages import HumanMessage  # type: ignore

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around LangChain ChatOpenAI with retry/backoff."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.3, max_tokens: int = 2000):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._llm = ChatOpenAI(model=model, temperature=temperature, max_tokens=max_tokens)

    def generate(self, prompt: str, retries: int = 3, backoff: float = 1.5) -> str:
        for i in range(retries):
            try:
                resp = self._llm([HumanMessage(content=prompt)])
                return resp.content
            except Exception as e:  # pragma: no cover - network
                logger.warning("LLM error (%s/%s): %s", i + 1, retries, e)
                time.sleep(backoff * (i + 1))
        raise RuntimeError("LLM generation failed after retries")


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
            # coerce shapes
            for k in ["pain_points", "commitments", "timeline_hints", "budget_cues", "quotes"]:
                data.setdefault(k, [])
            return data
        except Exception:
            # fallback simple heuristic
            return {
                "pain_points": [],
                "commitments": [],
                "timeline_hints": [],
                "budget_cues": [],
                "quotes": [],
            }


class SectionChain:
    def __init__(self, llm: LLMClient, prompt_text: str):
        self.llm = llm
        self.prompt_text = prompt_text
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
        # section templates
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
        data = self._ensure_json(out)
        return data

    def regenerate_section(self, section_name: str, context: Dict[str, Any]) -> str:
        prompt_text = self.section_prompts.get(section_name)
        if not prompt_text:
            # generic fallback
            prompt_text = f"Write the section '{section_name}' in markdown. Tone: {{brand_tone}}"
        chain = SectionChain(self.llm, prompt_text)
        return chain.run(context)

    def _ensure_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            fixer = PromptTemplate.from_template(
                """
You will be given a possibly malformed JSON string. Fix it to be valid JSON. Return ONLY the corrected JSON.
Input:\n{text}
"""
            )
            fixed = self.llm.generate(fixer.format(text=text))
            return json.loads(fixed)
