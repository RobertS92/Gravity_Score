-- 009_reports_durability.sql
-- Make `deal_valuation_reports` durable end-to-end.
--
-- Adds:
--   - user_id        : owning user (FK to user_accounts; nullable for legacy rows)
--   - parameters     : JSON of the request body that produced the report
--   - report_json    : full CSC JSON returned to the caller
-- Relaxes:
--   - proposed_deal_value : was NOT NULL (came from a prior brand-deal flow);
--                           reports created via /v1/reports don't need it.
--   - deal_type           : was NOT NULL for the same reason.
--
-- Adds index on (user_id, created_at DESC) so per-user lists are fast.

ALTER TABLE deal_valuation_reports
  ADD COLUMN IF NOT EXISTS user_id     UUID REFERENCES user_accounts(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS parameters  JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS report_json JSONB;

ALTER TABLE deal_valuation_reports
  ALTER COLUMN proposed_deal_value DROP NOT NULL,
  ALTER COLUMN deal_type           DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_deal_valuation_reports_user_recent
  ON deal_valuation_reports (user_id, created_at DESC);
