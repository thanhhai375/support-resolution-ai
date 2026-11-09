export const DEMO_AUTH_ENABLED = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEMO_AUTH === 'true'
export const DEMO_EMAIL = 'demo@supportai.vn'
export const DEMO_PASSWORD = 'Demo@123'

export function createDemoToken(email: string, password: string): string {
  if (!DEMO_AUTH_ENABLED) throw new Error('Chế độ demo chưa được bật.')
  if (email.trim().toLowerCase() !== DEMO_EMAIL || password !== DEMO_PASSWORD) {
    throw new Error('Email hoặc mật khẩu demo không đúng.')
  }
  const encode = (value: object) => btoa(JSON.stringify(value)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${encode({ alg: 'none', typ: 'JWT' })}.${encode({ sub: DEMO_EMAIL, name: 'Demo Admin', exp: Math.floor(Date.now() / 1000) + 3600, demo: true })}.local-demo`
}
