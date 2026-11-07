import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getStoredToken, readClaims, TOKEN_KEY } from './token'

interface AuthContextValue {
  token: string | null
  signIn: (token: string) => void
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(getStoredToken)

  function signOut() {
    try { localStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(TOKEN_KEY) } catch { /* Still clear the in-memory session. */ }
    setToken(null)
  }

  function signIn(nextToken: string) {
    if (!readClaims(nextToken)) throw new Error('Token đăng nhập không hợp lệ hoặc đã hết hạn.')
    localStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.setItem(TOKEN_KEY, nextToken)
    setToken(nextToken)
  }

  useEffect(() => {
    const sync = () => setToken(getStoredToken())
    const onStorage = (event: StorageEvent) => {
      if (event.key === TOKEN_KEY || event.key === null) sync()
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', sync)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', sync)
    }
  }, [])

  useEffect(() => {
    if (!token) return
    const claims = readClaims(token)
    if (!claims) { signOut(); return }
    let timer: number
    function checkExpiry() {
      const current = readClaims(token)
      if (!current) { signOut(); return }
      timer = window.setTimeout(checkExpiry, Math.min(current.exp * 1000 - Date.now(), 2_147_483_647))
    }
    checkExpiry()
    return () => window.clearTimeout(timer)
  }, [token])

  return <AuthContext.Provider value={{ token, signIn, signOut }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth requires AuthProvider')
  return context
}
