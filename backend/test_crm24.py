"""Script test độc lập cho Task CRM-24: Copilot Engine (Incident Analysis & Evidence Extraction)."""

import asyncio
import sys

from app.services.copilot_engine import CopilotEngineService


async def main() -> None:
    """Chạy kiểm thử bất đồng bộ 2 kịch bản cho CopilotEngineService."""
    # Đảm bảo hiển thị tiếng Việt UTF-8 trên Windows console
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    engine = CopilotEngineService()

    # -------------------------------------------------------------------------
    # Kịch bản 1: Ticket kỹ thuật thông thường
    # -------------------------------------------------------------------------
    scenario_1_ticket = "Biến tần báo lỗi F0022 khi tăng tốc"
    print("=" * 80)
    print(f"KỊCH BẢN 1 (Ticket thường): {scenario_1_ticket}")
    print("=" * 80)
    result_1 = await engine.analyze_ticket(scenario_1_ticket)
    print(result_1.model_dump_json(indent=2))
    print()

    # -------------------------------------------------------------------------
    # Kịch bản 2: Ticket có dấu hiệu nguy hiểm (Cháy nổ / Bốc khói)
    # -------------------------------------------------------------------------
    scenario_2_ticket = "Động cơ bốc khói và có tiếng nổ nhẹ"
    print("=" * 80)
    print(f"KỊCH BẢN 2 (Ticket nguy hiểm): {scenario_2_ticket}")
    print("=" * 80)
    result_2 = await engine.analyze_ticket(scenario_2_ticket)
    print(result_2.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
