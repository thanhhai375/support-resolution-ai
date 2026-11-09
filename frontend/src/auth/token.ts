
import { DEMO_AUTH_ENABLED } from './demo'

export const TOKEN_KEY = 'access_token'

export interface JwtClaims {
  sub: string
  exp: number
  name?: string
}

// Chỉ kiểm tra cấu trúc và thời hạn JWT phía client.
// Backend phải xác minh chữ ký và quyền truy cập.
export function readClaims(
  token: string | null
): JwtClaims | null {
  if (!token) return null

  try {
    const parts = token.split('.')

    if (
      parts.length !== 3 ||
      parts.some(part => !/^[A-Za-z0-9_-]+$/.test(part))
    ) {
      return null
    }

    const payload = parts[1]
      .replace(/-/g, '+')
      .replace(/_/g, '/')

    const padded = payload.padEnd(
      Math.ceil(payload.length / 4) * 4,
      '='
    )

    const bytes = Uint8Array.from(
      atob(padded),
      char => char.charCodeAt(0)
    )

    const claims: unknown = JSON.parse(
      new TextDecoder().decode(bytes)
    )

    if (
      typeof claims !== 'object' ||
      claims === null
    ) {
      return null
    }

    const value = claims as Record<string, unknown>

    if (
      value.demo === true &&
      !DEMO_AUTH_ENABLED
    ) {
      return null
    }

    if (
      typeof value.sub !== 'string' ||
      !value.sub.trim() ||
      typeof value.exp !== 'number' ||
      !Number.isFinite(value.exp) ||
      value.exp * 1000 <= Date.now() ||
      (
        value.nbf !== undefined &&
        (
          typeof value.nbf !== 'number' ||
          !Number.isFinite(value.nbf) ||
          value.nbf * 1000 > Date.now()
        )
      )
    ) {
      return null
    }

    return {
      sub: value.sub,
      exp: value.exp,
      name:
        typeof value.name === 'string'
          ? value.name
          : undefined,
    }
  } catch {
    return null
  }
}

// Đọc JWT từ LocalStorage
export function getStoredToken(): string | null {
  try {
    const token = localStorage.getItem(TOKEN_KEY)

    return readClaims(token) ? token : null
  } catch {
    return null
  }
}
