-- PostgreSQL Database Schema for AI Support Resolution Copilot

CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    full_name   VARCHAR(100) NOT NULL,
    role        VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_users_role
        CHECK (role IN ('user', 'agent', 'admin'))
);

CREATE TABLE IF NOT EXISTS categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL UNIQUE,
    parent_id   UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_categories_parent
        FOREIGN KEY (parent_id)
        REFERENCES categories(id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        VARCHAR(255) NOT NULL,
    description  TEXT NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'open',
    priority     VARCHAR(20) NOT NULL DEFAULT 'medium',
    category_id  UUID,
    created_by   UUID NOT NULL,
    assigned_to  UUID,
    resolved_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_tickets_category
        FOREIGN KEY (category_id)
        REFERENCES categories(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_tickets_created_by
        FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_tickets_assigned_to
        FOREIGN KEY (assigned_to)
        REFERENCES users(id)
        ON DELETE SET NULL,
    CONSTRAINT ck_tickets_priority
        CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    CONSTRAINT ck_tickets_status
        CHECK (status IN ('open', 'in_progress', 'pending', 'resolved', 'closed')),
    CONSTRAINT ck_tickets_resolved_at
        CHECK (status NOT IN ('resolved', 'closed') OR resolved_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS messages (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id    UUID NOT NULL,
    sender_id    UUID,
    sender_type  VARCHAR(20) NOT NULL,
    content      TEXT NOT NULL,
    is_internal  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_messages_ticket
        FOREIGN KEY (ticket_id)
        REFERENCES tickets(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_messages_sender
        FOREIGN KEY (sender_id)
        REFERENCES users(id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_messages_sender_type
        CHECK (sender_type IN ('user', 'agent', 'ai', 'system')),
    CONSTRAINT ck_messages_sender
        CHECK (
            (sender_type IN ('user', 'agent') AND sender_id IS NOT NULL)
            OR
            (sender_type IN ('ai', 'system') AND sender_id IS NULL)
        ),
    CONSTRAINT ck_messages_content
        CHECK (length(trim(content)) > 0)
);


-- Indexes for performance
CREATE INDEX IF NOT EXISTS ix_tickets_created_by ON tickets(created_by);
CREATE INDEX IF NOT EXISTS ix_tickets_assigned_to ON tickets(assigned_to);
CREATE INDEX IF NOT EXISTS ix_tickets_category_id ON tickets(category_id);
CREATE INDEX IF NOT EXISTS ix_tickets_status_priority ON tickets(status, priority);
CREATE INDEX IF NOT EXISTS ix_tickets_created_at ON tickets(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_messages_ticket_created_at ON messages(ticket_id, created_at);
CREATE INDEX IF NOT EXISTS ix_categories_parent_id ON categories(parent_id);