-- VoiceOS optional Postgres schema (audit + session metadata)

CREATE TABLE IF NOT EXISTS voiceos_audit (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action TEXT NOT NULL,
    details JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS voiceos_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_voiceos_audit_ts ON voiceos_audit (ts DESC);
