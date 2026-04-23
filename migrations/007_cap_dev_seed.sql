-- Dev / demo CapIQ seed — safe to re-run.
-- Org id matches gravity-terminal MOCK_ORG_ID.

INSERT INTO organizations (id, name, slug)
VALUES (
  '00000000-0000-4000-8000-0000000000aa'::uuid,
  'Gravity Dev School',
  'gravity-dev-school'
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  slug = EXCLUDED.slug;

INSERT INTO user_accounts (id, email, role, organization, organization_id)
SELECT
  '00000000-0000-4000-8000-000000000001'::uuid,
  'demo@gravity.local',
  'school_admin',
  'Gravity Dev School',
  '00000000-0000-4000-8000-0000000000aa'::uuid
WHERE NOT EXISTS (SELECT 1 FROM user_accounts WHERE id = '00000000-0000-4000-8000-000000000001'::uuid)
  AND NOT EXISTS (SELECT 1 FROM user_accounts WHERE lower(email) = lower('demo@gravity.local'));

UPDATE user_accounts
SET organization_id = '00000000-0000-4000-8000-0000000000aa'::uuid,
    organization = COALESCE(NULLIF(trim(organization), ''), 'Gravity Dev School')
WHERE id = '00000000-0000-4000-8000-000000000001'::uuid
   OR lower(email) = lower('demo@gravity.local');

INSERT INTO organization_members (user_id, org_id, role, sport)
SELECT u.id, '00000000-0000-4000-8000-0000000000aa'::uuid, 'school_admin', NULL::text
FROM user_accounts u
WHERE (u.id = '00000000-0000-4000-8000-000000000001'::uuid OR lower(u.email) = lower('demo@gravity.local'))
  AND NOT EXISTS (
    SELECT 1 FROM organization_members om
    WHERE om.user_id = u.id
      AND om.org_id = '00000000-0000-4000-8000-0000000000aa'::uuid
      AND om.role = 'school_admin'
  );
