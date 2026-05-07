CREATE TABLE IF NOT EXISTS agent_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  conversation_id TEXT NOT NULL,
  title TEXT NOT NULL,
  messages_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  context_athlete_id TEXT,
  context_athlete_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_conversations_user_updated
  ON agent_conversations(user_id, updated_at DESC);
