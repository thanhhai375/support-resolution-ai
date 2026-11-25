"""Fixtures dùng chung cho bộ test E2E (CRM-48).

Nguyên tắc:
- Dùng PostgreSQL THẬT, tạo bằng testcontainers-python (Docker), không mock DB.
- Chỉ các test yêu cầu fixture `e2e_*` mới bị ảnh hưởng; các test cũ không đổi.
- Không có Docker:
    * chạy local  -> test E2E được SKIP kèm lý do rõ ràng;
    * chạy trên CI (biến môi trường CI=true) -> test E2E bị FAIL, không được bỏ qua âm thầm.
- Có thể dùng sẵn một DB khác bằng biến E2E_DATABASE_URL (ví dụ postgresql://user:pass@host:5432/db).
  LƯU Ý: đó phải là DB TRỐNG dùng một lần (tests ghi dữ liệu và không dọn lại); chạy lại trên DB đã
  có dữ liệu CSV thì Flow 1 sẽ fail vì tổng passage không còn tăng. Với testcontainers thì mỗi lần
  chạy là một container mới nên không bị vấn đề này.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLE_CSV = BACKEND_DIR / "app" / "ingestion" / "sample_data" / "curated_knowledge_passages.csv"
SCHEMA_SQL = BACKEND_DIR.parent / "docs" / "database" / "schema.sql"


def _to_sync_url(url: str) -> str:
    """postgresql+psycopg2://... hoặc postgresql+asyncpg://... -> postgresql://..."""
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


def _to_async_url(url: str) -> str:
    return re.sub(r"^postgresql(\+\w+)?://", "postgresql+asyncpg://", url)


def _skip_or_fail(reason: str):
    """Trên CI thì fail (không để test E2E bị bỏ qua âm thầm), local thì skip."""
    if os.getenv("CI", "").lower() in {"1", "true", "yes"}:
        pytest.fail(reason)
    pytest.skip(reason)


def _apply_schema(sync_url: str) -> None:
    """Khởi tạo DB giống môi trường thật: docker-compose (songnhat-db-init) nạp docs/database/schema.sql.

    Schema này chứa cả ràng buộc uq_knowledge_passage_identity mà bước ingestion (CRM-42) cần.
    """
    import psycopg2

    conn = psycopg2.connect(sync_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    finally:
        conn.close()


@pytest.fixture(scope="session")
def e2e_pg_url():
    """URL PostgreSQL dạng đồng bộ (postgresql://...) của DB thật dùng cho E2E."""
    override = os.getenv("E2E_DATABASE_URL")
    if override:
        url = _to_sync_url(override)
        _apply_schema(url)
        yield url
        return

    try:  # tên module khác nhau giữa các phiên bản testcontainers
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:
        try:
            from testcontainers.postgres import PostgresContainer
        except ImportError:
            _skip_or_fail("Chưa cài testcontainers: pip install 'testcontainers[postgres]'")

    try:
        container = PostgresContainer(
            "postgres:16-alpine",
            username="songnhat",
            password="songnhat_dev",
            dbname="songnhat_e2e",
        )
        container.start()
    except Exception as exc:  # Docker chưa bật / không có quyền
        _skip_or_fail(f"Không khởi động được PostgreSQL bằng Docker (testcontainers): {exc}")

    try:
        url = _to_sync_url(container.get_connection_url())
        _apply_schema(url)
        yield url
    finally:
        container.stop()


@pytest.fixture(scope="module")
def e2e_app(e2e_pg_url):
    """FastAPI app thật của backend (app/main.py), trỏ vào PostgreSQL thật.

    Từ khi team gộp backend/main.py vào backend/app/main.py thì app/main.py đã gắn đủ router
    (tickets, copilot, knowledge, auth, ingestion, camunda) nên dùng thẳng app đó.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool

    mp = pytest.MonkeyPatch()
    async_url = _to_async_url(e2e_pg_url)
    # Cho ingestion (psycopg2) và mọi code đọc biến môi trường
    mp.setenv("DATABASE_URL", e2e_pg_url)

    from app import main  

    test_engine = create_async_engine(async_url, poolclass=NullPool, future=True)
    mp.setattr(main, "engine", test_engine)
    mp.setattr(
        main,
        "AsyncSessionLocal",
        sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False),
    )
    mp.setattr(main, "_db_initialized", False)  # buộc chạy lại migration trên DB mới

    app = main.app
    app.state.main_module = main
    app.state.pg_url = e2e_pg_url
    try:
        yield app
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def e2e_client(e2e_app):
    from fastapi.testclient import TestClient

    with TestClient(e2e_app) as client:
        # lifespan đã chạy migration; xác nhận KHÔNG bị âm thầm chuyển sang SQLite.
        main = e2e_app.state.main_module
        assert main.engine.dialect.name == "postgresql", (
            "Backend đã tự chuyển sang SQLite: E2E phải chạy trên PostgreSQL thật"
        )
        yield client


@pytest.fixture(scope="module")
def e2e_users():
    """Tạo 1 user cho mỗi role (đăng ký vào kho user của backend), xóa sau khi test xong.

    Tên role dùng từ vựng của lớp xác thực: support_agent=STAFF, technical_approver=ENGINEER,
    knowledge_steward=MANAGER, administrator=ADMIN.
    """
    from app.repositories import user_repository

    suffix = uuid.uuid4().hex[:6]
    password = "E2e-Test-Pass1!"
    spec = {
        "staff": "support_agent",
        "engineer": "technical_approver",
        "manager": "knowledge_steward",
        "admin": "administrator",
    }
    users = {}
    for key, role in spec.items():
        email = f"e2e-{key}-{suffix}@songnhat.vn"
        user_repository.add_user(email, password, full_name=f"E2E {key}", role=role)
        users[key] = {"email": email, "password": password, "role": role}
    try:
        yield users
    finally:
        for u in users.values():
            user_repository._USERS.pop(u["email"].lower(), None)


@pytest.fixture(scope="module")
def e2e_tokens(e2e_client, e2e_users):
    """Đăng nhập thật qua POST /api/auth/login cho từng role -> Bearer headers."""
    headers = {}
    for key, u in e2e_users.items():
        res = e2e_client.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
        assert res.status_code == 200, f"Đăng nhập {key} thất bại: {res.text}"
        headers[key] = {"Authorization": f"Bearer {res.json()['access_token']}"}
    return headers


@pytest.fixture(scope="module")
def e2e_sql(e2e_pg_url):
    """Chạy SQL trực tiếp trên DB thật để kiểm chứng dữ liệu đã được ghi (không qua API)."""
    import psycopg2

    def run(query: str, params: tuple = ()):
        conn = psycopg2.connect(e2e_pg_url)
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall() if cur.description else None
        finally:
            conn.close()

    return run
