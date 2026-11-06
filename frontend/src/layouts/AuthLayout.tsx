import { useEffect } from 'react'
import type { ReactNode } from 'react'

export default function AuthLayout({ children, title, className = '' }: { children: ReactNode; title: string; className?: string }) {
  useEffect(() => { document.title = `${title} | Support AI` }, [title])
  return <main className={`login-page ${className}`}>
    <aside className="login-intro">
      <span className="login-wordmark">SUPPORT AI</span>
      <div className="login-intro-copy"><h2>Hỗ trợ người dùng<br />thông minh hơn với AI</h2><p>Một nền tảng tập trung để tiếp nhận, quản lý và giải quyết yêu cầu hỗ trợ.</p><span className="login-tag">AI-POWERED SUPPORT</span></div>
      <small>SECURE • SIMPLE • SMART</small>
    </aside>
    <div className="login-form-side">{children}</div>
  </main>
}
