-- ============================================================
-- Migration 002: Enable pg_trgm extension and create GIN trigram index
-- Task CRM-43: [BE] Retriever thuc — Full-text Search knowledge_passages thay the mock data
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_knowledge_passages_content_trgm
ON knowledge_passages USING gin (passage_content gin_trgm_ops);
