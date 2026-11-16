import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { knowledgeExcerpts, normalizeSearch } from '../data/knowledge'
import type { KnowledgeExcerpt } from '../data/knowledge'
import SourceViewer from '../components/SourceViewer'
import '../knowledge.css'
const PAGE_SIZE = 12
export default function KnowledgeBase() {
  const [params, setParams] = useSearchParams()
  const query = params.get('search') ?? ''
  const product = ['Motors', 'Drives'].includes(params.get('product') ?? '') ? params.get('product')! : 'all'
  const requestedPage = Number(params.get('page') ?? 1)
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  function setQuery(value: string) { setParams({ search: value, product }, { replace: true }) }
  function setProduct(value: string) { setParams({ search: query, product: value }) }
  function setPage(value: number) { setParams({ search: query, product, page: String(value) }) }
  const [selected, setSelected] = useState<KnowledgeExcerpt | null>(null)
  const results = useMemo(() => {
    const terms = normalizeSearch(query).trim().split(/\s+/).filter(Boolean)
    return knowledgeExcerpts.filter(item => (product === 'all' || item.productLine === product) && terms.every(term => normalizeSearch(`${item.id} ${item.title} ${item.document} ${item.content}`).includes(term)))
  }, [query, product])
  const pages = Math.max(1, Math.ceil(results.length / PAGE_SIZE))
  const currentPage = Math.min(page, pages)
  const start = (currentPage - 1) * PAGE_SIZE
  return <>
    <div className="page-title-row"><div><h1>Kho tri thức kỹ thuật</h1><p className="subtitle">Tra cứu đoạn trích và đối chiếu tài liệu nguồn · REV 01 / WP 03</p></div></div>
    <p className="kb-demo">Bộ dữ liệu minh họa: 300 đoạn trích mô phỏng trạng thái đã phê duyệt (150 Motors, 150 Drives). Chưa kết nối kho tri thức thực tế.</p>
    <section className="panel kb-toolbar" aria-label="Bộ lọc tri thức">
      <label className="search-box"><input type="search" aria-label="Tìm đoạn trích" placeholder="Tìm nội dung, tên tài liệu, mã KB…" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <label className="field-label">Dòng sản phẩm<select value={product} onChange={event => setProduct(event.target.value)}><option value="all">Tất cả sản phẩm</option><option value="Motors">Motors</option><option value="Drives">Drives</option></select></label>
      <button className="secondary-button" onClick={() => setParams({})}>Xóa bộ lọc</button>
    </section>
    <p role="status" className="subtitle">{results.length} đoạn trích · {results.length ? `${start + 1}–${Math.min(start + PAGE_SIZE, results.length)}` : '0'} / {results.length}</p>
    {results.length ? <div className="kb-grid">{results.slice(start, start + PAGE_SIZE).map(item => <article className="panel kb-card" key={item.id}>
      <div className="kb-tags"><span>{item.productLine}</span><span>Đã phê duyệt · mẫu</span></div><small>{item.id} · {item.revision}</small><h2>{item.title}</h2><p>{item.content}</p><div className="subtitle">{item.document} · Trang {item.page}</div><button className="secondary-button" onClick={() => setSelected(item)}>Xem nguồn {item.id}</button>
    </article>)}</div> : <section className="panel kb-empty"><h2>Không tìm thấy đoạn trích</h2><p>Thử từ khóa khác hoặc xóa bộ lọc sản phẩm.</p></section>}
    {results.length > 0 && <nav className="kb-pagination" aria-label="Phân trang tri thức"><button className="secondary-button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Trang trước</button><span>Trang {currentPage} / {pages}</span><button className="secondary-button" disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Trang sau</button></nav>}
    <SourceViewer excerpt={selected} onClose={() => setSelected(null)} />
  </>
}
