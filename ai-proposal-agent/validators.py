from __future__ import annotations
from typing import Dict, List, Tuple


def validate_inputs(data: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate required fields and basic constraints.

    Returns (ok, errors)
    """
    errors: List[str] = []
    req = ["company_name", "client_name", "project_title", "goals", "budget", "timeline", "brand_tone"]
    for k in req:
        if not data.get(k):
            errors.append(f"Missing required field: {k}")
    # simple contradictions
    if data.get("budget") and any(x in data["budget"].lower() for x in ["tbd", "unknown"]):
        # allow but warn
        pass
    if data.get("timeline") and len(data["timeline"]) < 3:
        errors.append("Timeline appears too short.")
    return (len(errors) == 0, errors)


def sanity_check(sections: Dict[str, str], data: Dict[str, str]) -> List[str]:
    """Flag potential contradictions for user confirmation."""
    flags: List[str] = []
    if "Scope of Work" in sections.get("Scope of Work & Deliverables", "") and "Pricing" in sections.get("Pricing & Payment Terms", ""):
        pass
    if data.get("budget") and "free" in sections.get("Pricing & Payment Terms", "").lower():
        flags.append("Pricing mentions 'free' while a budget is specified.")
    return flags
