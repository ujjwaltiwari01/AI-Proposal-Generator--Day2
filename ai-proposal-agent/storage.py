from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROPOSALS_DIR = DATA_DIR / "proposals"
EXPORTS_DIR = DATA_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"

for d in (PROPOSALS_DIR, EXPORTS_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _now_ts() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def save_proposal_json(metadata: Dict[str, Any], sections: Dict[str, str], history: Optional[List[Dict[str, Any]]] = None) -> str:
    """Save proposal JSON to disk with versioned ID and return proposal_id."""
    slug = metadata.get("slug") or "proposal"
    pid = f"{_now_ts()}_{slug}"
    payload = {
        "id": pid,
        "metadata": metadata,
        "sections": sections,
        "history": history or [],
    }
    out = PROPOSALS_DIR / f"{pid}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return pid


def load_proposal(proposal_id: str) -> Dict[str, Any]:
    """Load a previously saved proposal by ID."""
    fp = PROPOSALS_DIR / f"{proposal_id}.json"
    if not fp.exists():
        raise FileNotFoundError(f"Proposal not found: {proposal_id}")
    with fp.open("r", encoding="utf-8") as f:
        return json.load(f)


def list_proposals() -> List[Tuple[str, str]]:
    """List proposals as (id, filename)."""
    items: List[Tuple[str, str]] = []
    for p in sorted(PROPOSALS_DIR.glob("*.json")):
        items.append((p.stem, p.name))
    return items


def save_export_files(proposal_id: str, files: Dict[str, bytes]) -> Dict[str, str]:
    """Save exported files under exports/<proposal_id>/ and return paths."""
    outdir = EXPORTS_DIR / proposal_id
    outdir.mkdir(parents=True, exist_ok=True)
    saved: Dict[str, str] = {}
    for name, content in files.items():
        path = outdir / name
        with path.open("wb") as f:
            f.write(content)
        saved[name] = str(path)
    return saved
