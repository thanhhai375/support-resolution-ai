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
