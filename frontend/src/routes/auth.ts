import { Hono } from 'hono'
import { getCookie, setCookie, deleteCookie } from 'hono/cookie'
import { authLayout } from '../layouts/auth'
import { login, forgotPassword, changePassword, logout as logoutApi, isJwtValid } from '../auth/api-auth'

export const authRouter = new Hono()

const SESSION_COOKIE = 'daios_session'
const SESSION_MAX_AGE = 60 * 60 * 24 // 1 day (matches JWT TTL)

// ── Helpers ───────────────────────────────────────────────────────────────

const input = (name: string, type: string, placeholder: string, required = true) =>
  `<input class="auth-input" name="${name}" type="${type}" placeholder="${placeholder}" ${required ? 'required' : ''} autocomplete="${type === 'password' ? 'current-password' : type === 'email' ? 'email' : 'off'}" />`

const btn = (text: string) =>
  `<button class="auth-btn" type="submit">${text}</button>`

const link = (href: string, text: string) =>
  `<a class="auth-link" href="${href}">${text}</a>`

const errorBox = (msg: string) =>
  msg ? `<div class="auth-error">${msg}</div>` : ''

function setSessionCookie(c: Parameters<typeof setCookie>[0], token: string) {
  setCookie(c, SESSION_COOKIE, token, {
    path: '/',
    httpOnly: true,
    sameSite: 'Lax',
    maxAge: SESSION_MAX_AGE,
  })
}

// ── Login ─────────────────────────────────────────────────────────────────

authRouter.get('/login', (c) => {
  const error = c.req.query('error') ?? ''
  return c.html(authLayout('Login', `
    ${errorBox(error)}
    <form method="POST" action="/auth/login">
      ${input('email', 'email', 'Email')}
      ${input('password', 'password', 'Password')}
      ${btn('Sign in')}
    </form>
    <div class="auth-links">
      ${link('/auth/forgot', 'Forgot password?')}
    </div>
  `))
})

authRouter.post('/login', async (c) => {
  const body = await c.req.parseBody()
  const email = String(body.email ?? '').trim()
  const password = String(body.password ?? '')

  const result = await login(email, password)
  if (!result.ok) {
    return c.redirect(`/auth/login?error=${encodeURIComponent(result.error)}`)
  }

  setSessionCookie(c, result.data.token)
  return c.redirect('/today')
})

// ── Forgot password ───────────────────────────────────────────────────────

authRouter.get('/forgot', (c) => {
  const sent = c.req.query('sent') === '1'
  const error = c.req.query('error') ?? ''
  return c.html(authLayout('Password recovery', `
    ${errorBox(error)}
    ${sent ? `<div class="auth-success">Recovery link has been sent to your email</div>` : ''}
    <form method="POST" action="/auth/forgot">
      ${input('email', 'email', 'Email')}
      ${btn('Send recovery link')}
    </form>
    <div class="auth-links">
      ${link('/auth/login', 'Back to sign in')}
    </div>
  `))
})

authRouter.post('/forgot', async (c) => {
  const body = await c.req.parseBody()
  const email = String(body.email ?? '').trim()

  const result = await forgotPassword(email)
  if (!result.ok) {
    return c.redirect(`/auth/forgot?error=${encodeURIComponent(result.error)}`)
  }
  return c.redirect('/auth/forgot?sent=1')
})

// ── Change password ──────────────────────────────────────────────────────

authRouter.get('/change-password', (c) => {
  const token = getCookie(c, SESSION_COOKIE)
  if (!isJwtValid(token)) {
    return c.redirect('/auth/login')
  }
  const error = c.req.query('error') ?? ''
  const success = c.req.query('success') === '1'
  return c.html(authLayout('Change password', `
    ${errorBox(error)}
    ${success ? `<div class="auth-success">Password changed successfully</div>` : ''}
    <form method="POST" action="/auth/change-password" onsubmit="
      const p1 = this.new_password.value;
      const p2 = this.new_password_confirm.value;
      if (p1 !== p2) {
        event.preventDefault();
        document.getElementById('auth-err').textContent = 'Passwords do not match';
        document.getElementById('auth-err').style.display = 'block';
      }
    ">
      <div id="auth-err" class="auth-error" style="display:none;"></div>
      ${input('old_password', 'password', 'Current password')}
      ${input('new_password', 'password', 'New password')}
      <input class="auth-input" name="new_password_confirm" type="password" placeholder="Confirm new password" required autocomplete="new-password" />
      ${btn('Change password')}
    </form>
    <div class="auth-links">
      ${link('/today', 'Back to dashboard')}
    </div>
  `))
})

authRouter.post('/change-password', async (c) => {
  const token = getCookie(c, SESSION_COOKIE)
  if (!isJwtValid(token)) {
    return c.redirect('/auth/login')
  }

  const body = await c.req.parseBody()
  const oldPassword = String(body.old_password ?? '')
  const newPassword = String(body.new_password ?? '')
  const confirm = String(body.new_password_confirm ?? '')

  if (!oldPassword || !newPassword) {
    return c.redirect('/auth/change-password?error=All fields are required')
  }
  if (newPassword !== confirm) {
    return c.redirect('/auth/change-password?error=Passwords do not match')
  }
  if (newPassword.length < 6) {
    return c.redirect('/auth/change-password?error=Password must be at least 6 characters')
  }

  const result = await changePassword(token!, oldPassword, newPassword)
  if (!result.ok) {
    return c.redirect(`/auth/change-password?error=${encodeURIComponent(result.error)}`)
  }
  return c.redirect('/auth/change-password?success=1')
})

// ── Logout ────────────────────────────────────────────────────────────────

authRouter.get('/logout', async (c) => {
  const token = getCookie(c, SESSION_COOKIE)
  if (token) {
    await logoutApi(token).catch(() => { /* ignore */ })
    deleteCookie(c, SESSION_COOKIE, { path: '/' })
  }
  return c.redirect('/auth/login')
})
