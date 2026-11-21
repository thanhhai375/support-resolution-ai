
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react'

import type { ReactNode } from 'react'

import {
  getStoredToken,
  readClaims,
  TOKEN_KEY,
} from './token'

import type { UserRole } from './token'
import {
  getCurrentUser,
  revokeAccessToken,
} from '../services/authService'
import { DEMO_AUTH_ENABLED } from './demo'

interface AuthContextValue {
  token: string | null
  role: UserRole | null
  signIn: (token: string) => Promise<void>
  signOut: () => Promise<void>
}

interface AuthSession {
  token: string
  role: UserRole
}

const AuthContext =
  createContext<AuthContextValue | null>(null)

// Xác định vai trò từ phiên đăng nhập
async function resolveRole(token: string): Promise<UserRole> {
  const claims = readClaims(token)

  if (!claims) {
    throw new Error(
      'Token không hợp lệ hoặc đã hết hạn.'
    )
  }

  // Chỉ dùng role trong token với chế độ demo
  if (DEMO_AUTH_ENABLED && claims.demo) {
    if (!claims.role) {
      throw new Error('Vai trò demo không hợp lệ.')
    }

    return claims.role
  }

  // Backend CRM-40: xác thực và lấy role thực tế
  const user = await getCurrentUser(token)

  if (!readClaims(token)) {
    throw new Error('Phiên đăng nhập đã hết hạn.')
  }

  return user.role
}

export function AuthProvider({
  children,
}: {
  children: ReactNode
}) {
  const [session, setSession] =
    useState<AuthSession | null>(null)

  const [restoring, setRestoring] = useState(true)

  const activeToken = useRef<string | null>(null)
  const requestVersion = useRef(0)

  const token = session?.token ?? null
  const role = session?.role ?? null


function clearSession() {
  requestVersion.current += 1

  try {
    localStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Vẫn xóa phiên trong React State
  }

  activeToken.current = null
  setSession(null)
  setRestoring(false)
}

async function signOut() {
  const currentToken = activeToken.current
  const claims = readClaims(currentToken)

  // Xóa phiên đăng nhập trên Frontend
  clearSession()

  // Không gọi Backend nếu không có token hoặc là demo
  if (!currentToken || claims?.demo) {
    return
  }

  try {
    await revokeAccessToken(currentToken)
  } catch {
    window.alert(
      'Đã đăng xuất khỏi thiết bị, nhưng chưa thể xác nhận thu hồi token trên máy chủ.'
    )
  }
}

  async function signIn(nextToken: string) {
    const version = ++requestVersion.current

    const nextRole = await resolveRole(nextToken)

    if (version !== requestVersion.current) {
      throw new Error(
        'Phiên đăng nhập đã thay đổi. Vui lòng thử lại.'
      )
    }

    try {
      localStorage.setItem(TOKEN_KEY, nextToken)
      sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      throw new Error(
        'Không thể lưu phiên đăng nhập.'
      )
    }

    activeToken.current = nextToken

    setSession({
      token: nextToken,
      role: nextRole,
    })

    setRestoring(false)
  }

  // Khôi phục phiên và đồng bộ giữa các tab
  useEffect(() => {
    async function sync(force = false) {
      const storedToken = getStoredToken()

      if (
        !force &&
        storedToken === activeToken.current
      ) {
        return
      }

      const version = ++requestVersion.current

      if (!storedToken) {
        clearSession()
        return
      }

      setRestoring(true)
      setSession(null)
      activeToken.current = null

      try {
        const restoredRole =
          await resolveRole(storedToken)

        if (version !== requestVersion.current) {
          return
        }

        if (getStoredToken() !== storedToken) {
          void sync(true)
          return
        }

        activeToken.current = storedToken

        setSession({
          token: storedToken,
          role: restoredRole,
        })

        setRestoring(false)
      } catch {
        if (version === requestVersion.current) {
          clearSession()
        }
      }
    }

    const onStorage = (event: StorageEvent) => {
      if (
        event.key === TOKEN_KEY ||
        event.key === null
      ) {
        void sync(true)
      }
    }

    const onFocus = () => {
      void sync()
    }

    void sync(true)

    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', onFocus)

    return () => {
      requestVersion.current += 1

      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', onFocus)
    }
  }, [])

  // Kiểm tra thời hạn JWT
  useEffect(() => {
    if (!token) return

    let timer: number

    function checkExpiry() {
      if (activeToken.current !== token) return

      const claims = readClaims(token)

      if (!claims) {
        clearSession()
        return
      }

      const remaining =
        claims.exp * 1000 - Date.now()

      timer = window.setTimeout(
        checkExpiry,
        Math.min(
          Math.max(remaining, 0),
          2_147_483_647
        )
      )
    }

    checkExpiry()

    return () => {
      window.clearTimeout(timer)
    }
  }, [token])

  return (
    <AuthContext.Provider
      value={{ token, role, signIn, signOut }}
    >
      {restoring ? (
        <div
          role="status"
          style={{
            minHeight: '100vh',
            display: 'grid',
            placeItems: 'center',
            color: '#4568e8',
            fontWeight: 600,
          }}
        >
          Đang xác thực phiên đăng nhập...
        </div>
      ) : (
        children
      )}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error(
      'useAuth requires AuthProvider'
    )
  }

  return context
}
