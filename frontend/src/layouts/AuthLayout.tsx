import { useEffect } from 'react'
import type { ReactNode } from 'react'

export default function AuthLayout({ children, title, className = '' }: { children: ReactNode; title: string; className?: string }) {
  useEffect(() => { document.title = `${title} | Support AI` }, [title])
  return <main className={`login-page ${className}`}>
    <aside className="login-intro">
      <span className="login-wordmark">SN SONGNHAT</span>
      <div className="login-intro-copy"><h2>Support<br />Resolution AI</h2><p>Trợ lý AI hỗ trợ xử lý sự cố<br />và vận hành thiết bị công nghiệp</p><div className="assistant-art" aria-hidden="true"><div className="assistant-head"><i /><span>⌣</span><i /></div></div></div>
      <small>✦ Tra cứu tài liệu　✦ Gợi ý xử lý　✦ An toàn</small>
    </aside>
    <div className="login-form-side">{children}</div>
  </main>
}
