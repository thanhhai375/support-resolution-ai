export interface KnowledgeExcerpt { id: string; productLine: 'Motors' | 'Drives'; title: string; document: string; page: number; content: string; revision: string }
const topics = ['Xử lý quá nhiệt', 'Môi trường vận hành', 'Kiểm tra rung động', 'Thông tin nhãn thiết bị', 'Lịch sử cảnh báo', 'Bảo trì định kỳ']
// Illustrative fixtures, not the actual approved technical corpus.
export const knowledgeExcerpts: KnowledgeExcerpt[] = Array.from({ length: 300 }, (_, i) => {
  const productLine = i < 150 ? 'Motors' : 'Drives'
  const section = Math.floor((i % 150) / 6) + 1
  return { id: `KB-${String(i + 1).padStart(3, '0')}`, productLine, title: `${topics[i % 6]} — ${productLine} / mục ${section}`, document: `${productLine} — Tài liệu minh họa ${section}`, page: 12 + i % 150, revision: 'REV 01', content: `${topics[i % 6]}: Thu thập model, serial, mã cảnh báo và điều kiện vận hành. Đối chiếu tài liệu đúng model và phiên bản trước khi đưa ra hướng dẫn. Công việc kiểm tra và bảo trì phải do nhân sự được phân quyền thực hiện theo quy trình an toàn tại cơ sở.` }
})
export const normalizeSearch = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase()
