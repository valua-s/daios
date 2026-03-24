import { Hono } from 'hono'
import { baseLayout } from '../layouts/base'
import { getTasksByRange, type TaskDTO } from '../api'

export const calendarRouter = new Hono()

const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]
const DAYS_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

function pad(n: number) {
  return n < 10 ? '0' + n : '' + n
}

function isoDate(y: number, m: number, d: number) {
  return `${y}-${pad(m + 1)}-${pad(d)}`
}

/** Monday-based day of week (0=Mon, 6=Sun) */
function dayOfWeek(date: Date) {
  return (date.getDay() + 6) % 7
}

function getMonthGrid(year: number, month: number) {
  const first = new Date(year, month, 1)
  const startOffset = dayOfWeek(first)
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const cells: { day: number; date: string; isCurrentMonth: boolean }[] = []

  // days from previous month
  const prevDays = new Date(year, month, 0).getDate()
  for (let i = startOffset - 1; i >= 0; i--) {
    const d = prevDays - i
    const prev = new Date(year, month - 1, d)
    cells.push({ day: d, date: isoDate(prev.getFullYear(), prev.getMonth(), d), isCurrentMonth: false })
  }

  // current month
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, date: isoDate(year, month, d), isCurrentMonth: true })
  }

  // fill remaining to complete last week
  const remaining = 7 - (cells.length % 7)
  if (remaining < 7) {
    for (let d = 1; d <= remaining; d++) {
      const next = new Date(year, month + 1, d)
      cells.push({ day: d, date: isoDate(next.getFullYear(), next.getMonth(), d), isCurrentMonth: false })
    }
  }

  return cells
}

function getWeekDates(today: Date) {
  const dow = dayOfWeek(today)
  const monday = new Date(today)
  monday.setDate(today.getDate() - dow)
  const dates: { day: number; date: string; weekday: string; isToday: boolean }[] = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    dates.push({
      day: d.getDate(),
      date: isoDate(d.getFullYear(), d.getMonth(), d.getDate()),
      weekday: DAYS_SHORT[i],
      isToday: d.toDateString() === today.toDateString(),
    })
  }
  return dates
}

function esc(s: string) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')
}

calendarRouter.get('/', async (c) => {
  const now = new Date()
  const yearParam = c.req.query('year')
  const monthParam = c.req.query('month')
  const year = yearParam ? parseInt(yearParam) : now.getFullYear()
  const month = monthParam ? parseInt(monthParam) - 1 : now.getMonth()
  const todayIso = isoDate(now.getFullYear(), now.getMonth(), now.getDate())

  const cells = getMonthGrid(year, month)
  const rangeFrom = cells[0].date
  const rangeTo = cells[cells.length - 1].date

  let tasks: TaskDTO[]
  try {
    tasks = await getTasksByRange(rangeFrom, rangeTo)
  } catch (e: any) {
    return c.html(baseLayout('Календарь', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'calendar'))
  }

  // group tasks by date
  const byDate = new Map<string, TaskDTO[]>()
  for (const t of tasks) {
    const arr = byDate.get(t.date) ?? []
    arr.push(t)
    byDate.set(t.date, arr)
  }

  // serialize tasks map for client-side JS
  const tasksJson = JSON.stringify(
    Object.fromEntries(
      Array.from(byDate.entries()).map(([date, list]) => [
        date,
        list.map(t => ({
          title: t.title,
          time: t.scheduled_time ? t.scheduled_time.slice(0, 5) : null,
          status: t.status,
          notes: t.notes,
        })),
      ])
    )
  )

  // nav
  const prevMonth = month === 0 ? 12 : month
  const prevYear = month === 0 ? year - 1 : year
  const nextMonth = month === 11 ? 1 : month + 2
  const nextYear = month === 11 ? year + 1 : year

  // week data for mobile
  const weekDates = getWeekDates(now)
  const weekFrom = weekDates[0].date
  const weekTo = weekDates[6].date

  const content = `
    <!-- Desktop: month calendar -->
    <div class="cal-desktop">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:20px;">
        <a href="/calendar?year=${prevYear}&month=${prevMonth}" style="color:#666; text-decoration:none; font-size:18px; padding:8px 12px; border-radius:6px; background:#181818; border:1px solid #2a2a2a;">←</a>
        <h1 style="margin:0; font-size:20px; font-weight:700; color:#e8e8e8;">${MONTHS[month]} ${year}</h1>
        <a href="/calendar?year=${nextYear}&month=${nextMonth}" style="color:#666; text-decoration:none; font-size:18px; padding:8px 12px; border-radius:6px; background:#181818; border:1px solid #2a2a2a;">→</a>
      </div>

      <div class="cal-grid">
        ${DAYS_SHORT.map(d => `<div class="cal-header-cell">${d}</div>`).join('')}
        ${cells.map(cell => {
          const dayTasks = byDate.get(cell.date) ?? []
          const isToday = cell.date === todayIso
          const doneCount = dayTasks.filter(t => t.status === 'done').length
          const pendingCount = dayTasks.filter(t => t.status !== 'done').length

          return `<div class="cal-cell${isToday ? ' cal-today' : ''}${!cell.isCurrentMonth ? ' cal-other' : ''}" data-date="${cell.date}" onclick="toggleDay(this)">
            <div class="cal-day-num">${cell.day}</div>
            ${dayTasks.length > 0 ? `
              <div class="cal-dots">
                ${Array(Math.min(doneCount, 3)).fill('<span class="cal-dot cal-dot-done"></span>').join('')}
                ${Array(Math.min(pendingCount, 3)).fill('<span class="cal-dot cal-dot-pending"></span>').join('')}
              </div>
              <div class="cal-count">${dayTasks.length}</div>
            ` : ''}
          </div>`
        }).join('')}
      </div>

      <div id="cal-expand" class="cal-expand" style="display:none;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;">
          <span id="cal-expand-date" style="font-size:14px; font-weight:600; color:#e8e8e8;"></span>
          <button onclick="closeExpand()" style="background:none; border:none; cursor:pointer; color:#555; font-size:18px;">✕</button>
        </div>
        <div id="cal-expand-list"></div>
      </div>
    </div>

    <!-- Mobile: week view -->
    <div class="cal-mobile">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;">
        <span style="font-size:16px; font-weight:700; color:#e8e8e8;">Неделя</span>
        <span style="font-size:13px; color:#555;">${weekDates[0].date.slice(5)} — ${weekDates[6].date.slice(5)}</span>
      </div>

      <div class="cal-week">
        ${weekDates.map(wd => {
          const dayTasks = byDate.get(wd.date) ?? []
          const doneCount = dayTasks.filter(t => t.status === 'done').length
          const pendingCount = dayTasks.filter(t => t.status !== 'done').length

          return `<div class="cal-week-day${wd.isToday ? ' cal-today' : ''}" data-date="${wd.date}" onclick="toggleDay(this)">
            <div style="display:flex; align-items:center; justify-content:space-between;">
              <div>
                <span style="font-size:13px; font-weight:600; color:${wd.isToday ? '#7c6aff' : '#e8e8e8'};">${wd.weekday}</span>
                <span style="font-size:13px; color:#555; margin-left:6px;">${wd.day}</span>
              </div>
              ${dayTasks.length > 0 ? `
                <div style="display:flex; align-items:center; gap:4px;">
                  <div class="cal-dots">
                    ${Array(Math.min(doneCount, 3)).fill('<span class="cal-dot cal-dot-done"></span>').join('')}
                    ${Array(Math.min(pendingCount, 3)).fill('<span class="cal-dot cal-dot-pending"></span>').join('')}
                  </div>
                  <span style="font-size:12px; color:#555;">${dayTasks.length}</span>
                </div>
              ` : '<span style="font-size:12px; color:#333;">—</span>'}
            </div>
            <div class="cal-week-expand" style="display:none; margin-top:10px;"></div>
          </div>`
        }).join('')}
      </div>
    </div>

    <script>
      var calTasks = ${tasksJson};
      var openEl = null;

      function taskListHtml(date) {
        var list = calTasks[date] || [];
        if (!list.length) return '<div style="color:#444; font-size:13px;">Задач нет</div>';
        return list.map(function(t) {
          var done = t.status === 'done';
          return '<div style="display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid #222;">' +
            '<span style="width:6px;height:6px;border-radius:50%;flex-shrink:0;background:' + (done ? '#3a9e6a' : '#d97706') + ';"></span>' +
            '<span style="flex:1;font-size:13px;color:' + (done ? '#444' : '#e8e8e8') + ';' + (done ? 'text-decoration:line-through;' : '') + '">' + t.title + '</span>' +
            (t.time ? '<span style="font-size:12px;color:#555;">' + t.time + '</span>' : '') +
          '</div>';
        }).join('');
      }

      function toggleDay(el) {
        var date = el.dataset.date;
        var isMobile = el.classList.contains('cal-week-day');

        if (isMobile) {
          var expand = el.querySelector('.cal-week-expand');
          if (expand.style.display !== 'none') {
            expand.style.display = 'none';
            return;
          }
          // close others
          document.querySelectorAll('.cal-week-expand').forEach(function(e) { e.style.display = 'none'; });
          expand.innerHTML = taskListHtml(date);
          expand.style.display = 'block';
        } else {
          var panel = document.getElementById('cal-expand');
          if (panel.style.display !== 'none' && panel.dataset.date === date) {
            panel.style.display = 'none';
            return;
          }
          panel.dataset.date = date;
          var parts = date.split('-');
          document.getElementById('cal-expand-date').textContent = parts[2] + '.' + parts[1] + '.' + parts[0];
          document.getElementById('cal-expand-list').innerHTML = taskListHtml(date);
          panel.style.display = 'block';
        }
      }

      function closeExpand() {
        document.getElementById('cal-expand').style.display = 'none';
      }
    </script>
  `

  return c.html(baseLayout('Календарь', content, 'calendar'))
})
