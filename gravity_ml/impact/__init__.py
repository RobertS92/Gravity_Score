"""Impact (winning contribution) models — WP-I.

Blocked on scraper SCRAPER_FIX_SPEC WP10 (`games`, `game_player_box`, CFBD plays).
Modules below are placeholders so imports and package layout are stable; do not
train or promote until gates G-I1..G-I5 pass on real game data.
"""

BLOCKED_REASON = (
    "WP-I requires scraper WP10 tables: games, game_player_box, and for CFB "
    "cfb_plays / cfb_play_players. Season history must also pass WP1–WP7 "
    "(validation_status, stats_as_of). See docs/specs/SCORING_ML_FIX_SPEC.md §4 "
    "and docs/specs/SCRAPER_FIX_SPEC.md WP10."
)

__all__ = ["BLOCKED_REASON"]
