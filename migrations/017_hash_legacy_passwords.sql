-- Normalize legacy plaintext password rows to bcrypt hashes.
-- Safe guard: only rewrites rows that do not already look like bcrypt.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

UPDATE user_accounts
SET password_hash = crypt(password_hash, gen_salt('bf'))
WHERE password_hash IS NOT NULL
  AND password_hash <> ''
  AND password_hash !~ '^\$2[aby]\$';
