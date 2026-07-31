import { Hono } from 'hono'
import { getCookie } from 'hono/cookie'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle, emptyState } from '../components/card'
import { table } from '../components/table'
import { getBacklog, moveBacklogToToday, deleteBacklogItem } from '../api'

export const backlogRouter = new Hono()

backlogRouter.post('/:id/restore', async (c) => {
  const token = getCookie(c, 'daios_session')
  const id = parseInt(c.req.param('id'))
  await moveBacklogToToday(id, token)
  return c.redirect('/backlog')
})

backlogRouter.post('/:id/delete', async (c) => {
  const token = getCookie(c, 'daios_session')
  const id = parseInt(c.req.param('id'))
  await deleteBacklogItem(id, token)
  return c.redirect('/backlog')
})

backlogRouter.get('/', async (c) => {
  const token = getCookie(c, 'daios_session')
  let items: Awaited<ReturnType<typeof getBacklog>>
  try {
    items = await getBacklog(token)
  } catch (e: any) {
    return c.html(baseLayout('Backlog', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'backlog'))
  }

  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

  const rows = items.map(t => [
    `<div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${esc(t.title)}">${esc(t.title)}</div>`,
    `<span style="color:#666; font-size:13px;">${esc(t.reason ?? '—')}</span>`,
    `<div style="display:flex; gap:4px; white-space:nowrap;">
      <form method="POST" action="/backlog/${t.id}/restore" style="display:inline;"><button type="submit" title="Move back to today" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;font-size:12px;background:#2a2a2a;color:#7c6aff;border:1px solid #333;cursor:pointer;">↩</button></form>
      <form method="POST" action="/backlog/${t.id}/delete" style="display:inline;"><button type="submit" title="Delete" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;font-size:12px;background:#2a2a2a;color:#e05252;border:1px solid #333;cursor:pointer;">✕</button></form>
    </div>`,
  ])

  const content = `
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:28px;">
      <div>
        <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Backlog</h1>
        <div style="font-size:13px; color:#555; margin-top:4px;">${items.length} tasks deferred</div>
      </div>
    </div>

    ${card(`
      ${sectionTitle('Deferred tasks')}
      ${items.length === 0
        ? emptyState('Backlog is empty — great job!')
        : table(['Task', 'Reason', ''], rows,
            ['', 'width:220px;', 'width:80px;'],
            ['', 'col-reason', '']
          )
      }
    `)}
  `

  return c.html(baseLayout('Backlog', content, 'backlog'))
})
