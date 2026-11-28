"""CRM-66 / RFP Annex D OPS 02: kiem thu tai 5 nguoi dung dong thoi, 100 request, do P95.

Cach chay (tu thu muc goc cua repo, can PostgreSQL that dang chay, vi du docker compose):

    set DATABASE_URL=postgresql://songnhat:songnhat_dev@localhost:5432/songnhat_copilot
    python docs/qa/load_test_p95.py

Tuy chon:
    --apply-schema   nap docs/database/schema.sql truoc (chi dung voi DB trong, vi du DB rieng de do tai)
    --users 5        so nguoi dung dong thoi (mac dinh 5, theo RFP)
    --requests 100   so request do duoc (mac dinh 100, theo RFP), chia deu: tra cuu tri thuc / phan tich Copilot
    --extra-passages N  them N doan tri thuc TONG HOP (danh dau metadata.synthetic=true) de kho tri thuc dat
                     co 300 doan nhu gia dinh cua RFP (muc 2). CHI de do tai, khong dung de danh gia chat luong.
    --out docs/qa    thu muc ghi ket qua

Cach do:
- Backend that (app.main:app) chay trong tien trinh nay bang uvicorn tren cong ngau nhien, ket noi PostgreSQL that.
- 5 worker bat dong bo (asyncio + httpx) lay request tu mot hang doi, moi worker dung token cua 1 nguoi dung rieng.
- Thoi gian dau-cuoi do o phia client (tu luc gui den luc nhan du phan hoi).
- Thoi gian phia may chu duoc tach bang cach boc 3 ham cua pipeline:
    * truy xuat (Retriever)         = search_knowledge_passages
    * luu goi ho tro vao DB         = _save_copilot_package_to_db
    * sinh van ban (generation)     = tong pipeline - truy xuat - luu DB
- Khoi dong lam nong 5 + 5 request (khong tinh vao ket qua).
- LUU Y: backend hien KHONG goi mo hinh AI that, phan sinh van ban la xu ly theo luat/mau co san.
"""
from __future__ import annotations

import argparse
import asyncio
import contextvars
import csv
import json
import os
import re
import socket
import statistics
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
SCHEMA_SQL = REPO / "docs" / "database" / "schema.sql"
SAMPLE_CSV = BACKEND / "app" / "ingestion" / "sample_data" / "curated_knowledge_passages.csv"

# Ticket thuong (khong nguy hiem) + 2 ticket nguy hiem de do ca duong "giu lai/leo thang".
TICKETS = [
    "Biến tần SD700 báo lỗi E001 quá dòng khi tăng tốc, cần hướng dẫn kiểm tra",
    "Động cơ SM Series rung mạnh khi chạy ở tốc độ thấp, cần tài liệu bảo trì",
    "Cho xin tài liệu hướng dẫn cài đặt thông số biến tần SD700",
    "Biến tần báo lỗi quá nhiệt sau 2 giờ chạy liên tục, kiểm tra quạt làm mát thế nào",
    "Khách hàng hỏi lịch bảo trì định kỳ cho động cơ SM Series",
    "Mã lỗi E-01 trên biến tần là gì và cách xử lý",
    "Cần hướng dẫn đấu nối cáp điều khiển cho biến tần SD700",
    "Biến tần dừng đột ngột khi tải thay đổi, kiểm tra thông số gia tốc",
    "Tủ điện đang bốc khói, có tia lửa",
    "Máy không cháy, không khói, chỉ xin manual",
]
QUERIES = ["SD700", "E001", "quá dòng", "biến tần", "bảo trì", "động cơ", "SM Series", "quá nhiệt", "cài đặt thông số", "lỗi"]


def pct(values, p):
    """Percentile theo noi suy tuyen tinh (giong numpy.percentile mac dinh)."""
    if not values:
        return float("nan")
    xs = sorted(values)
    k = (len(xs) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summarize(values):
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean_ms": round(statistics.fmean(values), 2),
        "p50_ms": round(pct(values, 50), 2),
        "p95_ms": round(pct(values, 95), 2),
        "p99_ms": round(pct(values, 99), 2),
        "max_ms": round(max(values), 2),
    }


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def add_synthetic_passages(sync_url: str, n: int) -> int:
    """Chen n doan tri thuc tong hop da duyet de kho tri thuc lon hon (chi cho do tai)."""
    import psycopg2

    topics = ["bien tan", "dong co", "quat lam mat", "cap dieu khien", "thong so gia toc", "bao tri dinh ky",
              "loi qua dong", "loi qua nhiet", "dau noi", "cai dat ban dau"]
    conn = psycopg2.connect(sync_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM products ORDER BY created_at LIMIT 2")
            pids = [r[0] for r in cur.fetchall()]
            if not pids:
                raise RuntimeError("Chua co san pham trong DB")
            for i in range(n):
                t = topics[i % len(topics)]
                content = (f"[Tong hop #{i}] Huong dan {t}: kiem tra nguon cap, doc ma loi tren man hinh, doi chieu "
                           f"bang thong so trong tai lieu, thuc hien theo buoc {i % 7 + 1}, ghi nhan ket qua va lien he ky su khi can.")
                cur.execute(
                    """INSERT INTO knowledge_passages
                       (product_id, document_name, document_code, section_name, section_number, page_number,
                        passage_content, is_approved, approved_at, approved_by, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, true, now(), 'load-test', %s)
                       ON CONFLICT ON CONSTRAINT uq_knowledge_passage_identity DO NOTHING""",
                    (pids[i % len(pids)], f"Tai lieu tong hop {i % 20}", f"SYN-{i}", t, f"S{i}", i % 60 + 1,
                     content, json.dumps({"synthetic": True, "purpose": "load-test"})),
                )
        conn.commit()
    finally:
        conn.close()
    return n


def apply_schema(sync_url: str) -> None:
    import psycopg2

    conn = psycopg2.connect(sync_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    finally:
        conn.close()


class ServerTimings:
    """Gom thoi gian phia may chu cho tung request /api/copilot/analyze."""

    def __init__(self):
        self.lock = threading.Lock()
        self.pipeline_ms: list[float] = []
        self.retrieval_ms: list[float] = []
        self.save_ms: list[float] = []
        self.generation_ms: list[float] = []
        self.retrieval_calls: list[float] = []
        self.reset_flag = False

    def clear(self):
        with self.lock:
            for lst in (self.pipeline_ms, self.retrieval_ms, self.save_ms, self.generation_ms, self.retrieval_calls):
                lst.clear()


def install_timers(timings: ServerTimings):
    """Boc cac ham pipeline de do thoi gian tach rieng (khong sua file cua team)."""
    from app.services import copilot_engine
    from app.api.v1 import camunda_workflow

    acc = contextvars.ContextVar("acc", default=None)

    orig_search = copilot_engine.search_knowledge_passages
    orig_save = copilot_engine._save_copilot_package_to_db
    orig_pipeline = copilot_engine.run_copilot_pipeline

    async def timed_search(*a, **kw):
        t = time.perf_counter()
        try:
            return await orig_search(*a, **kw)
        finally:
            d = (time.perf_counter() - t) * 1000
            cur = acc.get()
            if cur is not None:
                cur["retrieval"] += d

    async def timed_save(*a, **kw):
        t = time.perf_counter()
        try:
            return await orig_save(*a, **kw)
        finally:
            d = (time.perf_counter() - t) * 1000
            cur = acc.get()
            if cur is not None:
                cur["save"] += d

    async def timed_pipeline(*a, **kw):
        cur = {"retrieval": 0.0, "save": 0.0}
        token = acc.set(cur)
        t = time.perf_counter()
        try:
            return await orig_pipeline(*a, **kw)
        finally:
            total = (time.perf_counter() - t) * 1000
            acc.reset(token)
            with timings.lock:
                timings.pipeline_ms.append(total)
                timings.save_ms.append(cur["save"])
                if cur["retrieval"] > 0:  # ticket nguy hiem bi giu lai: khong goi Retriever
                    timings.retrieval_ms.append(cur["retrieval"])
                    timings.generation_ms.append(max(total - cur["retrieval"] - cur["save"], 0.0))

    copilot_engine.search_knowledge_passages = timed_search
    copilot_engine._save_copilot_package_to_db = timed_save
    copilot_engine.run_copilot_pipeline = timed_pipeline
    camunda_workflow.run_copilot_pipeline = timed_pipeline  # camunda router import ten truc tiep


def start_server(port: int):
    import uvicorn
    from app import main as app_main

    config = uvicorn.Config(app_main.app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(200):
        if server.started:
            return server, th, app_main
        time.sleep(0.1)
    raise RuntimeError("May chu khong khoi dong duoc trong 20 giay")


async def run_load(base, tokens, n_requests, n_users, warm=True):
    import httpx

    results = []  # dict cho moi request

    async def do(client, headers, kind, idx):
        if kind == "search":
            q = QUERIES[idx % len(QUERIES)]
            t = time.perf_counter()
            r = await client.get("/api/knowledge/passages", params={"q": q, "size": 10}, headers=headers)
            ms = (time.perf_counter() - t) * 1000
            ok = r.status_code == 200
            info = {"hits": len(r.json().get("items", [])) if ok else 0}
        else:
            text = TICKETS[idx % len(TICKETS)]
            t = time.perf_counter()
            r = await client.post("/api/copilot/analyze", json={"ticket_description": text}, headers=headers)
            ms = (time.perf_counter() - t) * 1000
            ok = r.status_code == 200
            body = r.json() if ok else {}
            info = {
                "hold": bool(body.get("is_hazard_escalated")),
                "citations": len(body.get("citations") or []),
            }
        return {"kind": kind, "idx": idx, "status": r.status_code, "ok": ok, "ms": ms, **info}

    async with httpx.AsyncClient(base_url=base, timeout=60) as client:
        if warm:
            h0 = tokens[0]
            for i in range(5):
                await do(client, h0, "search", i)
                await do(client, h0, "analyze", i)
            return_timings_clear()

        queue: asyncio.Queue = asyncio.Queue()
        for i in range(n_requests):
            kind = "search" if i % 2 == 0 else "analyze"
            queue.put_nowait((kind, i // 2))

        async def worker(w):
            headers = tokens[w % len(tokens)]
            while True:
                try:
                    kind, idx = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                res = await do(client, headers, kind, idx)
                res["worker"] = w
                results.append(res)

        t0 = time.perf_counter()
        await asyncio.gather(*(worker(w) for w in range(n_users)))
        wall = time.perf_counter() - t0
    return results, wall


_clear_hook = lambda: None  # noqa: E731


def return_timings_clear():
    _clear_hook()


def make_chart(path: Path, analyze_ms, search_ms, comp, limit_ms=30000):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    for ax, data, title, color in (
        (axes[0], analyze_ms, "Phân tích Copilot (đầu-cuối)", "#2563eb"),
        (axes[1], search_ms, "Tra cứu tri thức (đầu-cuối)", "#0f766e"),
    ):
        ax.hist(data, bins=20, color=color, alpha=0.85)
        p95 = pct(data, 95)
        ax.axvline(p95, color="#dc2626", linestyle="--", label=f"P95 = {p95:.0f} ms")
        ax.set_title(title)
        ax.set_xlabel("Độ trễ (ms)")
        ax.set_ylabel("Số request")
        ax.legend()
    names = ["Truy xuất\n(Retriever)", "Sinh văn bản\n(mẫu/luật)", "Lưu DB"]
    keys = ["retrieval", "generation", "save"]
    x = range(len(keys))
    p50 = [pct(comp[k], 50) if comp[k] else 0 for k in keys]
    p95 = [pct(comp[k], 95) if comp[k] else 0 for k in keys]
    w = 0.38
    axes[2].bar([i - w / 2 for i in x], p50, w, label="P50", color="#94a3b8")
    axes[2].bar([i + w / 2 for i in x], p95, w, label="P95", color="#f59e0b")
    axes[2].set_xticks(list(x))
    axes[2].set_xticklabels(names)
    axes[2].set_ylabel("ms (phía máy chủ)")
    axes[2].set_title("Tách thành phần của pipeline")
    axes[2].legend()
    fig.suptitle(f"CRM-66: 5 người dùng đồng thời, giới hạn P95 ≤ {limit_ms // 1000} giây (RFP OPS 02)", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=5)
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--apply-schema", action="store_true")
    ap.add_argument("--extra-passages", type=int, default=0)
    ap.add_argument("--out", default=str(REPO / "docs" / "qa"))
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url or not db_url.startswith("postgres"):
        sys.exit("Can dat DATABASE_URL tro toi PostgreSQL that, vi du postgresql://songnhat:songnhat_dev@localhost:5432/songnhat_copilot")
    sync_url = re.sub(r"^postgresql\+\w+://", "postgresql://", db_url)
    if args.apply_schema:
        apply_schema(sync_url)

    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    timings = ServerTimings()
    global _clear_hook
    _clear_hook = timings.clear

    port = free_port()
    from app import main as app_main  # noqa: F401  (import som de patch)
    install_timers(timings)
    server, th, app_main = start_server(port)
    try:
        import httpx

        assert app_main.engine.dialect.name == "postgresql", "Backend da chuyen sang SQLite: khong hop le"
        base = f"http://127.0.0.1:{port}"

        # tao nguoi dung (moi worker mot tai khoan) + dang nhap that
        from app.repositories import user_repository

        roles = ["support_agent", "technical_approver", "knowledge_steward", "administrator", "support_agent"]
        suffix = str(int(time.time()))[-6:]
        tokens = []
        with httpx.Client(base_url=base, timeout=60) as c:
            for i in range(args.users):
                email = f"load-{i}-{suffix}@songnhat.vn"
                user_repository.add_user(email, "Load-Test-Pass1!", full_name=f"Load {i}", role=roles[i % len(roles)])
                r = c.post("/api/auth/login", json={"email": email, "password": "Load-Test-Pass1!"})
                r.raise_for_status()
                tokens.append({"Authorization": f"Bearer {r.json()['access_token']}"})
            # nap kho tri thuc that bang CSV (neu da co thi upsert idempotent)
            c.get("/api/knowledge/passages", headers=tokens[0])
            with open(SAMPLE_CSV, "rb") as f:
                up = c.post("/api/v1/ingestion/upload", files={"file": ("curated_knowledge_passages.csv", f, "text/csv")},
                            data={"import_type": "increment"})
            if args.extra_passages:
                add_synthetic_passages(sync_url, args.extra_passages)
            total = c.get("/api/knowledge/passages", params={"size": 1}, headers=tokens[0]).json().get("total")
            print(f"Kho tri thuc: {total} doan (ingestion HTTP {up.status_code})")

        results, wall = asyncio.run(run_load(base, tokens, args.requests, args.users))
    finally:
        server.should_exit = True
        th.join(timeout=10)

    analyze = [r for r in results if r["kind"] == "analyze"]
    search = [r for r in results if r["kind"] == "search"]
    ok_all = [r["ms"] for r in results if r["ok"]]
    comp = {
        "retrieval": list(timings.retrieval_ms),
        "generation": list(timings.generation_ms),
        "save": list(timings.save_ms),
        "pipeline": list(timings.pipeline_ms),
    }
    summary = {
        "users": args.users,
        "requests": len(results),
        "wall_seconds": round(wall, 2),
        "throughput_rps": round(len(results) / wall, 2),
        "errors": sum(1 for r in results if not r["ok"]),
        "holds": sum(1 for r in analyze if r.get("hold")),
        "analyze_total": summarize([r["ms"] for r in analyze if r["ok"]]),
        "search_total": summarize([r["ms"] for r in search if r["ok"]]),
        "all_total": summarize(ok_all),
        "server_retrieval": summarize(comp["retrieval"]),
        "server_generation": summarize(comp["generation"]),
        "server_save_db": summarize(comp["save"]),
        "server_pipeline": summarize(comp["pipeline"]),
        "limit_p95_ms": 30000,
        "pass_p95_all": pct(ok_all, 95) <= 30000,
        "pass_p95_analyze": pct([r["ms"] for r in analyze if r["ok"]], 95) <= 30000,
        "knowledge_passages": total,
        "synthetic_passages_added": args.extra_passages,
        "ai_provider_called": False,
    }
    with open(out / "load_test_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(out / "load_test_raw.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["thu_tu", "loai", "worker", "http", "ms", "so_trich_dan", "bi_giu_lai"])
        for i, r in enumerate(results, 1):
            w.writerow([i, r["kind"], r["worker"], r["status"], round(r["ms"], 2), r.get("citations", ""), r.get("hold", "")])
    make_chart(out / "load_test_latency.png", [r["ms"] for r in analyze if r["ok"]], [r["ms"] for r in search if r["ok"]], comp)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
