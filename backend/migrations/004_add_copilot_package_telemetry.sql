-- CRM-61: Add telemetry, grounding, and budget hold columns to copilot_packages.
ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS model_version VARCHAR(100);
ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(100);
ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS token_usage JSONB DEFAULT '{}'::jsonb;
ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS latency_ms DOUBLE PRECISION;
ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS package_status VARCHAR(30) DEFAULT 'COMPLETED';
ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS hold_reason TEXT;
ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS grounding_score DOUBLE PRECISION;
