"""Unit tests for the LLM fallback helper."""

from nfl_gravity.scrapers import fallback


def test_extract_with_llm(monkeypatch) -> None:
    def fake_llm(prompt: str) -> str:
        return '{"age": 27, "position": "Quarterback", "college": "Louisville", "height": "6 ft 2 in"}'

    monkeypatch.setattr(fallback, "call_llm", fake_llm)
    html = "<html>messy</html>"
    fields = ["age", "position", "college", "height"]
    data = fallback.extract_with_llm(html, fields)
    assert data["age"] == 27
    assert data["college"] == "Louisville"
