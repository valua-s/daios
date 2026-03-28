import { Hono } from 'hono'
import { baseLayout } from '../layouts/base'
import { card, sectionTitle } from '../components/card'
import { table, badge, iconBtn } from '../components/table'
import { getTodayTasks, toggleTask, moveTaskToBacklog, deleteTask, getFocus, apiFetch } from '../api'

export const todayRouter = new Hono()

todayRouter.post('/:id/done', async (c) => {
  const id = parseInt(c.req.param('id'))
  await toggleTask(id)
  return c.redirect('/today')
})

todayRouter.post('/:id/backlog', async (c) => {
  const id = parseInt(c.req.param('id'))
  await moveTaskToBacklog(id)
  return c.redirect('/today')
})

todayRouter.post('/:id/delete', async (c) => {
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
      scheduled_date: body.date || null,
      scheduled_time: scheduledTime,
      notes: body.notes || null,
      source: 'web',
    }),
  })
  return c.redirect('/today')
})

todayRouter.get('/', async (c) => {
  const today = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
  const todayIso = new Date().toLocaleDateString('sv-SE') // YYYY-MM-DD в серверном timezone

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

  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

  const rows = sorted.map(t => {
    const doneStyle = t.status === 'done' ? ' style="color:#444;text-decoration:line-through;"' : ''
    const titleCell = `<div class="task-title"${doneStyle} title="${esc(t.title)}" data-id="${t.id}" data-title="${esc(t.title)}" data-notes="${esc(t.notes ?? '')}" data-time="${t.scheduled_time ? t.scheduled_time.slice(0, 5) : ''}" data-date="${t.scheduled_date}" data-status="${t.status}" onclick="openDetail(this)">${esc(t.title)}</div>`
    return [
    titleCell,
    t.scheduled_time
      ? `<span style="color:#666; font-size:13px;">${t.scheduled_time.slice(0, 5)}</span>`
      : `<span style="color:#333;">—</span>`,
    t.status === 'done'
      ? badge('Готово', '#3a9e6a')
      : badge('В процессе', '#d97706'),
    t.status === 'done'
      ? ''
      : `<div style="display:flex; gap:6px; align-items:center; white-space:nowrap;">
          <form method="POST" action="/today/${t.id}/done" style="display:inline;"><button type="submit" title="Выполнено" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;font-size:12px;background:#2a2a2a;color:#3a9e6a;border:1px solid #333;cursor:pointer;">✓</button></form>
          <form method="POST" action="/today/${t.id}/backlog" style="display:inline;"><button type="submit" title="В бэклог" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;font-size:12px;background:#2a2a2a;color:#666;border:1px solid #333;cursor:pointer;">бэклог ↗</button></form>
          <form method="POST" action="/today/${t.id}/delete" style="display:inline;"><button type="submit" title="Удалить" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;font-size:12px;background:#2a2a2a;color:#e05252;border:1px solid #333;cursor:pointer;">✕</button></form>
        </div>`,
  ]})

  const modal = `
    <div id="task-modal" onclick="if(event.target===this)closeModal()" style="
      display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6);
      z-index:200; align-items:center; justify-content:center; padding:16px;
    ">
      <div style="
        background:#181818; border:1px solid #2a2a2a; border-radius:12px;
        padding:28px; width:100%; max-width:460px; box-sizing:border-box;
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

          <div class="modal-date-grid">
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

    <div id="detail-modal" onclick="if(event.target===this)closeDetail()" style="
      display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6);
      z-index:200; align-items:center; justify-content:center; padding:16px;
    ">
      <div style="
        background:#181818; border:1px solid #2a2a2a; border-radius:12px;
        padding:28px; width:100%; max-width:460px; box-sizing:border-box;
      ">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:20px;">
          <h2 style="margin:0; font-size:16px; font-weight:600; color:#e8e8e8;">Задача</h2>
          <div style="display:flex; gap:8px; align-items:center;">
            <button id="d-edit-btn" onclick="startEdit()" style="
              background:none; border:1px solid #2a2a2a; cursor:pointer; border-radius:5px;
              color:#666; font-size:12px; padding:4px 10px;
            ">✎ Изменить</button>
            <button onclick="closeDetail()" style="
              background:none; border:none; cursor:pointer;
              color:#555; font-size:20px; line-height:1; padding:2px 6px;
            ">✕</button>
          </div>
        </div>

        <!-- View mode -->
        <div id="d-view">
          <div id="d-title" style="font-size:15px; color:#e8e8e8; font-weight:500; margin-bottom:10px; line-height:1.4;"></div>
          <div style="display:flex; gap:8px; align-items:center; margin-bottom:14px; flex-wrap:wrap;">
            <span id="d-status"></span>
            <span id="d-date" style="font-size:13px; color:#666;"></span>
            <span id="d-time" style="font-size:13px; color:#666;"></span>
          </div>
          <div id="d-notes-block">
            <div style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Заметки</div>
            <div id="d-notes" style="font-size:13px; line-height:1.6; white-space:pre-wrap; color:#aaa; background:#111; border-radius:6px; padding:10px 12px;"></div>
          </div>
        </div>

        <!-- Edit mode -->
        <div id="d-edit" style="display:none; flex-direction:column; gap:14px;">
          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Название</label>
            <input id="d-e-title" style="
              width:100%; box-sizing:border-box;
              background:#111; border:1px solid #2a2a2a; border-radius:6px;
              color:#e8e8e8; font-size:14px; padding:10px 12px;
              outline:none; font-family:inherit;
            " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
          </div>
          <div class="modal-date-grid">
            <div>
              <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Дата</label>
              <input id="d-e-date" type="date" style="
                width:100%; box-sizing:border-box;
                background:#111; border:1px solid #2a2a2a; border-radius:6px;
                color:#e8e8e8; font-size:14px; padding:10px 12px;
                outline:none; font-family:inherit; color-scheme:dark;
              " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
            </div>
            <div>
              <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Время</label>
              <input id="d-e-time" type="time" style="
                width:100%; box-sizing:border-box;
                background:#111; border:1px solid #2a2a2a; border-radius:6px;
                color:#e8e8e8; font-size:14px; padding:10px 12px;
                outline:none; font-family:inherit; color-scheme:dark;
              " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
            </div>
          </div>
          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Заметки</label>
            <textarea id="d-e-notes" rows="3" style="
              width:100%; box-sizing:border-box;
              background:#111; border:1px solid #2a2a2a; border-radius:6px;
              color:#e8e8e8; font-size:14px; padding:10px 12px;
              outline:none; font-family:inherit; resize:vertical;
            " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"></textarea>
          </div>
          <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:4px;">
            <button type="button" onclick="cancelEdit()" style="
              padding:9px 18px; border-radius:6px; font-size:13px; font-weight:500;
              background:transparent; color:#666; border:1px solid #2a2a2a; cursor:pointer;
            ">Отмена</button>
            <button type="button" onclick="saveEdit()" id="d-save-btn" style="
              padding:9px 18px; border-radius:6px; font-size:13px; font-weight:500;
              background:#7c6aff; color:#fff; border:none; cursor:pointer;
            ">Сохранить</button>
          </div>
        </div>
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
      var currentTaskId = null;

      function openDetail(el) {
        currentTaskId = el.dataset.id;
        document.getElementById('d-view').style.display = 'block';
        document.getElementById('d-edit').style.display = 'none';
        document.getElementById('d-edit-btn').style.display = 'inline-block';

        document.getElementById('d-title').textContent = el.dataset.title;

        var statusEl = document.getElementById('d-status');
        var isDone = el.dataset.status === 'done';
        statusEl.textContent = isDone ? 'Готово' : 'В процессе';
        statusEl.style.cssText = 'font-size:11px;padding:3px 8px;border-radius:4px;font-weight:500;' +
          (isDone ? 'background:rgba(58,158,106,0.15);color:#3a9e6a;' : 'background:rgba(217,119,6,0.15);color:#d97706;');

        var dateEl = document.getElementById('d-date');
        if (el.dataset.date) {
          var d = el.dataset.date.split('-');
          dateEl.textContent = d[2] + '.' + d[1] + '.' + d[0];
          dateEl.style.display = 'inline';
        } else { dateEl.style.display = 'none'; }

        var timeEl = document.getElementById('d-time');
        timeEl.textContent = el.dataset.time ? '🕐 ' + el.dataset.time : '';
        timeEl.style.display = el.dataset.time ? 'inline' : 'none';

        var notesBlock = document.getElementById('d-notes-block');
        var notesEl = document.getElementById('d-notes');
        if (el.dataset.notes) {
          notesEl.textContent = el.dataset.notes;
          notesBlock.style.display = 'block';
        } else {
          notesBlock.style.display = 'none';
        }

        // pre-fill edit fields
        document.getElementById('d-e-title').value = el.dataset.title;
        document.getElementById('d-e-date').value = el.dataset.date || '';
        document.getElementById('d-e-time').value = el.dataset.time || '';
        document.getElementById('d-e-notes').value = el.dataset.notes || '';

        document.getElementById('detail-modal').style.display = 'flex';
      }

      function startEdit() {
        document.getElementById('d-view').style.display = 'none';
        document.getElementById('d-edit').style.display = 'flex';
        document.getElementById('d-edit-btn').style.display = 'none';
        document.getElementById('d-e-title').focus();
      }

      function cancelEdit() {
        document.getElementById('d-view').style.display = 'block';
        document.getElementById('d-edit').style.display = 'none';
        document.getElementById('d-edit-btn').style.display = 'inline-block';
      }

      function saveEdit() {
        var btn = document.getElementById('d-save-btn');
        btn.disabled = true;
        btn.textContent = '...';

        var title = document.getElementById('d-e-title').value.trim();
        var date = document.getElementById('d-e-date').value;
        var time = document.getElementById('d-e-time').value;
        var notes = document.getElementById('d-e-notes').value;

        var body = {};
        if (title) body.title = title;
        if (date) body.scheduled_date = date;
        if (time) {
          body.scheduled_time = time.length === 5 ? time + ':00' : time;
        } else {
          body.clear_time = true;
        }
        if (notes) {
          body.notes = notes;
        } else {
          body.clear_notes = true;
        }

        fetch('/api/tasks/' + currentTaskId, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }).then(function(res) {
          if (!res.ok) throw new Error(res.status);
          window.location.reload();
        }).catch(function(err) {
          btn.disabled = false;
          btn.textContent = 'Сохранить';
          alert('Ошибка сохранения: ' + (err.message || 'неизвестная ошибка'));
        });
      }

      function closeDetail() {
        document.getElementById('detail-modal').style.display = 'none';
      }
      document.addEventListener('keydown', function(e) { if (e.key === 'Escape') { closeModal(); closeDetail(); } });
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
          <div style="font-size:11px; color:#555; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px;">Фокус недели</div>
          <div style="font-size:15px; color:#e8e8e8; line-height:1.4;">${focus.week?.description ?? '—'}</div>
        </div>
        <div class="focus-month" style="border-top:1px solid #2a2a2a; padding-top:10px;">
          <div style="font-size:11px; color:#555; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px;">Фокус месяца</div>
          <div style="font-size:14px; color:#888; line-height:1.4;">${focus.month?.description ?? '—'}</div>
        </div>
      </div>
      ${statsBlock}
    </div>

    ${tasksBlock}
  `

  return c.html(baseLayout('Сегодня', content, 'today'))
})
