import { Hono } from 'hono'
import { getCookie } from 'hono/cookie'
import { baseLayout } from '../layouts/base'
import { getDiaryEntries } from '../api'

export const diaryRouter = new Hono()

diaryRouter.get('/', async (c) => {
  const token = getCookie(c, 'daios_session')

  let entries: Awaited<ReturnType<typeof getDiaryEntries>>
  try {
    entries = await getDiaryEntries(token)
  } catch (e: any) {
    return c.html(baseLayout('Дневник', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'diary'))
  }

  const esc = (s: string | null) =>
    (s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

  const dayLabel = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
  }
  const timeLabel = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

  const entryCard = (e: typeof entries[number]) => `
    <div data-id="${e.id}" style="background:#181818; border:1px solid #2a2a2a; border-radius:10px; padding:16px 18px; display:flex; flex-direction:column; gap:10px;">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
        <span style="font-size:12px; color:#666;">${e.kind === 'voice' ? '🎙' : '✍️'} ${timeLabel(e.created_at)}</span>
        <button onclick="deleteEntry(${e.id})" style="background:none; border:none; cursor:pointer; color:#555; font-size:14px; padding:2px 6px;" onmouseover="this.style.color='#e05252'" onmouseout="this.style.color='#555'">✕</button>
      </div>
      <div style="font-size:14px; line-height:1.6; white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word; color:#e8e8e8;">${esc(e.content)}</div>
    </div>`

  let feed: string
  if (entries.length === 0) {
    feed = `<div style="padding:48px; text-align:center; color:#555;">Записей пока нет — поделитесь мыслями голосом или текстом</div>`
  } else {
    const groups: string[] = []
    let lastDay = ''
    for (const e of entries) {
      const day = dayLabel(e.created_at)
      if (day !== lastDay) {
        groups.push(`<div style="font-size:12px; color:#7c6aff; text-transform:uppercase; letter-spacing:0.5px; margin:18px 0 4px;">${day}</div>`)
        lastDay = day
      }
      groups.push(entryCard(e))
    }
    feed = `<div style="display:flex; flex-direction:column; gap:10px;">${groups.join('')}</div>`
  }

  const composer = `
    <div style="background:#181818; border:1px solid #2a2a2a; border-radius:12px; padding:18px; margin-bottom:24px; display:flex; flex-direction:column; gap:12px;">
      <textarea id="d-text" rows="3" placeholder="Что у вас на душе?..." style="
        width:100%; box-sizing:border-box; background:#111; border:1px solid #2a2a2a; border-radius:8px;
        color:#e8e8e8; font-size:14px; padding:12px; outline:none; font-family:inherit; resize:vertical;
      " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"></textarea>
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
        <div style="display:flex; align-items:center; gap:10px;">
          <button id="d-rec-btn" onclick="toggleDictation()" style="
            display:flex; align-items:center; gap:8px; padding:9px 16px; border-radius:8px; font-size:13px;
            background:#2a2a2a; color:#e8e8e8; border:1px solid #333; cursor:pointer;
          "><span id="d-rec-dot" style="width:10px; height:10px; border-radius:50%; background:#e05252; display:inline-block;"></span><span id="d-rec-label">Голосовой ввод</span></button>
          <span id="d-rec-status" style="font-size:12px; color:#888;"></span>
        </div>
        <button id="d-save-btn" onclick="saveEntry()" style="
          padding:9px 18px; border-radius:8px; font-size:13px; font-weight:500;
          background:#7c6aff; color:#fff; border:none; cursor:pointer;
        ">Записать</button>
      </div>
    </div>`

  const script = `
    <script>
      var recognition = null;
      var listening = false;
      var dictated = false;
      var baseText = '';

      function saveEntry() {
        var ta = document.getElementById('d-text');
        var text = ta.value.trim();
        if (!text) { ta.focus(); return; }
        if (listening) stopDictation();
        var btn = document.getElementById('d-save-btn');
        btn.disabled = true; btn.textContent = '...';
        fetch('/api/diary/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: text, kind: dictated ? 'voice' : 'text' }),
        }).then(function(r){
          if (!r.ok) throw new Error(r.status);
          window.location.reload();
        }).catch(function(err){
          btn.disabled = false; btn.textContent = 'Записать';
          alert('Ошибка: ' + err.message);
        });
      }

      function toggleDictation() {
        if (listening) { stopDictation(); return; }
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
          alert('Голосовой ввод не поддерживается в этом браузере (нужен Chrome или Edge)');
          return;
        }
        recognition = new SR();
        recognition.lang = 'ru-RU';
        recognition.interimResults = true;
        recognition.continuous = true;

        var ta = document.getElementById('d-text');
        baseText = ta.value ? ta.value.replace(/\\s*$/, '') + ' ' : '';

        recognition.onresult = function(ev){
          var finalText = '';
          var interim = '';
          for (var i = 0; i < ev.results.length; i++) {
            var res = ev.results[i];
            if (res.isFinal) finalText += res[0].transcript;
            else interim += res[0].transcript;
          }
          if (finalText) dictated = true;
          ta.value = baseText + finalText + interim;
        };
        recognition.onerror = function(ev){
          document.getElementById('d-rec-status').textContent = ev.error === 'no-speech' ? 'Ничего не услышал' : 'Ошибка: ' + ev.error;
        };
        recognition.onend = function(){
          if (listening) { try { recognition.start(); return; } catch (e) {} }
          setIdleUI();
        };

        try { recognition.start(); } catch (e) { alert('Не удалось запустить: ' + e.message); return; }
        listening = true;
        document.getElementById('d-rec-label').textContent = 'Остановить';
        document.getElementById('d-rec-dot').style.animation = 'pulse 1s infinite';
        document.getElementById('d-rec-status').textContent = 'Слушаю...';
      }

      function stopDictation() {
        listening = false;
        if (recognition) { try { recognition.stop(); } catch (e) {} }
        setIdleUI();
      }

      function setIdleUI() {
        document.getElementById('d-rec-label').textContent = 'Голосовой ввод';
        document.getElementById('d-rec-dot').style.animation = '';
        document.getElementById('d-rec-status').textContent = '';
      }

      function deleteEntry(id) {
        if (!confirm('Удалить запись?')) return;
        fetch('/api/diary/' + id, { method: 'DELETE' })
          .then(function(r){ if (!r.ok) throw new Error(r.status); window.location.reload(); })
          .catch(function(err){ alert('Ошибка: ' + err.message); });
      }
    </script>
    <style>@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }</style>`

  const content = `
    <div style="margin-bottom:24px;">
      <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Дневник</h1>
      <div style="font-size:13px; color:#555; margin-top:4px;">Переживания и мысли — голосом или текстом</div>
    </div>
    ${composer}
    ${feed}
    ${script}`

  return c.html(baseLayout('Дневник', content, 'diary'))
})
