import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import type { KnowledgeExcerpt } from '../data/knowledge'
import '../knowledge.css'
export default function SourceViewer({ excerpt, onClose }: { excerpt: KnowledgeExcerpt | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (!excerpt) return
    const previous = document.activeElement as HTMLElement | null
    const element = dialog.current
    element?.showModal()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { element?.close(); document.body.style.overflow = overflow; previous?.focus() }
  }, [excerpt])
  if (!excerpt) return null
  return createPortal(<dialog ref={dialog} className="kb-dialog" aria-labelledby="source-title" onCancel={event => { event.preventDefault(); onClose() }} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <div className="kb-dialog-body"><header><div><small>SOURCE VIEWER · {excerpt.id}</small><h2 id="source-title">{excerpt.title}</h2></div><button className="secondary-button" autoFocus aria-label="Đóng Source Viewer" onClick={onClose}>✕</button></header>
      <p className="kb-demo">Dữ liệu minh họa — không phải tài liệu kỹ thuật đã phê duyệt thực tế.</p>
      <div className="kb-tags"><span>{excerpt.productLine}</span><span>{excerpt.revision}</span><span>Đã phê duyệt · mẫu</span></div>
      <p>{excerpt.document}</p><p>Trang {excerpt.page}</p><section className="kb-source-page" aria-label="Đoạn trích nguồn"><small>ĐOẠN TRÍCH · TRANG {excerpt.page}</small><blockquote>{excerpt.content}</blockquote></section>
      <footer><span className="subtitle">Hiển thị đoạn trích; chưa có file PDF gốc.</span><button className="primary-button" onClick={onClose}>Đóng</button></footer>
    </div></dialog>, document.body)
}
