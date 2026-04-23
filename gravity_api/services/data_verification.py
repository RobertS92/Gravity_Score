"""Stub auto-verification for school athlete data submissions (Phase 3 placeholder)."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple


def run_stub_verification(fields: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (status, verification_results).
    NIL deal values always need review; trivial fields auto-pass in stub.
    """
    results: Dict[str, Any] = {}
    flagged_any = False
    for key, val in fields.items():
        lk = key.lower()
        if "nil" in lk and ("deal" in lk or "value" in lk or "comp" in lk):
            results[key] = {"passed": False, "source": "stub", "reason": "manual_review_required"}
            flagged_any = True
        else:
            results[key] = {"passed": True, "source": "stub"}
    if flagged_any:
        return "partial", results
    return "auto_verified", results
