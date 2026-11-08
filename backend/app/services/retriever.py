"""Knowledge Base Retriever service for extracting technical citations (Task CRM-24)."""

import logging
from typing import Any, List, Optional

from app.schemas.copilot import CitationItem

logger = logging.getLogger(__name__)


def get_mock_knowledge_passages(query: str) -> List[CitationItem]:
    """Trả về danh sách 2-3 CitationItem mẫu để chạy độc lập khi chưa có kết nối DB.

    Args:
        query: Câu truy vấn hoặc mô tả sự cố từ ticket.

    Returns:
        Danh sách các đối tượng CitationItem liên quan đến truy vấn.
    """
    query_lower = query.lower()

    if "f0022" in query_lower or "biến tần" in query_lower or "tăng tốc" in query_lower:
        return [
            CitationItem(
                document_title="Tài liệu Hướng dẫn Xử lý Lỗi Biến tần SongNhat SN-G120",
                page_number=142,
                content_snippet=(
                    "Mã lỗi F0022 (Powerstack Fault / Quá dòng phần cứng): Xuất hiện khi "
                    "có dòng ngắn mạch tại IGBT, chạm đất đầu ra động cơ hoặc thời gian "
                    "tăng tốc (P1120) cài đặt quá ngắn so với quán tính tải."
                ),
            ),
            CitationItem(
                document_title="Sổ tay Bảo trì & Chẩn đoán Sự cố Truyền động Điện",
                page_number=58,
                content_snippet=(
                    "Khi lỗi F0022 xảy ra trong quá trình tăng tốc: (1) Kiểm tra cách điện "
                    "cáp động cơ bằng đồng hồ Megohmmeter; (2) Kéo dài thời gian tăng tốc "
                    "P1120; (3) Kiểm tra công suất định mức giữa biến tần và động cơ."
                ),
            ),
            CitationItem(
                document_title="Quy trình Thu thập Dữ kiện Kỹ thuật SongNhat (SOP-TECH-04)",
                page_number=12,
                content_snippet=(
                    "Đối với các lỗi ngắt mạch phần cứng trên biến tần, nhân viên hỗ trợ "
                    "cần thu thập Mã Serial (S/N), Phiên bản Firmware, thông số dòng điện "
                    "tại thời điểm ngắt (r0027) và ảnh chụp nhãn động cơ."
                ),
            ),
        ]

    return [
        CitationItem(
            document_title="Cẩm nang Kỹ thuật Thiết bị Tự động hóa SongNhat",
            page_number=24,
            content_snippet=(
                "Hướng dẫn kiểm tra sơ bộ hệ thống điều khiển: Xác minh nguồn cấp đầu vào, "
                "kiểm tra lịch sử mã cảnh báo trên màn hình BOP và đối chiếu sơ đồ đấu nối."
            ),
        ),
        CitationItem(
            document_title="Quy trình Hỗ trợ Kỹ thuật & Bảo hành SongNhat",
            page_number=9,
            content_snippet=(
                "Vui lòng cung cấp Mã Serial thiết bị, Phiên bản Firmware và mô tả điều kiện "
                "vận hành khi phát sinh sự cố để bộ phận kỹ thuật tra cứu hồ sơ."
            ),
        ),
    ]


class KnowledgeRetriever:
    """Class quản lý truy xuất đoạn văn bản kiến thức từ bảng `knowledge_passages`."""

    async def search_knowledge_passages(
        self,
        query: str,
        db: Optional[Any] = None,
        limit: int = 3,
    ) -> List[CitationItem]:
        """Truy vấn bảng `knowledge_passages` hoặc fallback về Mock Data khi db=None.

        Args:
            query: Nội dung truy vấn tìm kiếm tài liệu.
            db: Phiên kết nối cơ sở dữ liệu (AsyncSession hoặc Session). Mặc định là None.
            limit: Số lượng trích dẫn tối đa cần lấy.

        Returns:
            Danh sách các `CitationItem` trích xuất được.
        """
        if db is None:
            return get_mock_knowledge_passages(query)[:limit]

        try:
            # Truy vấn bảng knowledge_passages khi có kết nối Database thực tế
            from sqlalchemy import text

            sql = text(
                """
                SELECT document_title, page_number, content_snippet
                FROM knowledge_passages
                WHERE content_snippet ILIKE :pattern
                   OR document_title ILIKE :pattern
                LIMIT :limit
                """
            )
            params = {"pattern": f"%{query.strip()}%", "limit": limit}

            result = db.execute(sql, params)
            if hasattr(result, "__await__"):
                result = await result

            rows = result.fetchall()
            if rows:
                return [
                    CitationItem(
                        document_title=str(row.document_title),
                        page_number=int(row.page_number),
                        content_snippet=str(row.content_snippet),
                    )
                    for row in rows
                ]
        except Exception as exc:
            logger.warning(
                "Không thể truy vấn bảng knowledge_passages (%s), chuyển sang dùng Mock Data.",
                exc,
            )

        return get_mock_knowledge_passages(query)[:limit]


async def search_knowledge_passages(
    query: str,
    db: Optional[Any] = None,
) -> List[CitationItem]:
    """Hàm tiện ích truy vấn tài liệu kiến thức từ bảng `knowledge_passages`.

    Args:
        query: Câu truy vấn tìm kiếm bằng chứng kỹ thuật.
        db: Kết nối cơ sở dữ liệu (tùy chọn).

    Returns:
        Danh sách `CitationItem` phù hợp.
    """
    retriever = KnowledgeRetriever()
    return await retriever.search_knowledge_passages(query=query, db=db)
