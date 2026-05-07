-- Canonical roster lifecycle status for strict roster integrity.
ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS roster_status TEXT
    DEFAULT 'active_on_roster'
    CHECK (roster_status IN ('active_on_roster', 'transferred', 'left_for_draft', 'graduated', 'out_other'));

ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS roster_status_reason TEXT;

ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS roster_status_changed_at TIMESTAMPTZ;

UPDATE athletes
SET roster_status = CASE
  WHEN is_active IS FALSE THEN 'out_other'
  ELSE 'active_on_roster'
END
WHERE roster_status IS NULL;

CREATE INDEX IF NOT EXISTS idx_athletes_roster_status ON athletes (roster_status);
CREATE INDEX IF NOT EXISTS idx_athletes_roster_status_changed_at ON athletes (roster_status_changed_at DESC NULLS LAST);
