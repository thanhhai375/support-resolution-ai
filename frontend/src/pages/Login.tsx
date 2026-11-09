
import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  Link,
  Navigate,
  useLocation,
} from 'react-router-dom'

import { useAuth } from '../auth/AuthProvider'
import { readClaims } from '../auth/token'
import AuthLayout from '../layouts/AuthLayout'

import {
  DEMO_AUTH_ENABLED,
  DEMO_EMAIL,
  DEMO_PASSWORD,
} from '../auth/demo'

import { login } from '../services/authService'

import { validateLogin } from '../utils/loginValidation'
import type { LoginFormErrors } from '../utils/loginValidation'

export default function Login() {
  const { token, signIn } = useAuth()
  const location = useLocation()

  const registeredEmail: unknown = (
    location.state as {
      registeredEmail?: unknown
    } | null
  )?.registeredEmail

  const [email, setEmail] = useState(
    typeof registeredEmail === 'string'
      ? registeredEmail
      : ''
  )

  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  const [fieldErrors, setFieldErrors] =
    useState<LoginFormErrors>({})

  const [showPassword, setShowPassword] = useState(false)
  const [showResetHelp, setShowResetHelp] = useState(false)

  const from: unknown = (
    location.state as { from?: unknown } | null
  )?.from

  const destination =
    typeof from === 'string' &&
    /^\/(?!\/)/.test(from) &&
    !from.includes('\\') &&
    !from.startsWith('/login')
      ? from
      : '/dashboard'

  if (readClaims(token)) {
    return <Navigate to={destination} replace />
  }

  async function submit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault()

    if (pending) return

    const errors = validateLogin({
      email,
      password,
    })

    setFieldErrors(errors)
    setError('')

    if (Object.keys(errors).length > 0) {
      return
    }

    setPending(true)

    try {
      const response = await login({
        email,
        password,
      })

      signIn(response.access_token)
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Đăng nhập thất bại.'
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthLayout title="Đăng nhập tài khoản">
      <section
        className="login-card"
        aria-labelledby="login-title"
      >
        <h1 id="login-title">
          Đăng nhập vào hệ thống
        </h1>

        <p className="subtitle">
          Không gian làm việc của nhân viên hỗ trợ
        </p>

        <div className="staff-roles">
          <span>Support Agent</span>
          <span>Technical Approver</span>
        </div>

        {DEMO_AUTH_ENABLED && (
          <div
            className="demo-login-note"
            role="note"
          >
            <strong>
              Chế độ demo — không cần backend
            </strong>

            <span>
              {DEMO_EMAIL} / {DEMO_PASSWORD}
            </span>

            <button
              type="button"
              onClick={() => {
                setEmail(DEMO_EMAIL)
                setPassword(DEMO_PASSWORD)
                setError('')
                setFieldErrors({})
              }}
            >
              Điền tài khoản demo
            </button>
          </div>
        )}

        {typeof registeredEmail === 'string' && (
          <p
            className="auth-success"
            role="status"
          >
            Đăng ký thành công. Bạn có thể đăng nhập
            bằng tài khoản vừa tạo.
          </p>
        )}

        <form
          onSubmit={submit}
          className="login-form"
          noValidate
        >
          <label className="field-label">
            Email

            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={event => {
                setEmail(event.target.value)
                setFieldErrors(prev => ({
                  ...prev,
                  email: undefined,
                }))
              }}
              placeholder="name@company.com"
              disabled={pending}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={
                fieldErrors.email
                  ? 'login-email-error'
                  : undefined
              }
            />

            {fieldErrors.email && (
              <span
                id="login-email-error"
                className="form-error"
                role="alert"
              >
                {fieldErrors.email}
              </span>
            )}
          </label>

          <label
            className="field-label"
            htmlFor="login-password"
          >
            Mật khẩu
          </label>

          <div className="password-field">
            <input
              id="login-password"
              type={
                showPassword
                  ? 'text'
                  : 'password'
              }
              autoComplete="current-password"
              value={password}
              onChange={event => {
                setPassword(event.target.value)
                setFieldErrors(prev => ({
                  ...prev,
                  password: undefined,
                }))
              }}
              placeholder="Nhập mật khẩu"
              disabled={pending}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={
                fieldErrors.password
                  ? 'login-password-error'
                  : undefined
              }
            />

            <button
              type="button"
              aria-label={
                showPassword
                  ? 'Ẩn mật khẩu'
                  : 'Hiện mật khẩu'
              }
              aria-pressed={showPassword}
              onClick={() => {
                setShowPassword(!showPassword)
              }}
            >
              {showPassword ? 'Ẩn' : 'Hiện'}
            </button>
          </div>

          {fieldErrors.password && (
            <p
              id="login-password-error"
              className="form-error"
              role="alert"
            >
              {fieldErrors.password}
            </p>
          )}

          <div className="login-options">
            <span>
              Phiên đăng nhập được lưu trên thiết bị này
            </span>

            <button
              type="button"
              onClick={() => setShowResetHelp(true)}
            >
              Quên mật khẩu?
            </button>
          </div>

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="primary-button login-submit"
            disabled={pending}
          >
            {pending
              ? 'Đang đăng nhập…'
              : 'Đăng nhập'}
          </button>
        </form>

        <p className="login-footer">
          Bằng việc đăng nhập, bạn đồng ý với
          chính sách bảo mật của hệ thống.
        </p>

        <p className="login-footer auth-switch">
          Chưa có tài khoản?{' '}
          <Link to="/register">
            Đăng ký tài khoản
          </Link>
        </p>
      </section>

      {showResetHelp && (
        <div className="modal-backdrop">
          <section
            className="dialog-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-title"
          >
            <h2 id="reset-title">
              Quên mật khẩu?
            </h2>

            <p className="subtitle">
              Vui lòng liên hệ quản trị viên
              để được hỗ trợ đặt lại mật khẩu.
            </p>

            <button
              autoFocus
              className="primary-button dialog-action"
              onClick={() => setShowResetHelp(false)}
            >
              Đóng
            </button>
          </section>
        </div>
      )}
    </AuthLayout>
  )
}
