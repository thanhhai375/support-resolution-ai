import { useState } from 'react'
import { BookOpen, Search } from 'lucide-react'

export default function KnowledgeBase() {
  const [query, setQuery] = useState('')
  return <>
    <div className="page-title-row"><div><h1>Thư viện tài liệu</h1><p className="subtitle">Tra cứu kiến thức và bằng chứng hỗ trợ kỹ thuật</p></div></div>
    <section className="panel">
      <label className="search-box"><Search size={18} aria-hidden="true" /><input aria-label="Tìm tài liệu" placeholder="Tìm tài liệu, thiết bị, hướng dẫn…" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <div className="flex flex-col items-center gap-4 py-16 text-center" role="status"><BookOpen size={40} className="text-brand" /><h2>{query ? 'Không tìm thấy tài liệu' : 'Chưa có tài liệu trong thư viện'}</h2><p className="subtitle">{query ? 'Thử tìm bằng tên thiết bị hoặc từ khóa khác.' : 'Tài liệu kỹ thuật sẽ xuất hiện tại đây khi được bổ sung.'}</p></div>
    </section>
  </>
}
