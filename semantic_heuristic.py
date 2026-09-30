"""
Disclosed rule-based semantic signal — NOT an LLM.

No LLM API key is configured in this environment (checked: no .env, no *_API_KEY env vars), so
llm_ensemble.py's real API-backed engines cannot run here. Per CLAUDE.md's academic-integrity
rule 4 ("heuristics are allowed only if labelled as heuristics"), this module provides a real,
disclosed keyword/pattern heuristic over the page's actual visible text and title instead of
faking an LLM response. It is always reported with status="heuristic", never "llm".
"""

import re
from typing import Any, Dict

_CREDENTIAL_TERMS = (
    "password", "log in", "login", "sign in", "verify your account", "confirm your identity",
    "social security", "credit card", "card number", "cvv", "billing", "bank account",
)
_URGENCY_TERMS = (
    "urgent", "immediately", "suspended", "unusual activity", "act now", "within 24 hours",
    "your account will be", "limited time", "verify now",
)
_BRAND_TERMS = (
    "paypal", "apple", "microsoft", "amazon", "netflix", "bank of america", "wells fargo",
    "google", "facebook", "instagram", "chase",
)


def analyze_text_heuristically(title: str, visible_text: str) -> Dict[str, Any]:
    """Real, deterministic keyword scan over real page text. Returns a 0..1 score and the exact
    matched terms (evidence), never a fabricated confidence."""
    text = f"{title or ''} {visible_text or ''}".lower()

    credential_hits = sorted({t for t in _CREDENTIAL_TERMS if t in text})
    urgency_hits = sorted({t for t in _URGENCY_TERMS if t in text})
    brand_hits = sorted({t for t in _BRAND_TERMS if t in text})
    has_form_language = bool(re.search(r"\b(sign in|log ?in|register|verify)\b", text))

    raw_score = (
        0.4 * min(len(credential_hits), 3) / 3
        + 0.3 * min(len(urgency_hits), 3) / 3
        + 0.2 * (1.0 if brand_hits else 0.0)
        + 0.1 * (1.0 if has_form_language else 0.0)
    )

    return {
        "status": "heuristic",
        "engine": "rule_based_keyword_scan",
        "note": "No LLM API key configured in this environment — this is a disclosed rule-based "
                "heuristic over real page text, not an LLM call.",
        "score": round(raw_score, 4),
        "evidence": {
            "credential_related_terms_found": credential_hits,
            "urgency_terms_found": urgency_hits,
            "brand_terms_found": brand_hits,
            "has_login_form_language": has_form_language,
        },
    }
