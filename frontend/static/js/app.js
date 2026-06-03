/* ─── STATE ─────────────────────────────────────────────────── */
let lastResult = null;

const API = '';   // same origin

/* ─── INIT ──────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Set today's date
  const dateInput = document.getElementById('meeting-date');
  const today = new Date().toISOString().split('T')[0];
  dateInput.value = today;

  // Char counter
  const notesTA = document.getElementById('raw-notes');
  notesTA.addEventListener('input', () => {
    document.getElementById('char-count').textContent =
      notesTA.value.length.toLocaleString('de') + ' Zeichen';
  });

  // Load saved settings
  const savedUrl   = localStorage.getItem('ollama_url');
  const savedModel = localStorage.getItem('ollama_model');
  if (savedUrl)   document.getElementById('ollama-url').value = savedUrl;
  if (savedModel) {
    const sel = document.getElementById('ollama-model');
    const opt = [...sel.options].find(o => o.value === savedModel);
    if (opt) sel.value = savedModel;
  }

  checkOllama();
});

/* ─── TAB NAVIGATION ────────────────────────────────────────── */
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.disabled) return;
    switchTab(btn.dataset.tab);
  });
});

function switchTab(tab) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.querySelector(`.nav-item[data-tab="${tab}"]`).classList.add('active');
}

/* ─── OLLAMA STATUS ──────────────────────────────────────────── */
async function checkOllama() {
  const url   = document.getElementById('ollama-url').value.trim() || 'http://localhost:11434';
  const dot1  = document.querySelector('#ollama-status .status-dot');
  const dot2  = document.querySelector('#ollama-inline .status-dot');
  const text2 = document.getElementById('ollama-inline-text');
  const settingsBox  = document.getElementById('settings-status');
  const settingsDot  = settingsBox.querySelector('.status-dot');
  const settingsText = settingsBox.querySelector('span');

  [dot1, dot2, settingsDot].forEach(d => { if(d) d.className = 'status-dot checking'; });
  document.querySelector('#ollama-status span').textContent = 'Prüfe Verbindung…';
  if (text2) text2.textContent = 'Verbindung wird geprüft…';

  try {
    const resp = await fetch(`${API}/api/check-ollama`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ollama_url: url }),
    });
    const data = await resp.json();

    if (data.status === 'online') {
      [dot1, dot2, settingsDot].forEach(d => { if(d) d.className = 'status-dot online'; });
      document.querySelector('#ollama-status span').textContent = 'Ollama verbunden';
      if (text2) text2.textContent = 'Ollama läuft ✓';
      settingsText.textContent = `Ollama online · ${data.models.length} Modell(e) verfügbar`;

      if (data.models.length) {
        showAvailableModels(data.models);
      }
    } else {
      throw new Error('offline');
    }
  } catch {
    [dot1, dot2, settingsDot].forEach(d => { if(d) d.className = 'status-dot offline'; });
    document.querySelector('#ollama-status span').textContent = 'Ollama nicht erreichbar';
    if (text2) text2.textContent = 'Ollama nicht gefunden';
    settingsText.textContent = 'Ollama nicht erreichbar — ist Ollama gestartet?';
  }
}

function showAvailableModels(models) {
  const box  = document.getElementById('available-models-box');
  const list = document.getElementById('available-models-list');
  list.innerHTML = '';
  models.forEach(m => {
    const chip = document.createElement('span');
    chip.className = 'model-chip';
    chip.textContent = m;
    chip.onclick = () => {
      const shortName = m.split(':')[0];
      const sel = document.getElementById('ollama-model');
      const existing = [...sel.options].find(o => o.value === shortName);
      if (!existing) {
        const opt = document.createElement('option');
        opt.value = shortName;
        opt.textContent = shortName;
        sel.appendChild(opt);
      }
      sel.value = shortName;
    };
    list.appendChild(chip);
  });
  box.style.display = 'block';
}

/* ─── TEMPLATES ─────────────────────────────────────────────── */
function loadTemplate(type) {
  const ta = document.getElementById('raw-notes');
  if (type === 'short') {
    ta.value = `Kick-off Produktteam
- Anwesend: Anna, Max, Lisa, Tom
- Neues Dashboard-Feature besprochen
- Anna übernimmt UX-Design bis 20.7.
- Max kümmert sich um Backend-API bis 25.7.
- Budget: 15k genehmigt
- Offene Frage: Welches Chart-Framework?
- Nächstes Meeting: 10.7. 14 Uhr`;
  } else {
    ta.value = `Quartals-Review Q2 2025 — 3. Juni 2025
Teilnehmer: Dr. Meier (CEO), Sandra K. (CTO), Björn H. (Sales), Maria L. (Marketing), Dev-Team

AGENDA
1. Q2 Rückblick
2. Q3 Planung
3. Personalfragen
4. Sonstiges

Q2 RÜCKBLICK
- Umsatz 18% über Plan — sehr gut!
- Neue App-Version hatte Bugs in Woche 3, wurden schnell behoben
- 3 neue Großkunden gewonnen (Siemens, BMW, Bosch)
- Marketing-Kampagne lief gut, 40% mehr Leads

Q3 PLANUNG
- Neue Mobile App bis Ende August (Sandra verantwortlich)
- Sales-Team auf 8 Personen ausbauen bis Juli (Björn)
- Preise erhöhen wir ab 1. August um 10% (Meier hat entschieden)
- Neues CRM-System einführen (Maria koordiniert, Budget 25k)
- DSGVO-Audit muss bis September abgeschlossen sein (Legal)

OFFENE PUNKTE
- Wer übernimmt Kundenbetreuung für BMW?
- Serverkosten explodieren — Sandra soll Analyse bis 15.7. liefern
- Remote-Policy unklar für neue Mitarbeiter

ENTSCHEIDUNGEN
- Budgeterhöhung Marketing genehmigt (+30k Q3)
- Home-Office 3 Tage/Woche bleibt bestehen
- Azure statt AWS für nächstes Jahr evaluieren

Nächstes Meeting: 1. Oktober 2025, 10 Uhr, Raum Berlin`;
  }
  ta.dispatchEvent(new Event('input'));
}

/* ─── PROCESS ───────────────────────────────────────────────── */
async function processNotes() {
  const notes = document.getElementById('raw-notes').value.trim();
  if (!notes) {
    showError('Bitte gib zuerst Meeting-Notizen ein.');
    return;
  }

  const title    = document.getElementById('meeting-title').value.trim() || 'Meeting';
  const date     = document.getElementById('meeting-date').value;
  const parts    = document.getElementById('participants').value.trim();
  const lang     = document.getElementById('language').value;
  const url      = document.getElementById('ollama-url').value.trim() || 'http://localhost:11434';
  const model    = document.getElementById('ollama-model').value;

  localStorage.setItem('ollama_url', url);
  localStorage.setItem('ollama_model', model);

  hideError();
  showProgress();
  setStep(1);

  const btn = document.getElementById('process-btn');
  btn.disabled = true;
  btn.classList.add('btn-loading');

  try {
    setStep(2);
    setProgress(35);

    const resp = await fetch(`${API}/api/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        raw_notes:     notes,
        meeting_title: title,
        meeting_date:  formatDate(date),
        participants:  parts,
        ollama_model:  model,
        ollama_url:    url,
        language:      lang,
      }),
    });

    setProgress(70);
    setStep(3);

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unbekannter Fehler' }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    const data = await resp.json();
    setProgress(100);

    setTimeout(() => {
      hideProgress();
      lastResult = data;
      renderResult(data, title);
      document.getElementById('result-tab-btn').disabled = false;
      switchTab('result');
    }, 600);

  } catch (err) {
    hideProgress();
    showError(err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove('btn-loading');
  }
}

function formatDate(isoDate) {
  if (!isoDate) return new Date().toLocaleDateString('de-DE');
  const [y, m, d] = isoDate.split('-');
  return `${d}.${m}.${y}`;
}

/* ─── PROGRESS ──────────────────────────────────────────────── */
function showProgress() {
  document.getElementById('progress-container').style.display = 'block';
  setProgress(10);
}
function hideProgress() {
  document.getElementById('progress-container').style.display = 'none';
}
function setProgress(pct) {
  document.getElementById('progress-fill').style.width = `${pct}%`;
}
function setStep(n) {
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById(`step-${i}`);
    el.classList.remove('active', 'done');
    if (i < n)  el.classList.add('done');
    if (i === n) el.classList.add('active');
  }
}

/* ─── ERRORS ────────────────────────────────────────────────── */
function showError(msg) {
  const box = document.getElementById('error-box');
  document.getElementById('error-text').textContent = msg;
  box.style.display = 'flex';
}
function hideError() {
  document.getElementById('error-box').style.display = 'none';
}

/* ─── RENDER RESULT ─────────────────────────────────────────── */
function renderResult(data, title) {
  const s = data.structured;
  const lang = document.getElementById('language').value;
  const L = lang === 'de' ? {
    summary: 'Zusammenfassung', topics: 'Themen', decisions: 'Entscheidungen',
    actions: 'To-Dos', questions: 'Offene Fragen', next: 'Nächstes Meeting',
    task: 'Aufgabe', resp: 'Verantwortlich', deadline: 'Termin',
    noDecisions: 'Keine Entscheidungen', noActions: 'Keine To-Dos', noQuestions: 'Keine offenen Fragen',
  } : {
    summary: 'Summary', topics: 'Topics', decisions: 'Decisions',
    actions: 'Action Items', questions: 'Open Questions', next: 'Next Meeting',
    task: 'Task', resp: 'Responsible', deadline: 'Deadline',
    noDecisions: 'No decisions recorded', noActions: 'No action items', noQuestions: 'No open questions',
  };

  document.getElementById('result-filename').textContent = data.pdf_filename;
  document.getElementById('pdf-preview-btn').href  = data.pdf_url;
  document.getElementById('pdf-download-btn').href = data.pdf_url;
  document.getElementById('pdf-download-btn').download = data.pdf_filename;

  const grid = document.getElementById('result-content');
  grid.innerHTML = `
    ${card('full-width summary-card-result', 'accent', L.summary, `
      <p class="result-summary-text">${esc(s.summary || '–')}</p>
    `)}
    ${card('', 'blue', L.topics, s.key_topics?.length
      ? s.key_topics.map(t => `<span class="result-chip">${esc(t)}</span>`).join('')
      : '<p class="result-empty">–</p>',
      s.key_topics?.length
    )}
    ${card('', 'green', L.decisions,
      s.decisions?.length
        ? `<ul class="result-list">${s.decisions.map(d => `<li>${esc(d)}</li>`).join('')}</ul>`
        : `<p class="result-empty">${L.noDecisions}</p>`,
      s.decisions?.length
    )}
    ${card('full-width', 'orange', L.actions,
      s.action_items?.length
        ? `<table class="result-table">
            <thead><tr><th>${L.task}</th><th>${L.resp}</th><th>${L.deadline}</th></tr></thead>
            <tbody>${s.action_items.map(a =>
              `<tr>
                <td class="task-col">${esc(a.task)}</td>
                <td class="resp-col">${esc(a.responsible)}</td>
                <td><span class="result-deadline">${esc(a.deadline)}</span></td>
              </tr>`).join('')}</tbody>
          </table>`
        : `<p class="result-empty">${L.noActions}</p>`,
      s.action_items?.length
    )}
    ${s.open_questions?.length ? card('', 'purple', L.questions,
      `<ul class="result-list result-q-list">${s.open_questions.map(q => `<li>${esc(q)}</li>`).join('')}</ul>`,
      s.open_questions.length
    ) : ''}
    ${s.next_meeting ? card('', 'gray', L.next,
      `<div class="result-next">${esc(s.next_meeting)}</div>`
    ) : ''}
  `;
}

function card(extraClass, dotColor, title, content, count) {
  const countHtml = count != null ? `<span class="result-card-count">${count}</span>` : '';
  return `
    <div class="result-card ${extraClass}">
      <div class="result-card-header">
        <div class="result-card-dot" style="background:${dotColors[dotColor]}"></div>
        <span class="result-card-title">${title}</span>
        ${countHtml}
      </div>
      ${content}
    </div>`;
}

const dotColors = {
  accent: '#3b82f6', blue: '#60a5fa', green: '#10b981',
  orange: '#f59e0b', purple: '#8b5cf6', red: '#ef4444', gray: '#64748b',
};

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
