-- Roster lifecycle: hide departed players in market/search when populated by scrapers.
ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS roster_verified_at TIMESTAMPTZ;

COMMENT ON COLUMN athletes.is_active IS 'FALSE when player left college roster (transfer out, draft, etc.); default TRUE';
COMMENT ON COLUMN athletes.roster_verified_at IS 'Last time official roster sync confirmed this player on current school';

CREATE INDEX IF NOT EXISTS idx_athletes_is_active ON athletes (is_active)
  WHERE is_active = FALSE;
CREATE INDEX IF NOT EXISTS idx_athletes_roster_verified_at ON athletes (roster_verified_at DESC NULLS LAST);
