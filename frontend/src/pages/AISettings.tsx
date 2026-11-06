import { Bot, ShieldCheck } from 'lucide-react'

export default function AISettings() {
  return <>
    <div className="page-title-row"><div><h1>AI Settings</h1><p className="subtitle">Quản lý cấu hình trợ lý AI cho không gian làm việc.</p></div></div>
    <section className="panel settings-panel">
      <span className="settings-icon"><Bot size={28} aria-hidden="true" /></span>
      <h2>Cấu hình trợ lý AI</h2>
      <p>Chức năng cấu hình đang được phát triển.</p>
      <p>Bạn sẽ có thể quản lý phân loại ticket và gợi ý phản hồi tại đây.</p>
      <span className="settings-policy"><ShieldCheck size={16} aria-hidden="true" /> Nhân viên kiểm tra gợi ý trước khi áp dụng.</span>
    </section>
  </>
}
