/* ── State ── */
let currentData = null;

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  checkOllama();
  loadModels();
});

/* ── Ollama status ── */
async function checkOllama() {
  const pill = document.getElementById('ollama-status');
  const label = document.getElementById('status-text');
  try {
    const r = await fetch('/api/models');
    const data = await r.json();
    if (data.status === 'connected') {
      pill.className = 'status-pill status-connected';
      label.textContent = 'Ollama verbunden';
    } else {
      setDisconnected(pill, label);
    }
  } catch {
    setDisconnected(pill, label);
  }
}

function setDisconnected(pill, label) {
  pill.className = 'status-pill status-disconnected';
  label.textContent = 'Ollama nicht erreichbar';
}

/* ── Load models ── */
async function loadModels() {
  try {
    const r = await fetch('/api/models');
    const data = await r.json();
    const sel = document.getElementById('model-select');
    if (data.models && data.models.length > 0) {
      sel.innerHTML = data.models.map(m =>
        `<option value="${esc(m)}">${esc(m)}</option>`
      ).join('');
    }
  } catch {}
}

/* ── Process notes ── */
async function processNotes() {
  const notes = document.getElementById('notes-input').value.trim();
  const model = document.getElementById('model-select').value;
  const title = document.getElementById('title-input').value.trim();

  if (!notes) {
    showError('Bitte gib Meeting-Notizen ein.');
    return;
  }

  hideError();
  setLoading(true);
  setStep(2);

  try {
    const r = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes, model, title })
    });

    const data = await r.json();

    if (!r.ok) {
      throw new Error(data.detail || 'Unbekannter Fehler');
    }

    currentData = data.data;
    renderResult(currentData);
    setStep(3);
  } catch (err) {
    showError(err.message || 'Fehler bei der Verarbeitung.');
    setStep(1);
  } finally {
    setLoading(false);
  }
}

/* ── Render result ── */
function renderResult(d) {
  // Title + meta
  document.getElementById('res-title').textContent = d.title || 'Meeting Report';

  const meta = [];
  if (d.date) meta.push(`<span>📅 ${esc(d.date)}${d.time ? ' · ' + esc(d.time) : ''}</span>`);
  if (d.location) meta.push(`<span>📍 ${esc(d.location)}</span>`);
  document.getElementById('res-meta').innerHTML = meta.join('');

  // Summary
  document.getElementById('res-summary').textContent = d.summary || '';

  // Participants
  const partEl = document.getElementById('res-participants');
  const parts = d.participants || [];
  partEl.innerHTML = '';
  if (d.moderator) {
    partEl.innerHTML += `<span class="chip chip-moderator">★ ${esc(d.moderator)} (Mod.)</span>`;
  }
  parts.filter(p => p !== d.moderator).forEach(p => {
    partEl.innerHTML += `<span class="chip chip-participant">${esc(p)}</span>`;
  });
  if (!partEl.innerHTML) partEl.innerHTML = '<span style="color:#475569;font-size:.82rem">Keine Teilnehmer erfasst</span>';

  // Discussion
  const discEl = document.getElementById('res-discussion');
  discEl.innerHTML = (d.discussion_points || []).map(item => `
    <div class="disc-item">
      <div class="disc-topic">${esc(item.topic)}</div>
      <div class="disc-content">${esc(item.content)}</div>
      ${item.outcome ? `<div class="disc-outcome">→ ${esc(item.outcome)}</div>` : ''}
    </div>`).join('') || '<p style="color:#475569;font-size:.82rem">Keine Diskussionspunkte</p>';

  // Decisions
  const decEl = document.getElementById('res-decisions');
  decEl.innerHTML = (d.decisions || []).map(dec => `
    <div class="decision-item">
      <div class="decision-check">
        <svg width="8" height="8" viewBox="0 0 10 10" fill="none">
          <path d="M2 5l2.5 2.5L8 3" stroke="white" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
      </div>
      <div class="decision-text">${esc(dec)}</div>
    </div>`).join('') || '<p style="color:#475569;font-size:.82rem">Keine Entscheidungen</p>';

  // Open issues
  const issEl = document.getElementById('res-issues');
  issEl.innerHTML = (d.open_issues || []).map(i => `
    <div class="issue-item">
      <div class="issue-dot"></div>
      <div class="issue-text">${esc(i)}</div>
    </div>`).join('') || '<p style="color:#475569;font-size:.82rem">Keine offenen Punkte</p>';

  // Action items
  const actEl = document.getElementById('res-actions');
  if (d.action_items && d.action_items.length > 0) {
    actEl.innerHTML = `
      <table class="action-table">
        <thead><tr>
          <th>#</th>
          <th>Aufgabe</th>
          <th>Verantwortlich</th>
          <th>Deadline</th>
        </tr></thead>
        <tbody>
          ${d.action_items.map((item, i) => {
            const isOpen = !item.deadline || ['tbd','offen','open',''].includes((item.deadline||'').toLowerCase());
            const dlClass = isOpen ? 'badge-deadline-open' : 'badge-deadline-set';
            const dlText  = isOpen ? 'Offen' : esc(item.deadline);
            return `<tr>
              <td style="color:#475569">${i+1}</td>
              <td>${esc(item.task)}</td>
              <td>${item.responsible ? `<span class="badge badge-person">${esc(item.responsible)}</span>` : '—'}</td>
              <td><span class="badge ${dlClass}">${dlText}</span></td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>`;
  } else {
    actEl.innerHTML = '<p style="color:#475569;font-size:.82rem">Keine Action Items</p>';
  }

  // Next meeting
  const nextWrap = document.getElementById('res-next-wrap');
  if (d.next_meeting && !['', 'tbd'].includes(d.next_meeting.toLowerCase())) {
    document.getElementById('res-next').textContent = d.next_meeting;
    nextWrap.classList.remove('hidden');
  } else {
    nextWrap.classList.add('hidden');
  }

  // Show result
  document.getElementById('empty-state').classList.add('hidden');
  document.getElementById('loading-state').classList.add('hidden');
  document.getElementById('result-state').classList.remove('hidden');
}

/* ── Download PDF ── */
async function downloadPdf() {
  if (!currentData) return;

  const btn = document.getElementById('btn-pdf');
  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Generiere PDF…';

  try {
    const r = await fetch('/api/generate-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data: currentData,
        logo_text: document.getElementById('logo-input').value.trim() || ''
      })
    });

    if (!r.ok) {
      const err = await r.json();
      throw new Error(err.detail || 'PDF-Fehler');
    }

    const blob = await r.blob();
    const title = (currentData.title || 'meeting').replace(/[^a-zA-Z0-9_\- ]/g,'').trim().replace(/\s+/g,'_');
    const date = new Date().toISOString().slice(0,10).replace(/-/g,'');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title || 'meeting_report'}_${date}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('PDF-Fehler: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">📄</span> PDF herunterladen';
  }
}

/* ── Reset ── */
function resetAll() {
  currentData = null;
  document.getElementById('result-state').classList.add('hidden');
  document.getElementById('loading-state').classList.add('hidden');
  document.getElementById('empty-state').classList.remove('hidden');
  setStep(1);
}

/* ── Helpers ── */
function setLoading(on) {
  const btn = document.getElementById('btn-process');
  btn.disabled = on;
  btn.innerHTML = on
    ? '<span class="btn-icon">⏳</span> Verarbeite…'
    : '<span class="btn-icon">✨</span> Mit KI aufbereiten';

  document.getElementById('loading-state').classList.toggle('hidden', !on);
  document.getElementById('empty-state').classList.toggle('hidden', on);
  document.getElementById('result-state').classList.add('hidden');
}

function setStep(n) {
  [1, 2, 3].forEach(i => {
    const el = document.getElementById(`step-${i}`);
    el.classList.remove('active', 'done');
    if (i < n) el.classList.add('done');
    else if (i === n) el.classList.add('active');
  });
}

function showError(msg) {
  const box = document.getElementById('error-box');
  document.getElementById('error-text').textContent = msg;
  box.classList.remove('hidden');
}

function hideError() {
  document.getElementById('error-box').classList.add('hidden');
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}
