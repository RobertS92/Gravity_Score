"""Unit tests for Wikipedia parsing helpers."""

from bs4 import BeautifulSoup

from nfl_gravity.scrapers.wikipedia import parse_infobox


WIKI_HTML = """
<table class="infobox">
  <tr><th>Position</th><td>Quarterback</td></tr>
  <tr><th>Born</th><td>January 7, 1997 (age 27)</td></tr>
  <tr><th>Height</th><td>6 ft 2 in (1.88 m)</td></tr>
  <tr><th>Weight</th><td>212 lb (96 kg)</td></tr>
  <tr><th>College</th><td>Louisville</td></tr>
  <tr><th>Career highlights and awards</th><td><ul><li>MVP (2019)</li><li>Pro Bowl</li></ul></td></tr>
</table>
"""


def test_parse_infobox_basic_fields() -> None:
    soup = BeautifulSoup(WIKI_HTML, "lxml")
    data = parse_infobox(soup)
    assert data["position"] == "Quarterback"
    assert data["age"] == 27
    assert data["height"].startswith("6 ft")
    assert data["weight"] == 212
    assert data["college"] == "Louisville"
    assert data["birthdate"] == "1997-01-07"
    assert data["awards_count"] == 2


def test_parse_infobox_handles_missing() -> None:
    soup = BeautifulSoup("<table class='infobox'></table>", "lxml")
    data = parse_infobox(soup)
    assert data == {}
