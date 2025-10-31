from __future__ import annotations
from typing import Any, Dict
from ai_proposal_agent.chains import LLMClient, MainProposalChain, SummarizationChain, QualityAuditChain
from pathlib import Path

class DummyLLM(LLMClient):
    def __init__(self):
        pass
    def generate(self, prompt: str, retries: int = 3, backoff: float = 1.5) -> str:
        if "Extract key insights" in prompt:
            return '{"pain_points": ["A"], "commitments": [], "timeline_hints": [], "budget_cues": [], "quotes": []}'
        if "Fix it to be valid JSON" in prompt or "Fix it" in prompt:
            return '{"title":"T","metadata":{},"sections":{},"markdown_full":""}'
        if "Return ONLY a JSON object" in prompt:
            return '{"title":"T","metadata":{},"sections": {"Executive Summary": "X"}, "markdown_full": "X"}'
        if "Review the proposal" in prompt:
            return '{"grade": 90, "summary": "Good", "suggestions": ["S"], "apply_notes": []}'
        return "OK"


def test_summarization_chain():
    s = SummarizationChain(DummyLLM())
    out = s.run("hello")
    assert "pain_points" in out


def test_main_chain_json():
    base = Path(__file__).resolve().parents[1]
    prompts_dir = str(base / "prompts")
    c = MainProposalChain(DummyLLM(), prompts_dir)
    data: Dict[str, Any] = {
        "company_name":"Co","client_name":"Cli","project_title":"P","goals":"G","budget":"B","timeline":"T","brand_tone":"Warm","language":"English","transcript_insights":"-","additional_notes":"-","attachments_summary":"-"
    }
    out = c.generate(data)
    assert "sections" in out


def test_quality_audit():
    q = QualityAuditChain(DummyLLM())
    res = q.run({"a":1}, "md")
    assert isinstance(res, dict) and "grade" in res
