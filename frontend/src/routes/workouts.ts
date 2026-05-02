import { Hono } from 'hono'
import { getCookie } from 'hono/cookie'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle } from '../components/card'
import { table, badge } from '../components/table'
import { getWeekWorkouts, type WorkoutDTO } from '../api'

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
  let workouts: Awaited<ReturnType<typeof getWeekWorkouts>>
  try {
    workouts = await getWeekWorkouts(token)
  } catch (e: any) {
    return c.html(baseLayout('Тренировки', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'workouts'))
  }

  const todayWorkout = workouts.find(w => w.is_today)
  const weekDone = workouts.filter(w => w.is_today === false && new Date(w.date) < new Date() && w.type !== 'rest').length
  const totalKm = workouts.reduce((acc, w) => {
    const km = w.details.total_km as number | undefined
    return acc + (km ?? 0)
  }, 0)
  const upcoming = workouts.filter(w => new Date(w.date) > new Date() && w.type !== 'rest').length

  const rows = workouts.map(w => [
    `<span style="color:${w.is_today ? '#7c6aff' : '#888'}; font-weight:${w.is_today ? '600' : '400'};">${w.day}</span>`,
    badge(TYPE_LABELS[w.type], TYPE_COLORS[w.type]),
    `<span style="color:${w.type === 'rest' ? '#444' : '#888'}; font-size:13px;">${w.description}</span>`,
    w.duration_minutes ? `<span style="color:#666; font-size:13px;">${w.duration_minutes} мин</span>` : '—',
    w.is_today ? badge('Сегодня', '#7c6aff') : new Date(w.date) < new Date() ? badge('Готово', '#3a9e6a') : badge('Впереди', '#555'),
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

  const content = `
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:28px;">
      <div>
        <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Тренировки</h1>
        <div style="font-size:13px; color:#555; margin-top:4px;">Расписание на неделю из Google Sheets</div>
      </div>
    </div>

    ${todayCard}
    ${todayCard ? '<div style="height:16px;"></div>' : ''}

    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px;">
      ${statMini('Выполнено', `${weekDone} / ${workouts.filter(w => w.type !== 'rest').length}`, '#7c6aff')}
      ${statMini('Км на неделе', totalKm > 0 ? `~${Math.round(totalKm)} км` : '—', '#3a9e6a')}
      ${statMini('Осталось', `${upcoming} трен.`, '#d97706')}
    </div>

    ${card(`
      ${sectionTitle('Неделя')}
      ${table(['День', 'Тип', 'Описание', 'Время', 'Статус'], rows,
        ['width:50px;', 'width:100px;', '', 'width:90px;', 'width:110px;'],
        ['', 'col-type', '', 'col-duration', 'col-status']
      )}
    `)}
  `

  return c.html(baseLayout('Тренировки', content, 'workouts'))
})

const statMini = (label: string, value: string, color: string) =>
  card(`
    <div style="font-size:20px; font-weight:700; color:${color};">${value}</div>
    <div style="font-size:12px; color:#555; margin-top:2px;">${label}</div>
  `)
