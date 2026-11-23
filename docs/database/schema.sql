
-- ============================================================
-- PROJECT: SONGNHAT COPILOT
-- DATABASE: PostgreSQL
-- DESCRIPTION: Database schema initialization
-- ============================================================

-- 1. EXTENSION
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- 2. TABLE: products
-- Quản lý 2 dòng sản phẩm Motors và Drives
-- ============================================================

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    description TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_products_code
        CHECK (code IN ('MOTORS', 'DRIVES'))
);


-- Dữ liệu khởi tạo products
INSERT INTO products (code, name, description)
VALUES
    (
        'MOTORS',
        'Động cơ (Motors)',
        'Quản lý thông tin và yêu cầu hỗ trợ kỹ thuật liên quan đến động cơ.'
    ),
    (
        'DRIVES',
        'Biến tần (Drives)',
        'Quản lý thông tin và yêu cầu hỗ trợ kỹ thuật liên quan đến biến tần.'
    )
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 3. TABLE: categories
-- Quản lý 3 danh mục nghiệp vụ
-- ============================================================

CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    description TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_categories_code
        CHECK (
            code IN (
                'DOCUMENT_REQUEST',
                'SERVICE_PROGRESS',
                'TECHNICAL_ESCALATION'
            )
        )
);


-- Dữ liệu khởi tạo categories
INSERT INTO categories (code, name, description)
VALUES
    (
        'DOCUMENT_REQUEST',
        'Yêu cầu tài liệu',
        'Các yêu cầu cung cấp tài liệu và hướng dẫn kỹ thuật.'
    ),
    (
        'SERVICE_PROGRESS',
        'Tiến độ dịch vụ',
        'Theo dõi tiến độ xử lý và tình trạng dịch vụ.'
    ),
    (
        'TECHNICAL_ESCALATION',
        'Chuyển cấp kỹ thuật',
        'Các vấn đề kỹ thuật cần chuyển đến chuyên gia xử lý.'
    )
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 4. TABLE: knowledge_passages
-- Lưu các đoạn trích tài liệu kỹ thuật đã được phê duyệt
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_passages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    product_id UUID NOT NULL,

    document_name VARCHAR(255) NOT NULL,
    document_code VARCHAR(100),

    section_name VARCHAR(255),
    section_number VARCHAR(100),

    page_number INTEGER NOT NULL,

    passage_content TEXT NOT NULL,

    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    approved_at TIMESTAMPTZ,
    approved_by VARCHAR(150),

    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_knowledge_product
        FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_knowledge_page
        CHECK (page_number > 0),

    CONSTRAINT chk_knowledge_approval
        CHECK (
            (is_approved = FALSE AND approved_at IS NULL)
            OR
            (is_approved = TRUE AND approved_at IS NOT NULL)
        )
);


-- ============================================================
-- 5. TABLE: tickets
-- Quản lý yêu cầu hỗ trợ kỹ thuật
-- ============================================================

CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    ticket_number VARCHAR(50) NOT NULL UNIQUE,

    product_id UUID NOT NULL,
    category_id UUID NOT NULL,

    subject VARCHAR(255) NOT NULL,
    description TEXT,

    -- Thông tin thiết bị
    serial_number VARCHAR(150),
    firmware_version VARCHAR(100),

    -- Cảnh báo nguy hiểm
    is_hazard_escalated BOOLEAN NOT NULL DEFAULT FALSE,
    hazard_reason TEXT,

    -- Trạng thái ticket
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',

    priority VARCHAR(30) NOT NULL DEFAULT 'MEDIUM',

    created_by VARCHAR(150),
    assigned_to VARCHAR(150),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_tickets_product
        FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_tickets_category
        FOREIGN KEY (category_id)
        REFERENCES categories(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_ticket_status
        CHECK (
            status IN (
                'OPEN',
                'IN_PROGRESS',
                'PENDING',
                'RESOLVED',
                'CLOSED'
            )
        ),

    CONSTRAINT chk_ticket_priority
        CHECK (
            priority IN (
                'LOW',
                'MEDIUM',
                'HIGH',
                'CRITICAL'
            )
        ),

    CONSTRAINT chk_ticket_hazard_reason
        CHECK (
            is_hazard_escalated = FALSE
            OR (
                hazard_reason IS NOT NULL
                AND LENGTH(TRIM(hazard_reason)) > 0
            )
        )
);


-- ============================================================
-- 6. TABLE: copilot_packages
-- Lưu kết quả phân tích của AI Copilot
-- ============================================================

CREATE TABLE IF NOT EXISTS copilot_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    ticket_id UUID NOT NULL,

    -- Tóm tắt tình huống
    case_summary TEXT NOT NULL,

    -- Các thông tin còn thiếu
    missing_facts JSONB NOT NULL DEFAULT '[]'::JSONB,

    -- Nguồn trích dẫn tài liệu
    citations JSONB NOT NULL DEFAULT '[]'::JSONB,

    -- Trạng thái phê duyệt
    approval_status VARCHAR(20) NOT NULL DEFAULT 'Pending',

    reviewed_by VARCHAR(150),
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_copilot_ticket
        FOREIGN KEY (ticket_id)
        REFERENCES tickets(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_copilot_approval_status
        CHECK (
            approval_status IN (
                'Pending',
                'Approved',
                'Rejected'
            )
        ),

    CONSTRAINT chk_missing_facts_array
        CHECK (jsonb_typeof(missing_facts) = 'array'),

    CONSTRAINT chk_citations_array
        CHECK (jsonb_typeof(citations) = 'array')
);


-- ============================================================
-- 7. TABLE: run_ingestion_batches   (CRM-42)
-- Audit: 1 bản ghi cho mỗi lần upload CSV
-- ============================================================

CREATE TABLE IF NOT EXISTS run_ingestion_batches (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    batch_id         VARCHAR(255) NOT NULL,
    source_file      VARCHAR(255) NOT NULL,
    import_type      VARCHAR(20)  NOT NULL DEFAULT 'increment',

    started_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ,

    total_rows       INTEGER NOT NULL DEFAULT 0,
    accepted_rows    INTEGER NOT NULL DEFAULT 0,
    quarantined_rows INTEGER NOT NULL DEFAULT 0,
    inserted_rows    INTEGER NOT NULL DEFAULT 0,
    reconciliation_ok BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_ingestion_batch UNIQUE (batch_id, source_file),
    CONSTRAINT chk_ingestion_import_type
        CHECK (import_type IN ('snapshot', 'increment', 'tombstone'))
);

COMMENT ON TABLE run_ingestion_batches IS
'CRM-42: audit trail – 1 row per CSV upload batch.';


-- ============================================================
-- 8. TABLE: import_quarantine   (CRM-42)
-- Thay thế JSONL file — quarantined rows ghi vào DB
-- ============================================================

CREATE TABLE IF NOT EXISTS import_quarantine (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    batch_id         VARCHAR(255) NOT NULL,
    source_file      VARCHAR(255) NOT NULL,
    import_type      VARCHAR(20)  NOT NULL DEFAULT 'increment',

    row_index        INTEGER      NOT NULL,
    source_key       VARCHAR(255) NOT NULL,
    quarantine_reason VARCHAR(50) NOT NULL,

    errors           JSONB        NOT NULL DEFAULT '[]'::JSONB,
    raw_row          JSONB        NOT NULL DEFAULT '{}'::JSONB,

    quarantined_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Tombstone fields (DAT 02 explicit deletion)
    tombstone_reason VARCHAR(500),
    authorized_by    VARCHAR(150),
    is_tombstone     BOOLEAN     NOT NULL DEFAULT FALSE,

    CONSTRAINT uq_quarantine_entry UNIQUE (batch_id, source_file, row_index),

    CONSTRAINT chk_quarantine_reason
        CHECK (quarantine_reason IN (
            'SCHEMA_VIOLATION', 'MISSING_REQUIRED_FIELD',
            'STALE_VERSION', 'DUPLICATE_KEY',
            'IDENTITY_CONFLICT', 'INVALID_PROVENANCE',
            'TOMBSTONE', 'UNKNOWN'
        ))
);

CREATE INDEX IF NOT EXISTS idx_quarantine_source_file
    ON import_quarantine(source_file);

CREATE INDEX IF NOT EXISTS idx_quarantine_batch_id
    ON import_quarantine(batch_id, source_file);

CREATE INDEX IF NOT EXISTS idx_quarantine_source_key
    ON import_quarantine(source_key);

CREATE INDEX IF NOT EXISTS idx_quarantine_reason
    ON import_quarantine(quarantine_reason);

COMMENT ON TABLE import_quarantine IS
'CRM-42: quarantined rows từ CSV ingestion – thay thế JSONL file, append-only audit.';


-- ============================================================
-- 9. TABLE: case_events   (CRM-42)
-- Hàng ACCEPTED từ cases_and_events.csv
-- ============================================================

CREATE TABLE IF NOT EXISTS case_events (
    id                 UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    event_id           VARCHAR(100) NOT NULL,
    case_key           VARCHAR(100) NOT NULL,
    account_key        VARCHAR(100) NOT NULL,
    product_code       VARCHAR(50)  NOT NULL,
    serial_number      VARCHAR(150),
    event_author_role  VARCHAR(50)  NOT NULL,
    original_text      TEXT         NOT NULL,
    event_time         TIMESTAMPTZ  NOT NULL,
    is_customer_report BOOLEAN      NOT NULL DEFAULT FALSE,

    -- DAT 01 Provenance
    batch_id           VARCHAR(255) NOT NULL,
    record_version     INTEGER      NOT NULL DEFAULT 1,
    owner              VARCHAR(150) NOT NULL,
    access_label       VARCHAR(20)  NOT NULL DEFAULT 'INTERNAL',
    permitted_audience TEXT         NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_case_event_id UNIQUE (event_id),
    CONSTRAINT chk_case_event_product
        CHECK (product_code IN ('MOTORS', 'DRIVES')),
    CONSTRAINT chk_case_event_access_label
        CHECK (access_label IN ('INTERNAL', 'RESTRICTED', 'PUBLIC'))
);

CREATE INDEX IF NOT EXISTS idx_case_events_case_key
    ON case_events(case_key);
CREATE INDEX IF NOT EXISTS idx_case_events_account_key
    ON case_events(account_key);
CREATE INDEX IF NOT EXISTS idx_case_events_product_code
    ON case_events(product_code);

COMMENT ON TABLE case_events IS
'CRM-42: validated ACCEPTED rows từ cases_and_events.csv ingestion.';


-- ============================================================
-- 10. TABLE: customer_product_links   (CRM-42)
-- Hàng ACCEPTED từ customer_product_links.csv
-- ============================================================

CREATE TABLE IF NOT EXISTS customer_product_links (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    link_id          VARCHAR(100) NOT NULL,
    account_key      VARCHAR(100),
    product_code     VARCHAR(50)  NOT NULL,
    serial_number    VARCHAR(150),
    link_status      VARCHAR(20)  NOT NULL,
    confidence_score NUMERIC(4,3) NOT NULL,
    link_source      VARCHAR(100) NOT NULL,
    confirmed_by     VARCHAR(150),
    confirmed_at     TIMESTAMPTZ,
    conflict_note    TEXT,

    -- DAT 01 Provenance
    batch_id           VARCHAR(255) NOT NULL,
    record_version     INTEGER      NOT NULL DEFAULT 1,
    owner              VARCHAR(150) NOT NULL,
    access_label       VARCHAR(20)  NOT NULL DEFAULT 'INTERNAL',
    permitted_audience TEXT         NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_customer_product_link_id UNIQUE (link_id),
    CONSTRAINT chk_cpl_product
        CHECK (product_code IN ('MOTORS', 'DRIVES')),
    CONSTRAINT chk_cpl_link_status
        CHECK (link_status IN ('approved', 'pending_review', 'conflicted', 'rejected')),
    CONSTRAINT chk_cpl_access_label
        CHECK (access_label IN ('INTERNAL', 'RESTRICTED', 'PUBLIC'))
);

CREATE INDEX IF NOT EXISTS idx_cpl_account_key
    ON customer_product_links(account_key);
CREATE INDEX IF NOT EXISTS idx_cpl_link_status
    ON customer_product_links(link_status);

COMMENT ON TABLE customer_product_links IS
'CRM-42: validated ACCEPTED rows từ customer_product_links.csv ingestion.';


-- ============================================================
-- 11. UNIQUE CONSTRAINT on knowledge_passages (CRM-42 idempotent upsert)
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_knowledge_passage_identity'
    ) THEN
        ALTER TABLE knowledge_passages
            ADD CONSTRAINT uq_knowledge_passage_identity
                UNIQUE NULLS NOT DISTINCT (document_code, section_number, page_number, product_id);
    END IF;
END $$;


-- ============================================================
-- 12. INDEXES
-- Tối ưu hiệu suất truy vấn
-- ============================================================

-- Products
CREATE INDEX IF NOT EXISTS idx_products_code
    ON products(code);

-- Categories
CREATE INDEX IF NOT EXISTS idx_categories_code
    ON categories(code);

-- Knowledge passages
CREATE INDEX IF NOT EXISTS idx_knowledge_product
    ON knowledge_passages(product_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_approved
    ON knowledge_passages(product_id, page_number)
    WHERE is_approved = TRUE;

CREATE INDEX IF NOT EXISTS idx_knowledge_metadata
    ON knowledge_passages USING GIN(metadata);

-- Tickets
CREATE INDEX IF NOT EXISTS idx_tickets_product
    ON tickets(product_id);

CREATE INDEX IF NOT EXISTS idx_tickets_category
    ON tickets(category_id);

CREATE INDEX IF NOT EXISTS idx_tickets_status
    ON tickets(status);

CREATE INDEX IF NOT EXISTS idx_tickets_serial_number
    ON tickets(serial_number);

CREATE INDEX IF NOT EXISTS idx_tickets_hazard
    ON tickets(is_hazard_escalated)
    WHERE is_hazard_escalated = TRUE;

-- Copilot packages
CREATE INDEX IF NOT EXISTS idx_copilot_ticket
    ON copilot_packages(ticket_id);

CREATE INDEX IF NOT EXISTS idx_copilot_approval_status
    ON copilot_packages(approval_status);

CREATE INDEX IF NOT EXISTS idx_copilot_missing_facts
    ON copilot_packages USING GIN(missing_facts);

CREATE INDEX IF NOT EXISTS idx_copilot_citations
    ON copilot_packages USING GIN(citations);


-- ============================================================
-- 13. COMMENTS
-- Mô tả các bảng và trường dữ liệu
-- ============================================================

COMMENT ON TABLE products IS
'Quản lý các dòng sản phẩm Motors và Drives.';

COMMENT ON TABLE categories IS
'Quản lý các danh mục nghiệp vụ của SongNhat Copilot.';

COMMENT ON TABLE knowledge_passages IS
'Lưu các đoạn trích từ tài liệu kỹ thuật, bao gồm số trang, mục tài liệu và trạng thái phê duyệt.';

COMMENT ON TABLE tickets IS
'Quản lý yêu cầu hỗ trợ kỹ thuật, thông tin thiết bị và cảnh báo nguy hiểm.';

COMMENT ON TABLE copilot_packages IS
'Lưu kết quả phân tích AI gồm Case Summary, Missing Facts, Citations và trạng thái phê duyệt.';

COMMENT ON COLUMN tickets.is_hazard_escalated IS
'Đánh dấu ticket có vấn đề nguy hiểm cần chuyển cấp xử lý hay không.';

COMMENT ON COLUMN tickets.hazard_reason IS
'Lý do cảnh báo nguy hiểm và chuyển cấp kỹ thuật.';

COMMENT ON COLUMN tickets.serial_number IS
'Số serial của thiết bị cần hỗ trợ.';

COMMENT ON COLUMN tickets.firmware_version IS
'Phiên bản firmware của thiết bị.';

COMMENT ON COLUMN copilot_packages.missing_facts IS
'Danh sách thông tin còn thiếu dưới dạng JSON array.';

COMMENT ON COLUMN copilot_packages.citations IS
'Danh sách nguồn trích dẫn tài liệu kỹ thuật dưới dạng JSON array.';


-- ============================================================
-- 14. VERIFY DATABASE
-- Kiểm tra dữ liệu khởi tạo
-- ============================================================

SELECT * FROM products ORDER BY code;

SELECT * FROM categories ORDER BY code;

SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
AND table_name IN (
    'products',
    'categories',
    'knowledge_passages',
    'tickets',
    'copilot_packages',
    'run_ingestion_batches',
    'import_quarantine',
    'case_events',
    'customer_product_links'
)
ORDER BY table_name;


-- ============================================================
-- END OF SONGNHAT COPILOT DATABASE SCHEMA
-- ============================================================
