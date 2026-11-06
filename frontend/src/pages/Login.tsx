import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { readClaims } from '../auth/token'
import AuthLayout from '../layouts/AuthLayout'
import { createDemoToken, DEMO_AUTH_ENABLED, DEMO_EMAIL, DEMO_PASSWORD } from '../auth/demo'

export default function Login() {
  const { token, signIn } = useAuth()
  const location = useLocation()
  const registeredEmail: unknown = (location.state as { registeredEmail?: unknown } | null)?.registeredEmail
  const [email, setEmail] = useState(typeof registeredEmail === 'string' ? registeredEmail : '')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [remember, setRemember] = useState(false)
  const [showResetHelp, setShowResetHelp] = useState(false)
  const from: unknown = (location.state as { from?: unknown } | null)?.from
  const destination = typeof from === 'string' && /^\/(?!\/)/.test(from) && !from.includes('\\') && !from.startsWith('/login')
    ? from : '/dashboard'

  if (readClaims(token)) return <Navigate to={destination} replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      if (DEMO_AUTH_ENABLED) {
        signIn(createDemoToken(email, password), remember)
        return
      }
      const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
      const response = await fetch(`${baseUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
        signal: AbortSignal.timeout(15_000),
      })
      if (!response.ok) throw new Error(response.status === 401
        ? 'Email hoặc mật khẩu không đúng.' : 'Không thể đăng nhập. Vui lòng thử lại sau.')
      const payload: unknown = await response.json()
      if (typeof payload !== 'object' || payload === null
        || !('access_token' in payload) || typeof payload.access_token !== 'string') {
        throw new Error('Phản hồi đăng nhập không hợp lệ.')
      }
      signIn(payload.access_token, remember)
    } catch (cause) {
      setError(cause instanceof TypeError || (cause instanceof DOMException && cause.name === 'TimeoutError')
        ? 'Không kết nối được máy chủ đăng nhập. Vui lòng thử lại.'
        : cause instanceof Error ? cause.message : 'Đăng nhập thất bại.')
    } finally { setPending(false) }
  }

  return <AuthLayout title="Đăng nhập tài khoản">
    <section className="login-card" aria-labelledby="login-title">
      <h1 id="login-title">Đăng nhập tài khoản</h1>
      <p className="subtitle">Chào mừng bạn quay trở lại hệ thống</p>
      {DEMO_AUTH_ENABLED && <div className="demo-login-note" role="note"><strong>Chế độ demo — không cần backend</strong><span>{DEMO_EMAIL} / {DEMO_PASSWORD}</span><button type="button" onClick={() => { setEmail(DEMO_EMAIL); setPassword(DEMO_PASSWORD); setError('') }}>Điền tài khoản demo</button></div>}
      {typeof registeredEmail === 'string' && <p className="auth-success" role="status">Đăng ký thành công. Bạn có thể đăng nhập bằng tài khoản vừa tạo.</p>}
      <form onSubmit={submit} className="login-form">
        <label className="field-label">Email<input type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} placeholder="name@company.com" disabled={pending} /></label>
        <label className="field-label">Mật khẩu<input type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} placeholder="Nhập mật khẩu" disabled={pending} /></label>
        <div className="login-options"><label><input type="checkbox" checked={remember} onChange={event => setRemember(event.target.checked)} /> Ghi nhớ đăng nhập</label><button type="button" onClick={() => setShowResetHelp(true)}>Quên mật khẩu?</button></div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button login-submit" disabled={pending}>{pending ? 'Đang đăng nhập…' : 'Đăng nhập'}</button>
      </form>
      <p className="login-footer">Bằng việc đăng nhập, bạn đồng ý với chính sách bảo mật của hệ thống.</p>
      <p className="login-footer auth-switch">Chưa có tài khoản? <Link to="/register">Đăng ký tài khoản</Link></p>
    </section>
    {showResetHelp && <div className="modal-backdrop"><section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="reset-title"><h2 id="reset-title">Quên mật khẩu?</h2><p className="subtitle">Vui lòng liên hệ quản trị viên để được hỗ trợ đặt lại mật khẩu.</p><button autoFocus className="primary-button dialog-action" onClick={() => setShowResetHelp(false)}>Đóng</button></section></div>}
  </AuthLayout>
}
