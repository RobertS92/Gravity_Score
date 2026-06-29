-- Partner API keys for external Gravity Score distribution.

CREATE TABLE IF NOT EXISTS partner_api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_name TEXT NOT NULL,
  key_hash TEXT NOT NULL UNIQUE,
  key_prefix TEXT NOT NULL,
  scopes TEXT[] NOT NULL DEFAULT ARRAY['scores:read', 'search:read'],
  allowed_origins TEXT[] DEFAULT NULL,
  rate_limit_per_minute INT NOT NULL DEFAULT 120 CHECK (rate_limit_per_minute > 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_used_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_partner_api_keys_active ON partner_api_keys(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_partner_api_keys_prefix ON partner_api_keys(key_prefix);

COMMENT ON TABLE partner_api_keys IS 'API keys for third-party sites consuming Gravity Score via /v2/partner';
COMMENT ON COLUMN partner_api_keys.key_hash IS 'SHA-256 hex digest of the full API key; raw key is shown once at creation';
COMMENT ON COLUMN partner_api_keys.allowed_origins IS 'Optional browser Origin allowlist; NULL allows server-to-server only (no Origin header)';
