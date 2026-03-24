import { Hono } from 'hono'
import { todayRouter } from './routes/today'
import { backlogRouter } from './routes/backlog'
import { workoutsRouter } from './routes/workouts'
import { focusRouter } from './routes/focus'
import { settingsRouter } from './routes/settings'
import { calendarRouter } from './routes/calendar'
import { readFileSync } from 'fs'
import { join } from 'path'

const app = new Hono()

app.get('/style.css', (c) => {
  const css = readFileSync(join(import.meta.dir, '../public/style.css'), 'utf8')
  return c.text(css, 200, { 'Content-Type': 'text/css' })
})

app.get('/manifest.json', (c) => {
  const json = readFileSync(join(import.meta.dir, '../public/manifest.json'), 'utf8')
  return c.text(json, 200, { 'Content-Type': 'application/json' })
})

const API_URL = process.env.API_URL ?? 'http://daios_api:8000'

// Proxy /api/* requests to backend (for client-side JS)
app.all('/api/*', async (c) => {
  const url = `${API_URL}${c.req.path}`
  const res = await fetch(url, {
    method: c.req.method,
    headers: { 'Content-Type': 'application/json' },
    body: ['GET', 'HEAD'].includes(c.req.method) ? undefined : await c.req.text(),
  })
  return new Response(res.body, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' },
  })
})

app.get('/', (c) => c.redirect('/today'))
app.route('/today', todayRouter)
app.route('/calendar', calendarRouter)
app.route('/backlog', backlogRouter)
app.route('/workouts', workoutsRouter)
app.route('/focus', focusRouter)
app.route('/settings', settingsRouter)

const PORT = parseInt(process.env.PORT ?? '3000')

export default {
  port: PORT,
  hostname: '0.0.0.0',
  fetch: app.fetch,
}

console.log(`DAIOS frontend running at http://localhost:${PORT}`)
