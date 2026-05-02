import { API_URL } from '../config'

export interface AuthUser {
  id: number
  email: string
  name: string
}

export interface AuthResult {
  token: string
  user: AuthUser
}

export interface JwtPayload {
  sub: string
  email?: string
  exp: number
  iat: number
}

function decodeBase64Url(s: string): string {
  const pad = s.length % 4 === 0 ? '' : '='.repeat(4 - (s.length % 4))
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + pad
  return atob(b64)
}

export function decodeJwt(token: string): JwtPayload | null {
  const parts = token.split('.')
  if (parts.length !== 3) return null
  try {
    return JSON.parse(decodeBase64Url(parts[1]!)) as JwtPayload
  } catch {
    return null
  }
}

export function isJwtValid(token: string | undefined): boolean {
  if (!token) return false
  const payload = decodeJwt(token)
  if (!payload) return false
  return payload.exp * 1000 > Date.now()
}

async function postJson<T>(path: string, body: unknown, token?: string): Promise<{ ok: true; data: T } | { ok: false; status: number; error: string }> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  const text = await res.text()
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = JSON.parse(text)
      detail = j.detail ?? j.error ?? j.message ?? detail
    } catch { /* keep statusText */ }
    return { ok: false, status: res.status, error: String(detail) }
  }
  return { ok: true, data: text ? (JSON.parse(text) as T) : ({} as T) }
}

export async function login(email: string, password: string) {
  return postJson<AuthResult>('/api/auth/login', { email, password })
}

export async function forgotPassword(email: string) {
  return postJson<{ ok: boolean }>('/api/auth/forgot', { email })
}

export async function changePassword(token: string, oldPassword: string, newPassword: string) {
  return postJson<{ ok: boolean }>(
    '/api/auth/change-password',
    { old_password: oldPassword, new_password: newPassword, new_password_confirm: newPassword },
    token,
  )
}

export async function logout(token: string) {
  return postJson<{ ok: boolean }>('/api/auth/logout', {}, token)
}
