import { Hono } from 'hono'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle } from '../components/card'
import { table, badge, iconBtn } from '../components/table'
import { getTodayTasks, toggleTask, moveTaskToBacklog, deleteTask, getFocus, apiFetch } from '../api'

export const todayRouter = new Hono()

todayRouter.get('/:id/done', async (c) => {
  const id = parseInt(c.req.param('id'))
  await toggleTask(id)
  return c.redirect('/today')
})

todayRouter.get('/:id/backlog', async (c) => {
  const id = parseInt(c.req.param('id'))
  await moveTaskToBacklog(id)
  return c.redirect('/today')
})

todayRouter.get('/:id/delete', async (c) => {
  const id = parseInt(c.req.param('id'))
  await deleteTask(id)
  return c.redirect('/today')
})

todayRouter.post('/new', async (c) => {
  const body = await c.req.parseBody()
  const title = String(body.title ?? '').trim()
  if (!title) return c.redirect('/today')

  const scheduledTime = body.scheduled_time
    ? String(body.scheduled_time).length === 5
      ? `${body.scheduled_time}:00`
      : String(body.scheduled_time)
    : null

  await apiFetch('/api/tasks/', {
    method: 'POST',
    body: JSON.stringify({
      title,
      priority: body.priority ?? 'medium',
      date: body.date || null,
      scheduled_time: scheduledTime,
      notes: body.notes || null,
      source: 'web',
    }),
  })
  return c.redirect('/today')
})

todayRouter.get('/', async (c) => {
  const today = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
  const todayIso = new Date().toISOString().slice(0, 10)

  let tasks: Awaited<ReturnType<typeof getTodayTasks>>
  let focus: Awaited<ReturnType<typeof getFocus>>
  try {
    ;[tasks, focus] = await Promise.all([getTodayTasks(), getFocus()])
  } catch (e: any) {
    return c.html(baseLayout('Сегодня', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'today'))
  }

  const done = tasks.filter(t => t.status === 'done').length
  const total = tasks.length
  const pct = total > 0 ? Math.round(done / total * 100) : 0

  const statsBlock = `
    <div class="stats-desktop">
      ${card(`
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; text-align:center; height:100%; align-items:center;">
          <div style="min-width:0;">
            <div style="font-size:28px; font-weight:700; color:#7c6aff;">${done}</div>
            <div style="font-size:12px; color:#555; margin-top:4px;">Выполнено</div>
          </div>
          <div style="min-width:0;">
            <div style="font-size:28px; font-weight:700; color:#d97706;">${total - done}</div>
            <div style="font-size:12px; color:#555; margin-top:4px;">Осталось</div>
          </div>
          <div style="min-width:0;">
            <div style="font-size:28px; font-weight:700; color:#3a9e6a;">${pct}%</div>
            <div style="font-size:12px; color:#555; margin-top:4px;">Прогресс</div>
          </div>
        </div>
      `)}
    </div>
    <div class="stats-mobile">
      ${card(`
        <div style="font-size:11px; color:#555; margin-bottom:10px; text-transform:uppercase; letter-spacing:0.5px;">Прогресс дня</div>
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="flex:1; background:#2a2a2a; border-radius:6px; height:8px; overflow:hidden;">
            <div style="width:${pct}%; height:100%; background:#7c6aff; transition:width 0.4s;"></div>
          </div>
          <div style="font-size:14px; font-weight:600; color:#7c6aff; white-space:nowrap;">${done}/${total}</div>
        </div>
      `)}
    </div>
  `

  const sorted = [...tasks].sort((a, b) => {
    if (a.status === 'done' && b.status !== 'done') return 1
    if (a.status !== 'done' && b.status === 'done') return -1
    return 0
  })

  const rows = sorted.map(t => [
    t.status === 'done'
      ? `<div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#444; text-decoration:line-through;" title="${t.title}">${t.title}</div>`
      : `<div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${t.title}">${t.title}</div>`,
    t.scheduled_time
      ? `<span style="color:#666; font-size:13px;">${t.scheduled_time.slice(0, 5)}</span>`
      : `<span style="color:#333;">—</span>`,
    t.status === 'done'
      ? badge('Готово', '#3a9e6a')
      : badge('В процессе', '#d97706'),
    t.status === 'done'
      ? ''
      : `<div style="display:flex; gap:6px; align-items:center; white-space:nowrap;">
          ${iconBtn('✓', 'Выполнено', `/today/${t.id}/done`, '#3a9e6a')}
          <a href="/today/${t.id}/backlog" title="В бэклог" style="
            display:inline-flex; align-items:center; gap:4px;
            padding:3px 9px; border-radius:5px; font-size:12px;
            background:#2a2a2a; color:#666; text-decoration:none;
            border:1px solid #333; transition:all 0.15s;
          " onmouseover="this.style.color='#aaa';this.style.borderColor='#555'" onmouseout="this.style.color='#666';this.style.borderColor='#333'">
            бэклог ↗
          </a>
          ${iconBtn('✕', 'Удалить', `/today/${t.id}/delete`, '#e05252')}
        </div>`,
  ])

  const modal = `
    <div id="task-modal" onclick="if(event.target===this)closeModal()" style="
      display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6);
      z-index:200; align-items:center; justify-content:center; padding:16px;
    ">
      <div style="
        background:#181818; border:1px solid #2a2a2a; border-radius:12px;
        padding:28px; width:100%; max-width:460px;
      ">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:24px;">
          <h2 style="margin:0; font-size:16px; font-weight:600; color:#e8e8e8;">Новая задача</h2>
          <button onclick="closeModal()" style="
            background:none; border:none; cursor:pointer;
            color:#555; font-size:20px; line-height:1; padding:2px 6px;
          ">✕</button>
        </div>

        <form method="POST" action="/today/new" style="display:flex; flex-direction:column; gap:16px;">

          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Название *</label>
            <input name="title" required autofocus placeholder="Что нужно сделать?" style="
              width:100%; box-sizing:border-box;
              background:#111; border:1px solid #2a2a2a; border-radius:6px;
              color:#e8e8e8; font-size:14px; padding:10px 12px;
              outline:none; font-family:inherit;
            " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div>
              <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Дата</label>
              <input name="date" type="date" value="${todayIso}" style="
                width:100%; box-sizing:border-box;
                background:#111; border:1px solid #2a2a2a; border-radius:6px;
                color:#e8e8e8; font-size:14px; padding:10px 12px;
                outline:none; font-family:inherit; color-scheme:dark;
              " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
            </div>
            <div>
              <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Время</label>
              <input name="scheduled_time" type="time" style="
                width:100%; box-sizing:border-box;
                background:#111; border:1px solid #2a2a2a; border-radius:6px;
                color:#e8e8e8; font-size:14px; padding:10px 12px;
                outline:none; font-family:inherit; color-scheme:dark;
              " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
            </div>
          </div>

          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Заметки</label>
            <textarea name="notes" rows="2" placeholder="Дополнительный контекст..." style="
              width:100%; box-sizing:border-box;
              background:#111; border:1px solid #2a2a2a; border-radius:6px;
              color:#e8e8e8; font-size:14px; padding:10px 12px;
              outline:none; font-family:inherit; resize:vertical;
            " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"></textarea>
          </div>

          <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:4px;">
            <button type="button" onclick="closeModal()" style="
              padding:9px 18px; border-radius:6px; font-size:13px; font-weight:500;
              background:transparent; color:#666; border:1px solid #2a2a2a; cursor:pointer;
            ">Отмена</button>
            <button type="submit" style="
              padding:9px 18px; border-radius:6px; font-size:13px; font-weight:500;
              background:#7c6aff; color:#fff; border:none; cursor:pointer;
            ">Добавить</button>
          </div>
        </form>
      </div>
    </div>

    <script>
      function openModal() {
        const m = document.getElementById('task-modal')
        m.style.display = 'flex'
        setTimeout(() => m.querySelector('input[name=title]').focus(), 50)
      }
      function closeModal() {
        document.getElementById('task-modal').style.display = 'none'
      }
      document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal() })
    </script>
  `

  const tasksBlock = card(`
    ${sectionTitle('Задачи на сегодня', `
      <button onclick="openModal()" style="
        padding:7px 14px; border-radius:6px; font-size:13px;
        background:#7c6aff; color:#fff; border:none; cursor:pointer; font-weight:500;
      ">+ Добавить</button>
    `)}
    ${total === 0
      ? `<div style="padding:32px; text-align:center; color:#555;">Задач нет — добавьте первую</div>`
      : table(['Задача', 'Время', 'Статус', ''], rows, [
          '',
          'width:70px;',
          'width:110px;',
          'width:165px;',
        ], ['', 'col-duration', 'col-status', ''])
    }
  `)

  const content = `
    ${modal}
    <div class="today-grid">
      <div class="today-date-card" style="background:#181818; border:1px solid #2a2a2a; border-radius:10px; padding:20px; display:flex; flex-direction:column; justify-content:center;">
        <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Сегодня</h1>
        <div style="font-size:13px; color:#555; margin-top:6px; text-transform:capitalize;">${today}</div>
      </div>
      <div style="background:#181818; border:1px solid #2a2a2a; border-radius:10px; padding:20px; display:flex; flex-direction:column; gap:10px;">
        <div>
          <div style="font-size:11px; color:#555; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px;">Неделя</div>
          <div style="font-size:15px; color:#e8e8e8; line-height:1.4;">${focus.week?.description ?? '—'}</div>
        </div>
        <div class="focus-month" style="border-top:1px solid #2a2a2a; padding-top:10px;">
          <div style="font-size:11px; color:#555; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px;">Месяц</div>
          <div style="font-size:14px; color:#888; line-height:1.4;">${focus.month?.description ?? '—'}</div>
        </div>
      </div>
      ${statsBlock}
    </div>

    ${tasksBlock}
  `

  return c.html(baseLayout('Сегодня', content, 'today'))
})
