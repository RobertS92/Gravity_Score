"""Handle discovery and verification tests."""

from gravity_api.scraper_registry.field_sufficiency import is_sufficient
from gravity_api.scrapers.parsers.handle_discovery import (
    apply_user_instagram_upload,
    bio_matches_athlete,
    google_instagram_search_url,
    has_trusted_instagram_handle,
    passes_authenticity_gate,
    resolve_instagram_fields,
)


def test_espn_auto_trust():
    fields = resolve_instagram_fields(
        [{"instagram": "starqb", "_source": "espn"}],
        name="John Smith",
        school="Texas",
        sport="cfb",
        position="QB",
    )
    assert fields["instagram_handle"] == "starqb"
    assert fields["instagram_handle_source"] == "espn"
    assert has_trusted_instagram_handle(fields)


def test_google_single_source_stays_candidate():
    fields = resolve_instagram_fields(
        [{"instagram": "maybe_wrong", "_source": "google_instagram"}],
        name="John Smith",
        school="Texas",
        sport="cfb",
        position="QB",
    )
    assert fields.get("instagram_handle") is None
    assert fields["instagram_handle_candidate"] == "maybe_wrong"
    assert not has_trusted_instagram_handle(fields)


def test_consensus_promotes_handle():
    fields = resolve_instagram_fields(
        [
            {"instagram": "realathlete", "_source": "google_instagram"},
            {"instagram": "realathlete", "_source": "wikipedia"},
        ],
        name="Jane Doe",
        school="UConn",
        sport="ncaab_womens",
        position="G",
    )
    assert fields["instagram_handle"] == "realathlete"
    assert fields["instagram_handle_source"] == "consensus"


def test_bio_matches_athlete():
    assert bio_matches_athlete(
        "Paige Bueckers | Official account | UConn Women's Basketball",
        name="Paige Bueckers",
        school="UConn",
        sport="ncaab_womens",
        position="G",
    )
    assert not bio_matches_athlete(
        "Fan page not affiliated",
        name="Paige Bueckers",
        school="UConn",
        sport="ncaab_womens",
        position="G",
    )


def test_user_upload_trusted():
    raw = apply_user_instagram_upload({"instagram_handle": "@MyHandle", "instagram_followers": 5000})
    assert raw["instagram_handle"] == "myhandle"
    assert raw["instagram_handle_source"] == "user"
    assert is_sufficient(raw, "instagram_handle")


def test_authenticity_gate_rejects_unverified():
    ok, auth = passes_authenticity_gate(
        handle="randomfan",
        followers=50,
        bio_text="unrelated content",
        name="John Smith",
        school="Texas",
        sport="cfb",
        position="QB",
        handle_source="google_instagram",
    )
    assert not ok
    assert auth["social_authenticity_score"] < 70


def test_tighter_google_query():
    url = google_instagram_search_url("John Smith", "Texas", "QB")
    assert "site%3Ainstagram.com" in url or "site:instagram.com" in url
    assert "John" in url
