import { Hono } from 'hono'
import { getCookie } from 'hono/cookie'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle } from '../components/card'
import { table, badge } from '../components/table'
import { getWeekWorkouts, getWeekSummary, type ActualWorkoutDTO, type WorkoutDTO, type WeekSummaryDTO } from '../api'

export const workoutsRouter = new Hono()

const TYPE_LABELS: Record<WorkoutDTO['type'], string> = {
  running:  'Running',
  cycling:  'Cycling',
  swimming: 'Swimming',
  strength: 'Strength',
  combined: 'Combo',
  rest:     'Rest',
}

const TYPE_COLORS: Record<WorkoutDTO['type'], string> = {
  running:  '#7c6aff',
  cycling:  '#2f9e9e',
  swimming: '#3a7bd5',
  strength: '#d97706',
  combined: '#3a9e6a',
  rest:     '#333',
}

const TYPE_ICONS: Record<WorkoutDTO['type'], string> = {
  running:  '🏃',
  cycling:  '🚴',
  swimming: '🏊',
  strength: '💪',
  combined: '🏋️',
  rest:     '🛌',
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
    return c.html(baseLayout('Workouts', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'workouts'))
  }

  const todayWorkout = workouts.find(w => w.is_today)
  const weekDone = workouts.filter(w => w.actuals.length > 0).length
  const totalPlanned = workouts.filter(w => w.type !== 'rest').length
  const upcoming = workouts.filter(w => new Date(w.date) > new Date() && w.type !== 'rest').length

  const rows = workouts.map(w => [
    `<span style="color:${w.is_today ? '#7c6aff' : '#888'}; font-weight:${w.is_today ? '600' : '400'};">${w.day}</span>`,
    badge(TYPE_LABELS[w.type], TYPE_COLORS[w.type]),
    w.duration_minutes ? `<span style="color:#666; font-size:13px;">${w.duration_minutes} min</span>` : '—',
    renderActual(w),
    `<span style="color:${w.type === 'rest' ? '#444' : '#888'}; font-size:13px;">${w.description}</span>`,
    renderStatus(w),
  ])

  const todayCard = todayWorkout && todayWorkout.type !== 'rest' ? card(`
    <div style="display:flex; align-items:center; gap:16px;">
      <div style="font-size:36px;">${TYPE_ICONS[todayWorkout.type]}</div>
      <div>
        <div style="font-size:11px; color:#7c6aff; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Today's workout</div>
        <div style="font-size:16px; font-weight:600; color:#e8e8e8;">${todayWorkout.description}</div>
        ${todayWorkout.duration_minutes ? `<div style="font-size:13px; color:#666; margin-top:4px;">${todayWorkout.duration_minutes} minutes</div>` : ''}
      </div>
    </div>
  `, 'border-color:#7c6aff33;') : ''

  const summaryCard = renderSummary(summary)

  const content = `
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:28px;">
      <div>
        <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Workouts</h1>
        <div style="font-size:13px; color:#555; margin-top:4px;">Plan from Google Sheets, actuals entered manually</div>
      </div>
    </div>

    ${todayCard}
    ${todayCard ? '<div style="height:16px;"></div>' : ''}

    ${summaryCard}
    <div style="height:16px;"></div>

    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px;">
      ${statMini('Completed', `${weekDone} / ${totalPlanned}`, '#7c6aff')}
      ${statMini('Running plan', `${summary.planned_km} km`, '#3a9e6a')}
      ${statMini('Left', `${upcoming} sessions`, '#d97706')}
    </div>

    ${card(`
      ${sectionTitle('Week')}
      ${table(['Day', 'Type', 'Plan', 'Actual', 'Description', 'Status'], rows,
        ['width:50px;', 'width:100px;', 'width:90px;', 'width:230px;', '', 'width:130px;'],
        ['', 'col-type', 'col-duration', 'col-actual', '', 'col-status']
      )}
    `)}

    ${logDialog()}
    ${editScript()}
  `

  return c.html(baseLayout('Workouts', content, 'workouts'))
})

const formatMetric = (a: ActualWorkoutDTO): string => {
  if (a.type === 'strength') return `${a.duration_minutes} min`
  if (a.type === 'swimming') return `${Math.round(a.distance_km * 1000)} m · ${a.duration_minutes} min`
  return `${a.distance_km.toFixed(2)} km · ${a.duration_minutes} min`
}

const actualRow = (a: ActualWorkoutDTO, w: WorkoutDTO): string => {
  const controls = a.source === 'strava'
    ? `<span style="color:#555; font-size:11px;" title="${a.note ?? 'Strava'}">strava</span>`
    : `<button class="cw-edit-btn" data-id="${a.id}" data-km="${a.distance_km}" data-mins="${a.duration_minutes}"
         data-date="${w.date}" data-type="${a.type}"
         style="background:none; border:none; color:#888; cursor:pointer; font-size:13px;">✏️</button>
       <button class="cw-del-btn" data-id="${a.id}"
         style="background:none; border:none; color:#888; cursor:pointer; font-size:13px;" title="Remove log">🗑</button>`
  return `
    <div style="display:flex; align-items:center; gap:6px; white-space:nowrap;">
      <span style="color:#666; font-size:12px; min-width:62px;">${TYPE_LABELS[a.type]}</span>
      <span style="color:#3a9e6a; font-weight:600; font-size:13px;">${formatMetric(a)}</span>
      ${controls}
    </div>
  `
}

const LOGGABLE = ['running', 'cycling', 'swimming', 'strength']

const defaultActivity = (w: WorkoutDTO): string => {
  const logged = w.actuals.map(a => a.type)
  const planned: string[] = LOGGABLE.includes(w.type)
    ? [w.type]
    : (w.details?.disciplines ?? []).filter((d: string) => LOGGABLE.includes(d))
  return planned.find(d => !logged.includes(d))
    ?? LOGGABLE.find(d => !logged.includes(d))
    ?? planned[0]
    ?? 'running'
}

const renderActual = (w: WorkoutDTO): string => {
  const addBtn = w.type === 'rest' ? '' : `
    <button class="cw-mark-btn" data-date="${w.date}" data-type="${defaultActivity(w)}"
      style="background:none; border:1px dashed #555; color:#888; padding:3px 8px; border-radius:4px; cursor:pointer; font-size:12px; align-self:flex-start;">
      + log
    </button>
  `

  if (w.actuals.length === 0) {
    if (w.type === 'rest') return '<span style="color:#444;">—</span>'
    return addBtn
  }

  return `
    <div style="display:flex; flex-direction:column; gap:4px;">
      ${w.actuals.map(a => actualRow(a, w)).join('')}
      ${addBtn}
    </div>
  `
}

const renderStatus = (w: WorkoutDTO): string => {
  if (w.is_completed) return badge('Completed', '#3a9e6a')
  if (w.is_today) return badge('Today', '#7c6aff')
  if (new Date(w.date) < new Date()) return badge('Missed', '#d97706')
  return badge('Upcoming', '#555')
}

const renderSummary = (s: WeekSummaryDTO): string => {
  const percent = Math.min(100, s.percent)
  const color = s.percent >= 100 ? '#3a9e6a' : s.percent >= 60 ? '#7c6aff' : '#d97706'
  return card(`
    <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:10px;">
      <div>
        <div style="font-size:11px; color:#7c6aff; text-transform:uppercase; letter-spacing:0.5px;">Weekly running volume</div>
        <div style="font-size:20px; font-weight:700; color:#e8e8e8; margin-top:4px;">
          ${s.actual_km} / ${s.planned_km} km
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

const logDialog = () => `
<dialog id="cw-dialog" style="background:#141414; border:1px solid #2a2a2a; border-radius:8px; padding:20px; color:#e8e8e8; width:300px;">
  <form method="dialog" id="cw-form" style="display:flex; flex-direction:column; gap:12px;">
    <div id="cw-dialog-title" style="font-size:15px; font-weight:600;">Log workout</div>

    <label style="display:flex; flex-direction:column; gap:4px; font-size:12px; color:#888;">
      Activity
      <select id="cw-activity" style="background:#1c1c1c; border:1px solid #2a2a2a; border-radius:4px; color:#e8e8e8; padding:6px; font-size:13px;">
        <option value="running">Running</option>
        <option value="cycling">Cycling</option>
        <option value="swimming">Swimming</option>
        <option value="strength">Strength</option>
      </select>
    </label>

    <label id="cw-distance-row" style="display:flex; flex-direction:column; gap:4px; font-size:12px; color:#888;">
      <span id="cw-distance-label">Distance, km</span>
      <input id="cw-distance" type="number" step="0.01" min="0" inputmode="decimal"
        style="background:#1c1c1c; border:1px solid #2a2a2a; border-radius:4px; color:#e8e8e8; padding:6px; font-size:13px;">
    </label>

    <label style="display:flex; flex-direction:column; gap:4px; font-size:12px; color:#888;">
      Duration, min
      <input id="cw-duration" type="number" step="1" min="0" inputmode="numeric"
        style="background:#1c1c1c; border:1px solid #2a2a2a; border-radius:4px; color:#e8e8e8; padding:6px; font-size:13px;">
    </label>

    <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:4px;">
      <button value="cancel" type="submit"
        style="background:none; border:1px solid #2a2a2a; color:#888; padding:6px 12px; border-radius:4px; cursor:pointer; font-size:13px;">Cancel</button>
      <button value="save" type="submit" id="cw-save"
        style="background:#7c6aff; border:none; color:#fff; padding:6px 14px; border-radius:4px; cursor:pointer; font-size:13px;">Save</button>
    </div>
  </form>
</dialog>
`

const editScript = () => `
<script>
(function() {
  async function upsert(payload) {
    const res = await fetch('/api/workouts/completed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) { alert('Error: ' + res.status); return false }
    return true
  }
  async function del(id) {
    const res = await fetch('/api/workouts/completed/' + id, { method: 'DELETE' })
    if (!res.ok && res.status !== 204) { alert('Error: ' + res.status); return false }
    return true
  }
  const dialog = document.getElementById('cw-dialog')
  const form = document.getElementById('cw-form')
  const activityEl = document.getElementById('cw-activity')
  const distanceEl = document.getElementById('cw-distance')
  const distanceRow = document.getElementById('cw-distance-row')
  const distanceLabel = document.getElementById('cw-distance-label')
  const durationEl = document.getElementById('cw-duration')
  const titleEl = document.getElementById('cw-dialog-title')
  let pendingDate = null
  let editId = null
  let editType = null

  function syncFields() {
    const type = activityEl.value
    distanceRow.style.display = type === 'strength' ? 'none' : 'flex'
    if (type === 'swimming') {
      distanceLabel.textContent = 'Distance, m'
      distanceEl.step = '10'
    } else {
      distanceLabel.textContent = 'Distance, km'
      distanceEl.step = '0.01'
    }
  }
  activityEl.addEventListener('change', syncFields)

  function openDialog(opts) {
    pendingDate = opts.date
    editId = opts.id != null ? opts.id : null
    editType = editId ? opts.type : null
    titleEl.textContent = opts.title
    activityEl.value = opts.type
    syncFields()
    const km = opts.km != null ? parseFloat(opts.km) : 0
    distanceEl.value = opts.km == null ? '' : (opts.type === 'swimming' ? Math.round(km * 1000) : km)
    durationEl.value = opts.mins != null ? opts.mins : ''
    dialog.showModal()
    durationEl.focus()
  }

  form.addEventListener('submit', async (e) => {
    if (e.submitter && e.submitter.value !== 'save') return
    e.preventDefault()
    const type = activityEl.value
    const rawDistance = parseFloat((distanceEl.value || '0').replace(',', '.'))
    const distance = isNaN(rawDistance) || rawDistance < 0 || type === 'strength' ? 0 : rawDistance
    const mins = parseInt(durationEl.value || '0', 10)
    const ok = await upsert({
      workout_date: pendingDate,
      activity_type: type,
      distance_km: type === 'swimming' ? distance / 1000 : distance,
      duration_minutes: isNaN(mins) || mins < 0 ? 0 : mins,
    })
    if (!ok) return
    // Смена типа создаёт запись по новому ключу — старую убираем.
    if (editId && editType && editType !== type) await del(editId)
    location.reload()
  })

  document.addEventListener('click', async (e) => {
    const t = e.target
    if (!(t instanceof HTMLElement)) return

    if (t.classList.contains('cw-mark-btn')) {
      openDialog({
        title: 'Log workout',
        date: t.dataset.date,
        type: t.dataset.type,
      })
      return
    }

    if (t.classList.contains('cw-edit-btn')) {
      openDialog({
        title: 'Edit log',
        date: t.dataset.date,
        type: t.dataset.type,
        km: t.dataset.km,
        mins: t.dataset.mins,
        id: t.dataset.id,
      })
      return
    }

    if (t.classList.contains('cw-del-btn')) {
      if (!confirm('Remove the completion log?')) return
      if (await del(t.dataset.id)) location.reload()
      return
    }
  })
})()
</script>
`
