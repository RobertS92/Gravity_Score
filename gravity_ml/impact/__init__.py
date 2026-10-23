"""Impact (winning contribution) models — WP-I.

APM ridge skeleton (``apm.py``) runs against fixtures. Live train/promote is
blocked until scraper SCRAPER_FIX_SPEC WP10 populates ``games`` /
``game_player_box`` (CFB also needs plays). Do not claim Impact trained without
that data and gates G-I1..G-I5.
"""

BLOCKED_REASON = (
    "WP-I requires scraper WP10 tables: games, game_player_box, and for CFB "
    "cfb_plays / cfb_play_players. Season history must also pass WP1–WP7 "
    "(validation_status, stats_as_of). See docs/specs/SCORING_ML_FIX_SPEC.md §4 "
    "and docs/specs/SCRAPER_FIX_SPEC.md WP10."
)

__all__ = ["BLOCKED_REASON"]
