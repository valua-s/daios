import { Hono } from 'hono'
import { getCookie } from 'hono/cookie'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle } from '../components/card'
import { table, badge } from '../components/table'
import { getWeekWorkouts, getWeekSummary, type WorkoutDTO, type WeekSummaryDTO } from '../api'

export const workoutsRouter = new Hono()

const TYPE_LABELS: Record<WorkoutDTO['type'], string> = {
  running:  'Бег',
  strength: 'Силовая',
  combined: 'Комбо',
  rest:     'Отдых',
}

const TYPE_COLORS: Record<WorkoutDTO['type'], string> = {
  running:  '#7c6aff',
  strength: '#d97706',
  combined: '#3a9e6a',
  rest:     '#333',
}

workoutsRouter.get('/', async (c) => {
  const token = getCookie(c, 'daios_session')
  let workouts: WorkoutDTO[]
  let summary: WeekSummaryDTO
  try {
    [workouts, summary] = await Promise.all([
      getWeekWorkouts(token),
      getWeekSummary(token),
    ])
  } catch (e: any) {
    return c.html(baseLayout('Тренировки', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'workouts'))
  }

  const todayWorkout = workouts.find(w => w.is_today)
  const weekDone = workouts.filter(w => w.is_completed).length
  const totalPlanned = workouts.filter(w => w.type !== 'rest').length
  const upcoming = workouts.filter(w => new Date(w.date) > new Date() && w.type !== 'rest').length

  const rows = workouts.map(w => [
    `<span style="color:${w.is_today ? '#7c6aff' : '#888'}; font-weight:${w.is_today ? '600' : '400'};">${w.day}</span>`,
    badge(TYPE_LABELS[w.type], TYPE_COLORS[w.type]),
    `<span style="color:${w.type === 'rest' ? '#444' : '#888'}; font-size:13px;">${w.description}</span>`,
    w.duration_minutes ? `<span style="color:#666; font-size:13px;">${w.duration_minutes} мин</span>` : '—',
    renderActual(w),
    renderStatus(w),
  ])

  const todayCard = todayWorkout && todayWorkout.type !== 'rest' ? card(`
    <div style="display:flex; align-items:center; gap:16px;">
      <div style="font-size:36px;">${todayWorkout.type === 'running' ? '🏃' : todayWorkout.type === 'strength' ? '💪' : '🏋️'}</div>
      <div>
        <div style="font-size:11px; color:#7c6aff; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Тренировка сегодня</div>
        <div style="font-size:16px; font-weight:600; color:#e8e8e8;">${todayWorkout.description}</div>
        ${todayWorkout.duration_minutes ? `<div style="font-size:13px; color:#666; margin-top:4px;">${todayWorkout.duration_minutes} минут</div>` : ''}
      </div>
    </div>
  `, 'border-color:#7c6aff33;') : ''

  const summaryCard = renderSummary(summary)

  const content = `
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:28px;">
      <div>
        <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Тренировки</h1>
        <div style="font-size:13px; color:#555; margin-top:4px;">План — Google Sheets, факт — Strava</div>
      </div>
    </div>

    ${todayCard}
    ${todayCard ? '<div style="height:16px;"></div>' : ''}

    ${summaryCard}
    <div style="height:16px;"></div>

    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px;">
      ${statMini('Выполнено', `${weekDone} / ${totalPlanned}`, '#7c6aff')}
      ${statMini('Бег план', `${summary.planned_km} км`, '#3a9e6a')}
      ${statMini('Осталось', `${upcoming} трен.`, '#d97706')}
    </div>

    ${card(`
      ${sectionTitle('Неделя')}
      ${table(['День', 'Тип', 'Описание', 'План', 'Факт', 'Статус'], rows,
        ['width:50px;', 'width:100px;', '', 'width:90px;', 'width:140px;', 'width:110px;'],
        ['', 'col-type', '', 'col-duration', 'col-actual', 'col-status']
      )}
    `)}

    ${editScript()}
  `

  return c.html(baseLayout('Тренировки', content, 'workouts'))
})

const renderActual = (w: WorkoutDTO): string => {
  if (!w.is_completed || w.completed_workout_id === null) {
    return '<span style="color:#444;">—</span>'
  }
  const km = w.actual_distance_km !== null ? w.actual_distance_km.toFixed(2) : '—'
  const id = w.completed_workout_id
  return `
    <span class="cw-view" data-id="${id}">
      <span class="cw-km" style="color:#3a9e6a; font-weight:600;">${km} км</span>
      <button class="cw-edit-btn" data-id="${id}" data-km="${km}"
        style="background:none; border:none; color:#888; cursor:pointer; font-size:13px; margin-left:6px;">✏️</button>
    </span>
    <span class="cw-edit" data-id="${id}" style="display:none;">
      <input type="number" step="0.01" class="cw-input" data-id="${id}" value="${km}"
        style="width:70px; padding:2px 4px; background:#1a1a1a; color:#e8e8e8; border:1px solid #444; border-radius:3px; font-size:13px;" />
      <button class="cw-save-btn" data-id="${id}"
        style="background:#3a9e6a; border:none; color:white; padding:2px 6px; border-radius:3px; cursor:pointer; font-size:12px; margin-left:3px;">✓</button>
      <button class="cw-reset-btn" data-id="${id}"
        style="background:none; border:1px solid #555; color:#888; padding:2px 6px; border-radius:3px; cursor:pointer; font-size:12px; margin-left:3px;" title="Сбросить к GPS-значению">↺</button>
      <button class="cw-cancel-btn" data-id="${id}"
        style="background:none; border:none; color:#888; cursor:pointer; font-size:13px; margin-left:3px;">✕</button>
    </span>
  `
}

const renderStatus = (w: WorkoutDTO): string => {
  if (w.is_completed) return badge('✅ Выполнено', '#3a9e6a')
  if (w.is_today) return badge('Сегодня', '#7c6aff')
  if (new Date(w.date) < new Date()) return badge('Пропущено', '#d97706')
  return badge('Впереди', '#555')
}

const renderSummary = (s: WeekSummaryDTO): string => {
  const percent = Math.min(100, s.percent)
  const color = s.percent >= 100 ? '#3a9e6a' : s.percent >= 60 ? '#7c6aff' : '#d97706'
  return card(`
    <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:10px;">
      <div>
        <div style="font-size:11px; color:#7c6aff; text-transform:uppercase; letter-spacing:0.5px;">Недельный объём бега</div>
        <div style="font-size:20px; font-weight:700; color:#e8e8e8; margin-top:4px;">
          ${s.actual_km} / ${s.planned_km} км
        </div>
      </div>
      <div style="font-size:22px; font-weight:700; color:${color};">${s.percent}%</div>
    </div>
    <div style="height:8px; background:#222; border-radius:4px; overflow:hidden;">
      <div style="height:100%; width:${percent}%; background:${color}; transition:width 0.3s;"></div>
    </div>
  `)
}

const statMini = (label: string, value: string, color: string) =>
  card(`
    <div style="font-size:20px; font-weight:700; color:${color};">${value}</div>
    <div style="font-size:12px; color:#555; margin-top:2px;">${label}</div>
  `)

const editScript = () => `
<script>
(function() {
  function toggleEdit(id, editing) {
    document.querySelectorAll('.cw-view[data-id="' + id + '"]').forEach(el => el.style.display = editing ? 'none' : '')
    document.querySelectorAll('.cw-edit[data-id="' + id + '"]').forEach(el => el.style.display = editing ? '' : 'none')
  }

  async function patch(id, distance_km) {
    const res = await fetch('/api/workouts/completed/' + id, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ distance_km }),
    })
    if (!res.ok) { alert('Ошибка: ' + res.status); return false }
    return true
  }

  document.addEventListener('click', async (e) => {
    const t = e.target
    if (!(t instanceof HTMLElement)) return
    const id = t.dataset.id
    if (!id) return
    if (t.classList.contains('cw-edit-btn')) { toggleEdit(id, true); return }
    if (t.classList.contains('cw-cancel-btn')) { toggleEdit(id, false); return }
    if (t.classList.contains('cw-save-btn')) {
      const inp = document.querySelector('.cw-input[data-id="' + id + '"]')
      const val = parseFloat(inp.value)
      if (isNaN(val) || val < 0) { alert('Введите число ≥ 0'); return }
      if (await patch(id, val)) location.reload()
      return
    }
    if (t.classList.contains('cw-reset-btn')) {
      if (await patch(id, null)) location.reload()
      return
    }
  })
})()
</script>
`
