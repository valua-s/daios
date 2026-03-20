import { Hono } from 'hono'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle, emptyState } from '../components/card'
import { table, iconBtn } from '../components/table'
import { getBacklog, moveBacklogToToday, deleteBacklogItem } from '../api'

export const backlogRouter = new Hono()

backlogRouter.get('/:id/restore', async (c) => {
  const id = parseInt(c.req.param('id'))
  await moveBacklogToToday(id)
  return c.redirect('/backlog')
})

backlogRouter.get('/:id/delete', async (c) => {
  const id = parseInt(c.req.param('id'))
  await deleteBacklogItem(id)
  return c.redirect('/backlog')
})

backlogRouter.get('/', async (c) => {
  let items: Awaited<ReturnType<typeof getBacklog>>
  try {
    items = await getBacklog()
  } catch (e: any) {
    return c.html(baseLayout('Бэклог', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'backlog'))
  }

  const rows = items.map(t => [
    `<div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${t.title}">${t.title}</div>`,
    `<span style="color:#666; font-size:13px;">${t.reason ?? '—'}</span>`,
    `<div style="display:flex; gap:4px; white-space:nowrap;">
      ${iconBtn('↩', 'Вернуть на сегодня', `/backlog/${t.id}/restore`, '#7c6aff')}
      ${iconBtn('✕', 'Удалить', `/backlog/${t.id}/delete`, '#e05252')}
    </div>`,
  ])

  const content = `
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:28px;">
      <div>
        <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Бэклог</h1>
        <div style="font-size:13px; color:#555; margin-top:4px;">${items.length} задач отложено</div>
      </div>
    </div>

    ${card(`
      ${sectionTitle('Отложенные задачи')}
      ${items.length === 0
        ? emptyState('Бэклог пуст — отличная работа!')
        : table(['Задача', 'Причина', ''], rows,
            ['', 'width:220px;', 'width:80px;'],
            ['', 'col-reason', '']
          )
      }
    `)}
  `

  return c.html(baseLayout('Бэклог', content, 'backlog'))
})
