import { Hono } from 'hono'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle } from '../components/card'
import { getInterests, setInterests, getSchedules, updateSchedule, addInterest, deleteInterest } from '../api'

export const settingsRouter = new Hono()

settingsRouter.post('/interests', async (c) => {
  const body = await c.req.parseBody()
  const keys = String(body._interest_keys ?? '').split(',').filter(Boolean)
  const interests: Record<string, boolean> = {}
  for (const key of keys) {
    interests[key] = body[key] === 'on'
  }
  await setInterests(interests)
  return c.redirect('/settings')
})

settingsRouter.post('/interests/add', async (c) => {
  const body = await c.req.parseBody()
  const key = String(body.key ?? '').trim().toLowerCase().replace(/\s+/g, '_')
  if (key) await addInterest(key)
  return c.redirect('/settings')
})

settingsRouter.post('/interests/:key/delete', async (c) => {
  const key = c.req.param('key')
  await deleteInterest(key)
  return c.redirect('/settings')
})

settingsRouter.post('/schedules/:event_name', async (c) => {
  const event_name = c.req.param('event_name')
  const body = await c.req.parseBody()
  const time = String(body.time ?? '06:00')
  const enabled = body.enabled === 'on'
  await updateSchedule(event_name, time, enabled)
  return c.redirect('/settings')
})

settingsRouter.get('/', async (c) => {
  let interests: Record<string, boolean>
  let schedules: Awaited<ReturnType<typeof getSchedules>>

  try {
    ;[interests, schedules] = await Promise.all([getInterests(), getSchedules()])
  } catch (e: any) {
    return c.html(baseLayout('Настройки', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'settings'))
  }

  const INTEREST_LABELS: Record<string, string> = {
    python: 'Python разработка',
    ai: 'Искусственный интеллект',
    running: 'Бег и спорт',
    economics: 'Экономика',
    politics: 'Политика',
  }

  const getLabel = (key: string) =>
    INTEREST_LABELS[key] ?? key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')

  const interestRow = (key: string, checked: boolean) => `
    <div style="display:flex; align-items:center; gap:8px; padding:10px 0; border-bottom:1px solid #1e1e1e;">
      <label style="display:flex; align-items:center; gap:12px; flex:1; cursor:pointer;">
        <div style="position:relative; width:36px; height:20px; flex-shrink:0;">
          <input type="checkbox" name="${key}" ${checked ? 'checked' : ''} form="interests-form"
            style="opacity:0; position:absolute; width:0; height:0;"
            onchange="this.closest('label').querySelector('.toggle-track').style.background = this.checked ? '#7c6aff' : '#2a2a2a';
                     this.closest('label').querySelector('.toggle-thumb').style.transform = this.checked ? 'translateX(18px)' : 'translateX(2px)';">
          <div class="toggle-track" style="position:absolute; inset:0; border-radius:10px; background:${checked ? '#7c6aff' : '#2a2a2a'}; transition:background 0.2s;"></div>
          <div class="toggle-thumb" style="position:absolute; top:2px; left:0; width:16px; height:16px; border-radius:50%; background:#e8e8e8; transition:transform 0.2s; transform:${checked ? 'translateX(18px)' : 'translateX(2px)'};"></div>
        </div>
        <span style="font-size:14px; color:#e8e8e8;">${getLabel(key)}</span>
      </label>
      <form method="POST" action="/settings/interests/${key}/delete" style="margin:0;">
        <button type="submit" title="Удалить" style="
          background:none; border:none; cursor:pointer; color:#555; font-size:16px;
          padding:4px 6px; border-radius:4px; line-height:1;
          transition:color 0.15s;
        " onmouseover="this.style.color='#e05252'" onmouseout="this.style.color='#555'">✕</button>
      </form>
    </div>
  `

  const SCHEDULE_LABELS: Record<string, string> = {
    morning_brief: 'Утренняя сводка',
    evening_summary: 'Вечерний итог',
    collect_content: 'Сбор контента',
    sync_workouts: 'Синхронизация тренировок',
  }

  const interestsForm = `
    <form id="interests-form" method="POST" action="/settings/interests" style="display:none;">
      <input type="hidden" name="_interest_keys" value="${Object.keys(interests).join(',')}">
    </form>
    ${Object.entries(interests).map(([key, checked]) => interestRow(key, checked)).join('')}
    <div style="display:flex; align-items:center; gap:8px; margin-top:14px; flex-wrap:wrap;">
      <button type="submit" form="interests-form" style="
        padding:8px 16px; border-radius:6px; font-size:13px;
        background:#7c6aff; color:#fff; border:none; cursor:pointer; font-weight:500;
      ">Сохранить</button>
    </div>
    <form method="POST" action="/settings/interests/add"
          style="display:flex; gap:8px; margin-top:14px; padding-top:14px; border-top:1px solid #1e1e1e;">
      <input type="text" name="key" placeholder="Новый интерес..." required
             autocomplete="off" style="
        flex:1; background:#111; border:1px solid #2a2a2a; border-radius:6px;
        color:#e8e8e8; font-size:13px; padding:7px 10px; outline:none; min-width:0;
      ">
      <button type="submit" style="
        padding:7px 14px; border-radius:6px; font-size:13px;
        background:#1e1e1e; color:#e8e8e8; border:1px solid #2a2a2a; cursor:pointer;
        white-space:nowrap;
      ">+ Добавить</button>
    </form>
  `

  const scheduleRow = (s: typeof schedules[0]) => `
    <form method="POST" action="/settings/schedules/${s.event_name}"
          style="display:flex; align-items:center; gap:12px; padding:12px 0; border-bottom:1px solid #1e1e1e; flex-wrap:wrap;">
      <div style="flex:1; min-width:160px;">
        <div style="font-size:14px; color:#e8e8e8;">${SCHEDULE_LABELS[s.event_name] ?? s.event_name}</div>
        <div style="font-size:11px; color:#555; margin-top:2px;">${s.cron_expr}</div>
      </div>
      <input type="time" name="time" value="${s.time}" style="
        background:#111; border:1px solid #2a2a2a; border-radius:6px;
        color:#e8e8e8; font-size:14px; padding:6px 10px; outline:none;
      " />
      <label style="display:flex; align-items:center; gap:6px; font-size:13px; color:#888; cursor:pointer;">
        <input type="checkbox" name="enabled" ${s.enabled ? 'checked' : ''} style="accent-color:#7c6aff;" />
        Вкл
      </label>
      <button type="submit" style="
        padding:6px 14px; border-radius:6px; font-size:13px;
        background:#1e1e1e; color:#e8e8e8; border:1px solid #2a2a2a; cursor:pointer;
      ">Сохранить</button>
    </form>
  `

  const content = `
    <div style="margin-bottom:28px;">
      <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Настройки</h1>
      <div style="font-size:13px; color:#555; margin-top:4px;">Интересы и расписание задач</div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;" class="settings-grid">
      ${card(`${sectionTitle('Интересы')}<div style="font-size:12px; color:#555; margin-top:-10px; margin-bottom:14px;">Темы для подборки контента</div>${interestsForm}`)}
      ${card(`${sectionTitle('Расписание')}<div style="font-size:12px; color:#555; margin-top:-10px; margin-bottom:14px;">Автоматические задачи</div>${schedules.map(scheduleRow).join('')}`)}
    </div>
  `

  return c.html(baseLayout('Настройки', content, 'settings'))
})
