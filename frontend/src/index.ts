import { Hono } from 'hono'
import { getCookie } from 'hono/cookie'
import { todayRouter } from './routes/today'
import { backlogRouter } from './routes/backlog'
import { workoutsRouter } from './routes/workouts'
import { focusRouter } from './routes/focus'
import { settingsRouter } from './routes/settings'
import { calendarRouter } from './routes/calendar'
import { notesRouter } from './routes/notes'
import { authRouter } from './routes/auth'
import { isJwtValid } from './auth/api-auth'
import { API_URL } from './config'
import { readFileSync } from 'fs'
import { join } from 'path'

const app = new Hono()

const cssCache = readFileSync(join(import.meta.dir, '../public/style.css'), 'utf8')
const manifestCache = readFileSync(join(import.meta.dir, '../public/manifest.json'), 'utf8')

app.get('/style.css', (c) => {
  return c.text(cssCache, 200, { 'Content-Type': 'text/css' })
})

app.get('/manifest.json', (c) => {
  return c.text(manifestCache, 200, { 'Content-Type': 'application/json' })
})

const SESSION_COOKIE = 'daios_session'

// Proxy /api/* requests to backend (for client-side JS).
// Forwards the session JWT as Bearer token so guarded endpoints accept the request.
app.all('/api/*', async (c) => {
  const reqUrl = new URL(c.req.url)
  const url = `${API_URL}${c.req.path}${reqUrl.search}`
  const headers: Record<string, string> = {
    'Content-Type': c.req.header('Content-Type') || 'application/json',
  }
  const token = getCookie(c, SESSION_COOKIE)
  if (token) headers['Authorization'] = `Bearer ${token}`

  const t0 = performance.now()
  const res = await fetch(url, {
    method: c.req.method,
    headers,
    body: ['GET', 'HEAD'].includes(c.req.method) ? undefined : await c.req.text(),
  })
  const ms = Math.round(performance.now() - t0)
  console.info(`[proxy] ${c.req.method} ${c.req.path} -> ${res.status} in ${ms}ms`)
  return new Response(res.body, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' },
  })
})

// Auth routes (public)
app.route('/auth', authRouter)

// Auth middleware — protect everything except /auth/*, static assets, /api/*
app.use('*', async (c, next) => {
  const path = c.req.path
  if (path.startsWith('/auth') || path === '/style.css' || path === '/manifest.json' || path.startsWith('/api/')) {
    return next()
  }
  const token = getCookie(c, SESSION_COOKIE)
  if (!isJwtValid(token)) {
    return c.redirect('/auth/login')
  }
  return next()
})

app.get('/', (c) => c.redirect('/today'))
app.route('/today', todayRouter)
app.route('/calendar', calendarRouter)
app.route('/backlog', backlogRouter)
app.route('/workouts', workoutsRouter)
app.route('/focus', focusRouter)
app.route('/notes', notesRouter)
app.route('/settings', settingsRouter)

const PORT = parseInt(process.env.PORT ?? '3000')

export default {
  port: PORT,
  hostname: '0.0.0.0',
  fetch: app.fetch,
}

console.log(`DAIOS frontend running at http://localhost:${PORT}`)
