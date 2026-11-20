import { normalizeRole, type UserRole } from '../auth/token'
import {
  createDemoToken,
  DEMO_AUTH_ENABLED,
} from '../auth/demo'

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
}

export async function login(
  credentials: LoginRequest
): Promise<LoginResponse> {
  const email = credentials.email.trim()
  const password = credentials.password

  // Mock authentication - development only
  if (DEMO_AUTH_ENABLED) {
    await new Promise<void>(resolve => {
      setTimeout(resolve, 400)
    })

    return {
      access_token: createDemoToken(email, password),
    }
  }

  // Real Backend authentication
  const baseUrl = (
    import.meta.env.VITE_API_BASE_URL ?? ''
  ).replace(/\/$/, '')

  let response: Response

  try {
    response = await fetch(
      `${baseUrl}/api/auth/login`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
        signal: AbortSignal.timeout(15000),
      }
    )
  } catch {
    throw new Error(
      'Không kết nối được máy chủ đăng nhập.'
    )
  }

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error(
        'Email hoặc mật khẩu không đúng.'
      )
    }

    throw new Error(
      'Không thể đăng nhập. Vui lòng thử lại sau.'
    )
  }

  let payload: unknown

  try {
    payload = await response.json()
  } catch {
    throw new Error(
      'Phản hồi từ máy chủ không hợp lệ.'
    )
  }

  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('access_token' in payload) ||
    typeof payload.access_token !== 'string' ||
    !payload.access_token
  ) {
    throw new Error(
      'Máy chủ không trả về Access Token hợp lệ.'
    )
  }

  return {
    access_token: payload.access_token,
  }
}

export interface CurrentUser {
  id: string
  email: string
  role: UserRole
  full_name: string
}

export async function getCurrentUser(
  token: string
): Promise<CurrentUser> {
  const baseUrl = (
    import.meta.env.VITE_API_BASE_URL ?? ''
  ).replace(/\/$/, '')

  const response = await fetch(
    `${baseUrl}/api/auth/me`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal: AbortSignal.timeout(15000),
    }
  )

  if (response.status === 401) {
    throw new Error(
      'Phiên đăng nhập không hợp lệ hoặc đã hết hạn.'
    )
  }

  if (response.status === 403) {
    throw new Error(
      'Bạn không có quyền truy cập hệ thống.'
    )
  }

  if (!response.ok) {
    throw new Error(
      'Không thể tải thông tin người dùng.'
    )
  }

  const payload = await response.json()

  const role = normalizeRole(payload?.role)

  if (
    !role ||
    typeof payload.id !== 'string' ||
    typeof payload.email !== 'string' ||
    typeof payload.full_name !== 'string'
  ) {
    throw new Error(
      'Thông tin tài khoản hoặc vai trò không hợp lệ.'
    )
  }

  return {
    id: payload.id,
    email: payload.email,
    role,
    full_name: payload.full_name,
  }
}

export async function revokeAccessToken(
  token: string
): Promise<void> {
  const baseUrl = (
    import.meta.env.VITE_API_BASE_URL ?? ''
  ).replace(/\/$/, '')

  const response = await fetch(
    `${baseUrl}/api/auth/revoke`,
    {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal: AbortSignal.timeout(15000),
    }
  )

  if (response.status === 401) {
    return
  }

  if (response.status !== 204) {
    throw new Error(
      'Không thể thu hồi phiên đăng nhập.'
    )
  }
}
