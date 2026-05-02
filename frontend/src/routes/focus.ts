import { Hono } from 'hono'
import { getCookie } from 'hono/cookie'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle } from '../components/card'
import { getFocus, setWeekFocus, setMonthFocus } from '../api'

export const focusRouter = new Hono()

focusRouter.post('/week', async (c) => {
  const token = getCookie(c, 'daios_session')
  const body = await c.req.parseBody()
  const description = String(body.description ?? '').trim()
  if (description) await setWeekFocus(description, token)
  return c.redirect('/focus')
})

focusRouter.post('/month', async (c) => {
  const token = getCookie(c, 'daios_session')
  const body = await c.req.parseBody()
  const description = String(body.description ?? '').trim()
  if (description) await setMonthFocus(description, token)
  return c.redirect('/focus')
})

focusRouter.get('/', async (c) => {
  const token = getCookie(c, 'daios_session')
  let focus: Awaited<ReturnType<typeof getFocus>>
  try {
    focus = await getFocus(token)
  } catch (e: any) {
    return c.html(baseLayout('Фокус', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'focus'))
  }

  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

  const editForm = (type: 'week' | 'month', current: string) => `
    <form method="POST" action="/focus/${type}" style="display:flex; flex-direction:column; gap:12px;">
      <div style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px;">
        ${type === 'week' ? 'Фокус недели' : 'Фокус месяца'}
      </div>
      <textarea name="description" rows="3" style="
        background:#111; border:1px solid #2a2a2a; border-radius:6px;
        color:#e8e8e8; font-size:14px; padding:10px 12px;
        resize:vertical; outline:none; width:100%; box-sizing:border-box;
        font-family:inherit;
      " placeholder="Опишите фокус...">${esc(current)}</textarea>
      <div>
        <button type="submit" style="
          padding:8px 16px; border-radius:6px; font-size:13px;
          background:#7c6aff; color:#fff; border:none; cursor:pointer; font-weight:500;
        ">Сохранить</button>
      </div>
    </form>
  `

  const content = `
    <div style="margin-bottom:28px;">
      <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Фокус</h1>
      <div style="font-size:13px; color:#555; margin-top:4px;">Направление развития на неделю и месяц</div>
    </div>

    <div class="focus-forms-grid" style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px;">
      ${card(editForm('week', focus.week?.description ?? ''))}
      ${card(editForm('month', focus.month?.description ?? ''))}
    </div>
  `

  return c.html(baseLayout('Фокус', content, 'focus'))
})
