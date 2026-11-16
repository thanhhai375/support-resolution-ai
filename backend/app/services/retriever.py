"""Knowledge Base Retriever service for extracting technical citations (Tasks CRM-24 & CRM-28)."""

import inspect
import logging
import re
from typing import Any, List, Optional

from app.schemas.copilot import CitationItem

logger = logging.getLogger(__name__)


def get_mock_knowledge_passages(query: str) -> List[CitationItem]:
    """Trả về danh sách 2-3 CitationItem mẫu để chạy độc lập khi chưa có kết nối DB hoặc bảng rỗng.

    Args:
        query: Câu truy vấn hoặc mô tả sự cố từ ticket.

    Returns:
        Danh sách các đối tượng CitationItem liên quan đến truy vấn.
    """
    query_lower = query.lower()

    if any(k in query_lower for k in ["f0022", "biến tần", "tăng tốc", "inverter"]):
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

    if any(k in query_lower for k in ["tài liệu", "manual", "sơ đồ", "hướng dẫn", "catalog", "datasheet"]):
        return [
            CitationItem(
                document_title="Tài liệu Hướng dẫn Vận hành & Cài đặt Biến tần SongNhat SN-G120",
                page_number=15,
                content_snippet=(
                    "Sơ đồ đấu nối mạch động lực và điều khiển: Chân DI0-DI3 nhận tín hiệu "
                    "kích hoạt RUN/STOP, cổng RS485 hỗ trợ giao thức Modbus RTU cho PLC."
                ),
            ),
            CitationItem(
                document_title="Sơ đồ Đấu nối Điều khiển và Động lực Hệ thống Tự động hóa SongNhat",
                page_number=32,
                content_snippet=(
                    "Bản vẽ sơ đồ nguyên lý mạch điều khiển biến tần và động cơ xoay chiều: "
                    "Yêu cầu gắn biến trở điều tốc tại chân AI0 và điện trở xả hãm nếu tải quán tính lớn."
                ),
            ),
        ]

    if any(k in query_lower for k in ["tiến độ", "bảo hành", "sửa", "dịch vụ"]):
        return [
            CitationItem(
                document_title="Quy trình Tiếp nhận Dịch vụ & Tra cứu Tiến độ Sửa chữa SongNhat",
                page_number=8,
                content_snippet=(
                    "Mỗi phiếu dịch vụ được cấp mã theo dõi duy nhất. Nhân viên dịch vụ có trách "
                    "nhiệm cập nhật tình trạng kiểm tra và thời gian hoàn tất dự kiến trong vòng 24 giờ."
                ),
            ),
            CitationItem(
                document_title="Chính sách Bảo hành & Thời hạn Trả máy Thiết bị Tự động hóa",
                page_number=14,
                content_snippet=(
                    "Thời gian thẩm định và thông báo phương án xử lý sự cố thiết bị không vượt quá "
                    "48 giờ làm việc kể từ thời điểm nhận thiết bị tại trung tâm dịch vụ."
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
        """Truy vấn bảng `knowledge_passages` hoặc fallback về Mock Data khi db=None hoặc rỗng.

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
            try:
                from models import KnowledgePassage
            except ImportError:
                from backend.models import KnowledgePassage

            from sqlalchemy import or_, select

            # Trích xuất các từ khóa đặc trưng (Mã lỗi, model hoặc từ có độ dài >= 4)
            keywords: List[str] = []
            error_codes = re.findall(r"[A-Za-z0-9]+-[A-Za-z0-9]+|[A-Za-z]\d{3,5}", query)
            keywords.extend(error_codes)

            for w in query.strip().split():
                clean_w = re.sub(r"[^\w]", "", w)
                if (
                    len(clean_w) >= 4
                    and clean_w.lower() not in ["biến", "động", "thiết", "thường", "không"]
                ):
                    keywords.append(clean_w)

            if not keywords:
                keywords = [query.strip()]

            filters = []
            for kw in keywords[:4]:
                pattern = f"%{kw}%"
                filters.append(KnowledgePassage.passage_content.ilike(pattern))
                filters.append(KnowledgePassage.document_name.ilike(pattern))
                filters.append(KnowledgePassage.section_name.ilike(pattern))

            stmt = select(KnowledgePassage).where(or_(*filters)).limit(limit)

            result = db.execute(stmt)
            if inspect.isawaitable(result):
                result = await result

            passages = (
                result.scalars().all()
                if hasattr(result, "scalars")
                else result.fetchall()
            )

            if passages:
                citations: List[CitationItem] = []
                for p in passages:
                    doc_title = (
                        getattr(p, "document_title", None)
                        or getattr(p, "document_name", None)
                        or "Tài liệu kỹ thuật SongNhat"
                    )
                    snippet = (
                        getattr(p, "content_snippet", None)
                        or getattr(p, "passage_content", None)
                        or ""
                    )
                    page_num = getattr(p, "page_number", 1) or 1
                    citations.append(
                        CitationItem(
                            document_title=str(doc_title),
                            page_number=int(page_num),
                            content_snippet=str(snippet),
                        )
                    )
                return citations
        except Exception as exc:
            logger.warning(
                "Không thể truy vấn bảng knowledge_passages (%s), chuyển sang dùng Mock Data.",
                exc,
            )

        # Fallback về Mock Data khi bảng rỗng hoặc có lỗi
        return get_mock_knowledge_passages(query)[:limit]


async def search_knowledge_passages(
    query: str,
    db: Optional[Any] = None,
    limit: int = 3,
) -> List[CitationItem]:
    """Hàm tiện ích truy vấn tài liệu kiến thức từ bảng `knowledge_passages`.

    Args:
        query: Câu truy vấn tìm kiếm bằng chứng kỹ thuật.
        db: Kết nối cơ sở dữ liệu (tùy chọn).
        limit: Số lượng kết quả tối đa.

    Returns:
        Danh sách `CitationItem` phù hợp.
    """
    retriever = KnowledgeRetriever()
    return await retriever.search_knowledge_passages(query=query, db=db, limit=limit)
