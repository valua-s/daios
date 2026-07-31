import { Hono } from 'hono'
import { getCookie } from 'hono/cookie'
import { baseLayout } from '../layouts/base'
import { getNotes } from '../api'

export const notesRouter = new Hono()

notesRouter.get('/', async (c) => {
  const token = getCookie(c, 'daios_session')

  let notes: Awaited<ReturnType<typeof getNotes>>
  try {
    notes = await getNotes(token)
  } catch (e: any) {
    return c.html(baseLayout('Notes', `<div style="padding:40px; color:#e05252;">⚠ ${e.message}</div>`, 'notes'))
  }

  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

  const noteCard = (n: typeof notes[number]) => {
    const total = n.items.length
    const checked = n.items.filter(i => i.checked).length
    const preview = n.body
      ? esc(n.body).slice(0, 140) + (n.body.length > 140 ? '…' : '')
      : ''
    const itemsPreview = n.items.slice(0, 4).map(i => `
      <div style="display:flex; gap:8px; align-items:flex-start; font-size:13px; color:${i.checked ? '#444' : '#aaa'}; ${i.checked ? 'text-decoration:line-through;' : ''}">
        <span style="color:#666; flex-shrink:0;">${i.checked ? '☑' : '☐'}</span>
        <span style="flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(i.text)}</span>
      </div>
    `).join('')
    const moreItems = n.items.length > 4 ? `<div style="font-size:11px; color:#555; margin-top:4px;">+ ${n.items.length - 4} more</div>` : ''

    return `
      <div class="note-card" data-id="${n.id}" onclick="openNote(${n.id})" style="
        background:#181818; border:1px solid #2a2a2a; border-radius:10px;
        padding:18px; cursor:pointer; transition:border-color 0.15s;
        display:flex; flex-direction:column; gap:10px;
      " onmouseover="this.style.borderColor='#3a3a3a'" onmouseout="this.style.borderColor='#2a2a2a'">
        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:10px;">
          <div style="font-size:15px; font-weight:600; color:#e8e8e8; line-height:1.3; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis;">${esc(n.title)}</div>
          ${total > 0 ? `<div style="font-size:11px; color:#7c6aff; background:rgba(124,106,255,0.1); padding:2px 8px; border-radius:10px; flex-shrink:0; white-space:nowrap;">${checked}/${total}</div>` : ''}
        </div>
        ${preview ? `<div style="font-size:13px; color:#888; line-height:1.5; white-space:pre-wrap; max-height:60px; overflow:hidden;">${preview}</div>` : ''}
        ${itemsPreview ? `<div style="display:flex; flex-direction:column; gap:4px; margin-top:4px;">${itemsPreview}${moreItems}</div>` : ''}
      </div>
    `
  }

  const grid = notes.length === 0
    ? `<div style="padding:48px; text-align:center; color:#555;">No notes — create your first one</div>`
    : `<div class="notes-grid" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:16px;">
        ${notes.map(noteCard).join('')}
      </div>`

  const createModal = `
    <div id="note-create-modal" class="note-modal" onclick="if(event.target===this)closeCreate()" style="
      display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6);
      z-index:200; align-items:center; justify-content:center; padding:16px;
    ">
      <div class="note-modal-card" style="background:#181818; border:1px solid #2a2a2a; border-radius:12px; padding:28px; width:100%; max-width:460px; box-sizing:border-box;">
        <div class="note-modal-head" style="display:flex; align-items:center; justify-content:space-between; margin-bottom:24px;">
          <h2 style="margin:0; font-size:16px; font-weight:600; color:#e8e8e8;">New note</h2>
          <button onclick="closeCreate()" style="background:none; border:none; cursor:pointer; color:#555; font-size:20px; line-height:1; padding:2px 6px;">✕</button>
        </div>
        <div class="note-modal-body" style="display:flex; flex-direction:column; gap:16px;">
          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Title *</label>
            <input id="nc-title" required autofocus placeholder="Note title" style="
              width:100%; box-sizing:border-box; background:#111; border:1px solid #2a2a2a; border-radius:6px;
              color:#e8e8e8; font-size:14px; padding:10px 12px; outline:none; font-family:inherit;
            " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
          </div>
          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Description</label>
            <textarea id="nc-body" rows="2" placeholder="Free-form text (optional)..." style="
              width:100%; box-sizing:border-box; background:#111; border:1px solid #2a2a2a; border-radius:6px;
              color:#e8e8e8; font-size:14px; padding:10px 12px; outline:none; font-family:inherit; resize:vertical;
            " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"></textarea>
          </div>
          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Checklist</label>
            <div id="nc-items" style="display:flex; flex-direction:column; gap:6px; margin-bottom:8px;"></div>
            <div style="display:flex; gap:8px;">
              <input id="nc-new-item" placeholder="Item + Enter" onkeydown="if(event.key==='Enter'){event.preventDefault();addDraftItem()}" style="
                flex:1; box-sizing:border-box; background:#111; border:1px solid #2a2a2a; border-radius:6px;
                color:#e8e8e8; font-size:13px; padding:8px 12px; outline:none; font-family:inherit;
              " onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
              <button type="button" onclick="addDraftItem()" style="padding:8px 14px; border-radius:6px; font-size:13px; background:#2a2a2a; color:#e8e8e8; border:1px solid #333; cursor:pointer;">+</button>
            </div>
          </div>
        </div>
        <div class="note-modal-foot" style="display:flex; gap:10px; justify-content:flex-end; margin-top:16px;">
          <button type="button" onclick="closeCreate()" style="padding:9px 18px; border-radius:6px; font-size:13px; font-weight:500; background:transparent; color:#666; border:1px solid #2a2a2a; cursor:pointer;">Cancel</button>
          <button type="button" id="nc-save" onclick="saveCreate()" style="padding:9px 18px; border-radius:6px; font-size:13px; font-weight:500; background:#7c6aff; color:#fff; border:none; cursor:pointer;">Create</button>
        </div>
      </div>
    </div>
  `

  const detailModal = `
    <div id="note-detail-modal" class="note-modal" onclick="if(event.target===this)closeDetail()" style="
      display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6);
      z-index:200; align-items:flex-start; justify-content:center; padding:16px; overflow-y:auto;
    ">
      <div class="note-modal-card" style="background:#181818; border:1px solid #2a2a2a; border-radius:12px; padding:28px; width:100%; max-width:560px; box-sizing:border-box; margin:32px 0;">
        <div class="note-modal-head" style="display:flex; align-items:center; justify-content:space-between; margin-bottom:20px; gap:10px;">
          <h2 style="margin:0; font-size:16px; font-weight:600; color:#e8e8e8;">Note</h2>
          <div style="display:flex; gap:8px;">
            <button id="nd-edit-btn" onclick="startNoteEdit()" style="background:none; border:1px solid #2a2a2a; cursor:pointer; border-radius:5px; color:#666; font-size:12px; padding:4px 10px;">✎ Edit</button>
            <button onclick="deleteCurrentNote()" style="background:none; border:1px solid #2a2a2a; cursor:pointer; border-radius:5px; color:#e05252; font-size:12px; padding:4px 10px;">✕ Delete</button>
            <button onclick="closeDetail()" style="background:none; border:none; cursor:pointer; color:#555; font-size:20px; line-height:1; padding:2px 6px;">✕</button>
          </div>
        </div>

        <div class="note-modal-body">
        <!-- View mode -->
        <div id="nd-view">
          <div id="nd-title" style="font-size:17px; color:#e8e8e8; font-weight:600; margin-bottom:10px; line-height:1.3;"></div>
          <div id="nd-body-block" style="margin-bottom:18px;">
            <div id="nd-body" style="font-size:13px; line-height:1.6; white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word; color:#aaa; background:#111; border-radius:6px; padding:10px 12px;"></div>
          </div>
        </div>

        <!-- Edit mode -->
        <div id="nd-edit" style="display:none; flex-direction:column; gap:14px; margin-bottom:18px;">
          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Title</label>
            <input id="nd-e-title" style="width:100%; box-sizing:border-box; background:#111; border:1px solid #2a2a2a; border-radius:6px; color:#e8e8e8; font-size:14px; padding:10px 12px; outline:none; font-family:inherit;" onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
          </div>
          <div>
            <label style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:6px;">Description</label>
            <textarea id="nd-e-body" rows="3" style="width:100%; box-sizing:border-box; background:#111; border:1px solid #2a2a2a; border-radius:6px; color:#e8e8e8; font-size:14px; padding:10px 12px; outline:none; font-family:inherit; resize:vertical;" onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"></textarea>
          </div>
          <div style="display:flex; gap:10px; justify-content:flex-end;">
            <button type="button" onclick="cancelNoteEdit()" style="padding:8px 16px; border-radius:6px; font-size:13px; background:transparent; color:#666; border:1px solid #2a2a2a; cursor:pointer;">Cancel</button>
            <button type="button" id="nd-save-btn" onclick="saveNoteEdit()" style="padding:8px 16px; border-radius:6px; font-size:13px; background:#7c6aff; color:#fff; border:none; cursor:pointer;">Save</button>
          </div>
        </div>

        <!-- Items -->
        <div style="font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:10px;">Checklist</div>
        <div id="nd-items" style="display:flex; flex-direction:column; gap:6px; margin-bottom:12px;"></div>
        </div>

        <div class="note-modal-foot" style="display:flex; gap:8px;">
          <input id="nd-new-item" placeholder="New item..." onkeydown="if(event.key==='Enter'){event.preventDefault();addItem()}" style="flex:1; box-sizing:border-box; background:#111; border:1px solid #2a2a2a; border-radius:6px; color:#e8e8e8; font-size:13px; padding:8px 12px; outline:none; font-family:inherit;" onfocus="this.style.borderColor='#7c6aff'" onblur="this.style.borderColor='#2a2a2a'"/>
          <button type="button" onclick="addItem()" style="padding:8px 14px; border-radius:6px; font-size:13px; background:#2a2a2a; color:#e8e8e8; border:1px solid #333; cursor:pointer;">+</button>
        </div>
      </div>
    </div>
  `

  const script = `
    <script>
      var currentNoteId = null;
      var draftItems = [];

      function openCreate() {
        var m = document.getElementById('note-create-modal');
        m.style.display = 'flex';
        document.getElementById('nc-title').value = '';
        document.getElementById('nc-body').value = '';
        document.getElementById('nc-new-item').value = '';
        draftItems = [];
        renderDraftItems();
        setTimeout(function(){ document.getElementById('nc-title').focus(); }, 50);
      }
      function closeCreate() { document.getElementById('note-create-modal').style.display = 'none'; }

      function addDraftItem() {
        var input = document.getElementById('nc-new-item');
        var text = input.value.trim();
        if (!text) return;
        draftItems.push(text);
        input.value = '';
        renderDraftItems();
        input.focus();
      }

      function removeDraftItem(idx) {
        draftItems.splice(idx, 1);
        renderDraftItems();
      }

      function renderDraftItems() {
        var box = document.getElementById('nc-items');
        if (!draftItems.length) { box.innerHTML = ''; return; }
        box.innerHTML = draftItems.map(function(t, i){
          return '<div class="note-item-row" style="display:flex; gap:10px; align-items:center; padding:6px 8px; background:#111; border-radius:6px;">' +
            '<span class="note-check-mark" style="color:#555; font-size:13px;">☐</span>' +
            '<span style="flex:1; min-width:0; color:#e8e8e8; font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">' + escAttr(t) + '</span>' +
            '<button class="note-item-del" onclick="removeDraftItem(' + i + ')" style="background:none; border:none; cursor:pointer; color:#555; font-size:14px; padding:2px 6px;">✕</button>' +
          '</div>';
        }).join('');
      }

      function saveCreate() {
        var title = document.getElementById('nc-title').value.trim();
        if (!title) { alert('Enter a title'); return; }
        var body = document.getElementById('nc-body').value.trim() || null;
        var pendingInput = document.getElementById('nc-new-item').value.trim();
        if (pendingInput) draftItems.push(pendingInput);
        var btn = document.getElementById('nc-save');
        btn.disabled = true; btn.textContent = '...';
        fetch('/api/notes/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: title, body: body }),
        }).then(function(res){
          if (!res.ok) throw new Error(res.status);
          return res.json();
        }).then(function(note){
          if (!draftItems.length) return null;
          return draftItems.reduce(function(p, text){
            return p.then(function(){
              return fetch('/api/notes/' + note.id + '/items', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text }),
              });
            });
          }, Promise.resolve());
        }).then(function(){
          window.location.reload();
        }).catch(function(err){
          btn.disabled = false; btn.textContent = 'Create';
          alert('Error: ' + err.message);
        });
      }

      function openNote(id) {
        currentNoteId = id;
        fetch('/api/notes/' + id).then(function(r){
          if (!r.ok) throw new Error(r.status);
          return r.json();
        }).then(function(n){
          renderNote(n);
          document.getElementById('note-detail-modal').style.display = 'flex';
        }).catch(function(err){ alert('Failed to load: ' + err.message); });
      }

      function renderNote(n) {
        document.getElementById('nd-view').style.display = 'block';
        document.getElementById('nd-edit').style.display = 'none';
        document.getElementById('nd-edit-btn').style.display = 'inline-block';

        document.getElementById('nd-title').textContent = n.title;
        var bodyBlock = document.getElementById('nd-body-block');
        var bodyEl = document.getElementById('nd-body');
        if (n.body) {
          bodyEl.textContent = n.body;
          bodyBlock.style.display = 'block';
        } else {
          bodyBlock.style.display = 'none';
        }
        document.getElementById('nd-e-title').value = n.title;
        document.getElementById('nd-e-body').value = n.body || '';
        renderItems(n.items);
      }

      function renderItems(items) {
        var box = document.getElementById('nd-items');
        if (!items.length) {
          box.innerHTML = '<div style="font-size:12px; color:#555; padding:6px 0;">No items yet</div>';
          return;
        }
        box.innerHTML = items.map(function(i){
          var textStyle = i.checked ? 'color:#555; text-decoration:line-through;' : 'color:#e8e8e8;';
          return '<div class="note-item-row" style="display:flex; gap:10px; align-items:center; padding:6px 8px; background:#111; border-radius:6px;">' +
            '<input type="checkbox" class="note-check" ' + (i.checked ? 'checked' : '') + ' onchange="toggleItem(' + i.id + ')" style="cursor:pointer; accent-color:#7c6aff;"/>' +
            '<input class="note-item-text" data-id="' + i.id + '" value="' + escAttr(i.text) + '" onblur="saveItemText(' + i.id + ', this.value)" onkeydown="if(event.key===\\'Enter\\'){this.blur()}" style="flex:1; min-width:0; background:transparent; border:none; font-size:13px; padding:4px 0; outline:none; font-family:inherit; ' + textStyle + '"/>' +
            '<button class="note-item-del" onclick="deleteItem(' + i.id + ')" style="background:none; border:none; cursor:pointer; color:#555; font-size:14px; padding:2px 6px;">✕</button>' +
          '</div>';
        }).join('');
      }

      function escAttr(s) { return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'); }

      function refreshCurrentNote() {
        if (currentNoteId == null) return Promise.resolve();
        return fetch('/api/notes/' + currentNoteId).then(function(r){ return r.json(); }).then(function(n){
          renderItems(n.items);
        });
      }

      function addItem() {
        var input = document.getElementById('nd-new-item');
        var text = input.value.trim();
        if (!text || currentNoteId == null) return;
        fetch('/api/notes/' + currentNoteId + '/items', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text }),
        }).then(function(r){
          if (!r.ok) throw new Error(r.status);
          input.value = '';
          return refreshCurrentNote();
        }).catch(function(err){ alert('Error: ' + err.message); });
      }

      function toggleItem(id) {
        fetch('/api/notes/items/' + id + '/toggle', { method: 'POST' })
          .then(function(r){ if (!r.ok) throw new Error(r.status); return refreshCurrentNote(); })
          .catch(function(err){ alert('Error: ' + err.message); });
      }

      function saveItemText(id, text) {
        text = text.trim();
        if (!text) return;
        fetch('/api/notes/items/' + id, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text }),
        }).catch(function(err){ alert('Error: ' + err.message); });
      }

      function deleteItem(id) {
        fetch('/api/notes/items/' + id, { method: 'DELETE' })
          .then(function(r){ if (!r.ok) throw new Error(r.status); return refreshCurrentNote(); })
          .catch(function(err){ alert('Error: ' + err.message); });
      }

      function startNoteEdit() {
        document.getElementById('nd-view').style.display = 'none';
        document.getElementById('nd-edit').style.display = 'flex';
        document.getElementById('nd-edit-btn').style.display = 'none';
        document.getElementById('nd-e-title').focus();
      }

      function cancelNoteEdit() {
        document.getElementById('nd-view').style.display = 'block';
        document.getElementById('nd-edit').style.display = 'none';
        document.getElementById('nd-edit-btn').style.display = 'inline-block';
      }

      function saveNoteEdit() {
        var title = document.getElementById('nd-e-title').value.trim();
        var body = document.getElementById('nd-e-body').value;
        var btn = document.getElementById('nd-save-btn');
        btn.disabled = true; btn.textContent = '...';
        var payload = {};
        if (title) payload.title = title;
        if (body.trim()) payload.body = body;
        else payload.clear_body = true;
        fetch('/api/notes/' + currentNoteId, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }).then(function(r){
          if (!r.ok) throw new Error(r.status);
          return r.json();
        }).then(function(n){
          renderNote(n);
          btn.disabled = false; btn.textContent = 'Save';
        }).catch(function(err){
          btn.disabled = false; btn.textContent = 'Save';
          alert('Error: ' + err.message);
        });
      }

      function deleteCurrentNote() {
        if (currentNoteId == null) return;
        if (!confirm('Delete this note?')) return;
        fetch('/api/notes/' + currentNoteId, { method: 'DELETE' })
          .then(function(r){ if (!r.ok) throw new Error(r.status); window.location.reload(); })
          .catch(function(err){ alert('Error: ' + err.message); });
      }

      function closeDetail() {
        document.getElementById('note-detail-modal').style.display = 'none';
        currentNoteId = null;
        window.location.reload();
      }

      document.addEventListener('keydown', function(e){
        if (e.key === 'Escape') {
          if (document.getElementById('note-create-modal').style.display === 'flex') closeCreate();
          else if (document.getElementById('note-detail-modal').style.display === 'flex') closeDetail();
        }
      });
    </script>
  `

  const content = `
    ${createModal}
    ${detailModal}

    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; gap:12px; flex-wrap:wrap;">
      <div>
        <h1 style="margin:0; font-size:22px; font-weight:700; color:#e8e8e8;">Notes</h1>
        <div style="font-size:13px; color:#555; margin-top:4px;">Free-form notes and checklists</div>
      </div>
      <button onclick="openCreate()" style="
        padding:8px 16px; border-radius:6px; font-size:13px; font-weight:500;
        background:#7c6aff; color:#fff; border:none; cursor:pointer;
      ">+ New note</button>
    </div>

    ${grid}
    ${script}
  `

  return c.html(baseLayout('Notes', content, 'notes'))
})
