"""Test registry — most scraping/ML tests live in separate repositories."""

from typing import Any, Dict, List

TEST_REGISTRY: Dict[str, Dict[str, Any]] = {
    "test_recruiting_collector": {
        "script": "test_recruiting_collector.py",
        "args": [],
        "description": "Recruiting data collection (in-repo smoke script)",
        "timeout": 180,
    },
}

KEYWORD_MAPPING: Dict[str, List[str]] = {
    "test_recruiting_collector": ["recruiting", "recruit", "247sports"],
}


def infer_test_from_keywords(feature_name: str, description: str = "") -> str:
    combined_text = f"{feature_name} {description}".lower()
    scores: Dict[str, int] = {}
    for test_name, keywords in KEYWORD_MAPPING.items():
        score = sum(1 for keyword in keywords if keyword in combined_text)
        if score > 0:
            scores[test_name] = score
    if scores:
        return max(scores, key=scores.get)
    return ""


def get_test_info(test_name: str) -> Dict[str, Any]:
    return TEST_REGISTRY.get(test_name, {})
