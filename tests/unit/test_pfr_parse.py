"""Unit tests for PFR parsing."""

from bs4 import BeautifulSoup

from nfl_gravity.scrapers.pfr import parse_career_tables


PFR_HTML = """
<table id="passing">
  <tr id="Career">
    <td data-stat="pass_yds">25,000</td>
    <td data-stat="pass_td">200</td>
  </tr>
</table>
<table id="rushing_and_receiving">
  <tr id="Career">
    <td data-stat="rush_yds">3,500</td>
    <td data-stat="rec_yds">800</td>
    <td data-stat="rush_td">30</td>
    <td data-stat="rec_td">5</td>
  </tr>
</table>
<table id="defense">
  <tr id="Career">
    <td data-stat="tackle_comb">150</td>
    <td data-stat="sk">12.5</td>
    <td data-stat="int">8</td>
  </tr>
</table>
"""


def test_parse_pfr_career_derived() -> None:
    soup = BeautifulSoup(PFR_HTML, "lxml")
    data = parse_career_tables(soup)
    assert data["career_yards"] == 25000 + 3500 + 800
    assert data["total_touchdowns"] == 200 + 30 + 5
    assert data["career_sacks"] == 12.5
    assert data["career_interceptions"] == 8
    assert data["career_tackles"] == 150.0
