import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { readClaims } from '../auth/token'
import AuthLayout from '../layouts/AuthLayout'

export default function Register() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  if (readClaims(token)) return <Navigate to="/dashboard" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    setError('')
    if (!fullName.trim()) { setError('Vui lòng nhập họ và tên.'); return }
    if (password.length < 8) { setError('Mật khẩu cần ít nhất 8 ký tự.'); return }
    if (new TextEncoder().encode(password).length > 72) { setError('Mật khẩu quá dài, vui lòng dùng tối đa 72 byte.'); return }
    if (password !== confirmation) { setError('Mật khẩu xác nhận không trùng khớp.'); return }
    if (!accepted) { setError('Vui lòng đồng ý với Điều khoản sử dụng.'); return }
    setPending(true)
    try {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
      const response = await fetch(`${baseUrl}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName.trim(), email: email.trim(), password }),
        signal: AbortSignal.timeout(15_000),
      })
      if (!response.ok) {
        if (response.status === 409) throw new Error('Email này đã được đăng ký. Vui lòng dùng email khác hoặc đăng nhập.')
        if (response.status === 404 || response.status === 405) throw new Error('Máy chủ hiện chưa hỗ trợ đăng ký tài khoản. Vui lòng liên hệ quản trị viên.')
        if (response.status === 400 || response.status === 422) throw new Error('Thông tin đăng ký chưa hợp lệ. Vui lòng kiểm tra lại.')
        throw new Error('Không thể đăng ký lúc này. Vui lòng thử lại sau.')
      }
      navigate('/login', { replace: true, state: { registeredEmail: email.trim() } })
    } catch (cause) {
      setError(cause instanceof TypeError || (cause instanceof DOMException && cause.name === 'TimeoutError')
        ? 'Không kết nối được máy chủ đăng ký. Vui lòng thử lại.'
        : cause instanceof Error ? cause.message : 'Đăng ký thất bại.')
    } finally { setPending(false) }
  }

  return <AuthLayout title="Tạo tài khoản mới" className="register-page">
    <section className="login-card" aria-labelledby="register-title">
      <h1 id="register-title">Tạo tài khoản mới</h1>
      <p className="subtitle">Đăng ký để bắt đầu sử dụng Support AI</p>
      <form className="login-form register-form" onSubmit={submit} aria-busy={pending}>
        <label className="field-label">Họ và tên<input autoComplete="name" required maxLength={100} placeholder="Nguyễn Văn A" value={fullName} onChange={event => setFullName(event.target.value)} disabled={pending} /></label>
        <label className="field-label">Email<input type="email" autoComplete="email" required maxLength={254} placeholder="name@company.com" value={email} onChange={event => setEmail(event.target.value)} disabled={pending} /></label>
        <label className="field-label">Mật khẩu<input type="password" autoComplete="new-password" required minLength={8} maxLength={72} aria-describedby="password-hint" placeholder="Ít nhất 8 ký tự" value={password} onChange={event => setPassword(event.target.value)} disabled={pending} /></label>
        <span id="password-hint" className="sr-only">Mật khẩu có ít nhất 8 ký tự, tối đa 72 byte.</span>
        <label className="field-label">Xác nhận mật khẩu<input type="password" autoComplete="new-password" required minLength={8} maxLength={72} placeholder="Nhập lại mật khẩu" value={confirmation} onChange={event => setConfirmation(event.target.value)} disabled={pending} /></label>
        <div className="login-options"><label><input type="checkbox" required checked={accepted} onChange={event => setAccepted(event.target.checked)} disabled={pending} /> Tôi đồng ý với Điều khoản sử dụng</label></div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button type="submit" className="primary-button login-submit" disabled={pending}>{pending ? 'Đang đăng ký…' : 'Đăng ký tài khoản'}</button>
      </form>
      <p className="login-footer auth-switch">Đã có tài khoản? <Link to="/login">Đăng nhập</Link></p>
    </section>
  </AuthLayout>
}
