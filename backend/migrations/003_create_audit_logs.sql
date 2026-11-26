-- CRM-60: immutable audit events for sensitive operations.
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action VARCHAR(80) NOT NULL,
    resource_type VARCHAR(80),
    resource_id VARCHAR(150),
    actor_email VARCHAR(255),
    actor_role VARCHAR(80),
    ip_address VARCHAR(64),
    user_agent VARCHAR(500),
    status_code INTEGER NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_id ON audit_logs(resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_email ON audit_logs(actor_email);

-- Align approval values with CRM-41/CRM-44 API contract (uppercase).
ALTER TABLE copilot_packages DROP CONSTRAINT IF EXISTS chk_copilot_approval_status;
ALTER TABLE copilot_packages
    ADD CONSTRAINT chk_copilot_approval_status
    CHECK (UPPER(approval_status) IN ('PENDING', 'APPROVED', 'REJECTED'));
