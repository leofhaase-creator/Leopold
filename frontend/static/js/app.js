/* ─── STATE ─────────────────────────────────────────────────── */
let currentProvider = 'groq';

/* ─── INIT ──────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('meeting-date').value = new Date().toISOString().split('T')[0];

  const notesTA = document.getElementById('raw-notes');
  notesTA.addEventListener('input', () => {
    document.getElementById('char-count').textContent = notesTA.value.length.toLocaleString('de') + ' Zeichen';
  });

  // Restore saved settings
  const saved = loadSettings();
  currentProvider = saved.provider || 'groq';
  selectProvider(currentProvider, false);
  if (saved.groqKey)       document.getElementById('groq-key').value       = saved.groqKey;
  if (saved.anthropicKey)  document.getElementById('anthropic-key').value  = saved.anthropicKey;
  if (saved.openaiKey)     document.getElementById('openai-key').value     = saved.openaiKey;
  if (saved.groqModel)     document.getElementById('groq-model').value     = saved.groqModel;
  if (saved.anthropicModel)document.getElementById('anthropic-model').value= saved.anthropicModel;
  if (saved.openaiModel)   document.getElementById('openai-model').value   = saved.openaiModel;
  if (saved.ollamaUrl)     document.getElementById('ollama-url').value     = saved.ollamaUrl;
  if (saved.ollamaModel)   document.getElementById('ollama-model').value   = saved.ollamaModel;

  setTimeout(autoCheckStatus, 500);
});

/* ─── TAB NAVIGATION ────────────────────────────────────────── */
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => { if (!btn.disabled) switchTab(btn.dataset.tab); });
});

function switchTab(tab) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.querySelector(`.nav-item[data-tab="${tab}"]`).classList.add('active');
}

/* ─── PROVIDER SELECTION ────────────────────────────────────── */
function selectProvider(p, save = true) {
  currentProvider = p;
  document.querySelectorAll('.provider-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.provider === p);
  });
  ['groq','anthropic','openai','ollama'].forEach(name => {
    document.getElementById(`config-${name}`).style.display = name === p ? 'block' : 'none';
  });
  if (save) saveSettings();
  updateStatusUI('checking', 'Wird geprüft…');
}

/* ─── STATUS UI ─────────────────────────────────────────────── */
function updateStatusUI(state, text) {
  const dot1 = document.querySelector('#ai-status .status-dot');
  const dot2 = document.querySelector('#ai-inline .status-dot');
  const span1 = document.querySelector('#ai-status span');
  const span2 = document.getElementById('ai-inline-text');
  [dot1, dot2].forEach(d => { if(d) { d.className = 'status-dot'; d.classList.add(state); } });
  if (span1) span1.textContent = text;
  if (span2) span2.textContent = text;
}

async function autoCheckStatus() {
  const key = getApiKey();
  if (currentProvider !== 'ollama' && !key) {
    updateStatusUI('offline', 'Kein API-Key — Einstellungen öffnen');
    return;
  }
  updateStatusUI('checking', 'Prüfe Verbindung…');
  const result = await doCheck();
  if (result.status === 'online') {
    updateStatusUI('online', providerLabel() + ' bereit ✓');
  } else if (result.status === 'no_key') {
    updateStatusUI('offline', 'API-Key fehlt');
  } else if (result.status === 'invalid_key') {
    updateStatusUI('offline', 'API-Key ungültig');
  } else {
    updateStatusUI('offline', providerLabel() + ' nicht erreichbar');
  }
}

async function testConnection() {
  saveSettings();
  const statusBoxId = `${currentProvider}-status`;
  const box = document.getElementById(statusBoxId);
  const dot = box.querySelector('.status-dot');
  const span = box.querySelector('span');
  box.style.display = 'flex';
  dot.className = 'status-dot checking';
  span.textContent = 'Wird geprüft…';

  const result = await doCheck();
  const msgs = {
    'online':      ['online',  providerLabel() + ' verbunden ✓'],
    'no_key':      ['offline', 'Bitte API-Key eingeben'],
    'invalid_key': ['offline', 'API-Key ungültig'],
    'offline':     ['offline', 'Nicht erreichbar'],
  };
  const [state, text] = msgs[result.status] || ['offline', 'Unbekannter Fehler'];
  dot.className = 'status-dot ' + state;
  span.textContent = text;
  updateStatusUI(state, text);

  if (result.models?.length && currentProvider === 'ollama') {
    const sel = document.getElementById('ollama-model');
    result.models.forEach(m => {
      const short = m.split(':')[0];
      if (![...sel.options].find(o => o.value === short)) {
        const opt = document.createElement('option');
        opt.value = short; opt.textContent = short;
        sel.appendChild(opt);
      }
    });
  }
}

async function doCheck() {
  try {
    const body = {
      provider: currentProvider,
      api_key: getApiKey(),
      ollama_url: document.getElementById('ollama-url')?.value || 'http://localhost:11434',
    };
    const resp = await fetch('/api/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return await resp.json();
  } catch { return { status: 'offline' }; }
}

function getApiKey() {
  const map = { groq: 'groq-key', anthropic: 'anthropic-key', openai: 'openai-key' };
  const id = map[currentProvider];
  return id ? (document.getElementById(id)?.value || '') : '';
}

function getModel() {
  const map = { groq: 'groq-model', anthropic: 'anthropic-model', openai: 'openai-model', ollama: 'ollama-model' };
  return document.getElementById(map[currentProvider])?.value || '';
}

function providerLabel() {
  const m = { groq: 'Groq', anthropic: 'Anthropic', openai: 'OpenAI', ollama: 'Ollama' };
  return m[currentProvider] || currentProvider;
}

/* ─── SETTINGS PERSISTENCE ──────────────────────────────────── */
function saveSettings() {
  localStorage.setItem('mnp_settings', JSON.stringify({
    provider:      currentProvider,
    groqKey:       document.getElementById('groq-key')?.value || '',
    anthropicKey:  document.getElementById('anthropic-key')?.value || '',
    openaiKey:     document.getElementById('openai-key')?.value || '',
    groqModel:     document.getElementById('groq-model')?.value || '',
    anthropicModel:document.getElementById('anthropic-model')?.value || '',
    openaiModel:   document.getElementById('openai-model')?.value || '',
    ollamaUrl:     document.getElementById('ollama-url')?.value || '',
    ollamaModel:   document.getElementById('ollama-model')?.value || '',
  }));
}

function loadSettings() {
  try { return JSON.parse(localStorage.getItem('mnp_settings') || '{}'); }
  catch { return {}; }
}

/* ─── TEMPLATES ─────────────────────────────────────────────── */
function loadTemplate(type) {
  const ta = document.getElementById('raw-notes');
  if (type === 'short') {
    ta.value = `Kick-off Produktteam\n- Anwesend: Anna, Max, Lisa, Tom\n- Neues Dashboard-Feature besprochen\n- Anna übernimmt UX-Design bis 20.7.\n- Max kümmert sich um Backend-API bis 25.7.\n- Budget: 15k genehmigt\n- Offene Frage: Welches Chart-Framework?\n- Nächstes Meeting: 10.7. 14 Uhr`;
  } else {
    ta.value = `Quartals-Review Q2 2025 — 3. Juni 2025\nTeilnehmer: Dr. Meier (CEO), Sandra K. (CTO), Björn H. (Sales), Maria L. (Marketing)\n\nQ2 RÜCKBLICK\n- Umsatz 18% über Plan\n- Neue App-Version hatte Bugs in Woche 3, wurden behoben\n- 3 neue Großkunden: Siemens, BMW, Bosch\n- Marketing-Kampagne: 40% mehr Leads\n\nQ3 PLANUNG\n- Neue Mobile App bis Ende August (Sandra)\n- Sales-Team auf 8 Personen ausbauen (Björn, bis Juli)\n- Preiserhöhung 10% ab 1. August (Meier entschieden)\n- Neues CRM einführen (Maria, Budget 25k)\n- DSGVO-Audit bis September (Legal)\n\nOFFENE PUNKTE\n- Wer übernimmt Betreuung für BMW?\n- Serverkosten explodieren — Sandra liefert Analyse bis 15.7.\n\nENTSCHEIDUNGEN\n- Budgeterhöhung Marketing genehmigt (+30k Q3)\n- Home-Office 3 Tage/Woche bleibt\n- Azure statt AWS evaluieren\n\nNächstes Meeting: 1. Oktober 2025, 10 Uhr`;
  }
  ta.dispatchEvent(new Event('input'));
}

/* ─── PROCESS ───────────────────────────────────────────────── */
async function processNotes() {
  const notes = document.getElementById('raw-notes').value.trim();
  if (!notes) { showError('Bitte gib zuerst Meeting-Notizen ein.'); return; }

  const apiKey = getApiKey();
  if (currentProvider !== 'ollama' && !apiKey) {
    showError('Bitte trage zuerst deinen API-Key in den Einstellungen ein.');
    return;
  }

  saveSettings();
  hideError();
  showProgress();
  setStep(1);

  const btn = document.getElementById('process-btn');
  btn.disabled = true;
  btn.classList.add('btn-loading');

  try {
    setStep(2); setProgress(35);

    const body = {
      raw_notes:     notes,
      meeting_title: document.getElementById('meeting-title').value.trim() || 'Meeting',
      meeting_date:  formatDate(document.getElementById('meeting-date').value),
      participants:  document.getElementById('participants').value.trim(),
      language:      document.getElementById('language').value,
      provider:      currentProvider,
      api_key:       apiKey,
      api_model:     getModel(),
      ollama_url:    document.getElementById('ollama-url')?.value || 'http://localhost:11434',
      ollama_model:  document.getElementById('ollama-model')?.value || 'llama3',
    };

    const resp = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    setProgress(70); setStep(3);

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unbekannter Fehler' }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    const data = await resp.json();
    setProgress(100);

    setTimeout(() => {
      hideProgress();
      renderResult(data);
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

function formatDate(iso) {
  if (!iso) return new Date().toLocaleDateString('de-DE');
  const [y,m,d] = iso.split('-');
  return `${d}.${m}.${y}`;
}

/* ─── PROGRESS ──────────────────────────────────────────────── */
function showProgress() { document.getElementById('progress-container').style.display = 'block'; setProgress(10); }
function hideProgress() { document.getElementById('progress-container').style.display = 'none'; }
function setProgress(p) { document.getElementById('progress-fill').style.width = `${p}%`; }
function setStep(n) {
  for (let i=1;i<=3;i++) {
    const el = document.getElementById(`step-${i}`);
    el.classList.remove('active','done');
    if (i<n)  el.classList.add('done');
    if (i===n) el.classList.add('active');
  }
}

/* ─── ERRORS ────────────────────────────────────────────────── */
function showError(msg) {
  document.getElementById('error-text').textContent = msg;
  document.getElementById('error-box').style.display = 'flex';
}
function hideError() { document.getElementById('error-box').style.display = 'none'; }

/* ─── RENDER RESULT ─────────────────────────────────────────── */
function renderResult(data) {
  const s = data.structured;
  const lang = document.getElementById('language').value;
  const L = lang === 'de' ? {
    summary:'Zusammenfassung', topics:'Themen', decisions:'Entscheidungen',
    actions:'To-Dos', questions:'Offene Fragen', next:'Nächstes Meeting',
    task:'Aufgabe', resp:'Verantwortlich', deadline:'Termin',
    noDecisions:'Keine Entscheidungen', noActions:'Keine To-Dos',
  } : {
    summary:'Summary', topics:'Topics', decisions:'Decisions',
    actions:'Action Items', questions:'Open Questions', next:'Next Meeting',
    task:'Task', resp:'Responsible', deadline:'Deadline',
    noDecisions:'No decisions recorded', noActions:'No action items',
  };

  document.getElementById('result-filename').textContent = data.pdf_filename;
  document.getElementById('pdf-preview-btn').href  = data.pdf_url;
  document.getElementById('pdf-download-btn').href = data.pdf_url;
  document.getElementById('pdf-download-btn').download = data.pdf_filename;

  document.getElementById('result-content').innerHTML = `
    ${card('full-width summary-card-result','accent',L.summary,`<p class="result-summary-text">${esc(s.summary||'–')}</p>`)}
    ${card('','blue',L.topics, s.key_topics?.length ? s.key_topics.map(t=>`<span class="result-chip">${esc(t)}</span>`).join('') : '<p class="result-empty">–</p>', s.key_topics?.length)}
    ${card('','green',L.decisions,
      s.decisions?.length
        ? `<ul class="result-list">${s.decisions.map(d=>`<li>${esc(d)}</li>`).join('')}</ul>`
        : `<p class="result-empty">${L.noDecisions}</p>`,
      s.decisions?.length
    )}
    ${card('full-width','orange',L.actions,
      s.action_items?.length
        ? `<table class="result-table"><thead><tr><th>${L.task}</th><th>${L.resp}</th><th>${L.deadline}</th></tr></thead><tbody>${
            s.action_items.map(a=>`<tr><td class="task-col">${esc(a.task)}</td><td class="resp-col">${esc(a.responsible)}</td><td><span class="result-deadline">${esc(a.deadline)}</span></td></tr>`).join('')
          }</tbody></table>`
        : `<p class="result-empty">${L.noActions}</p>`,
      s.action_items?.length
    )}
    ${s.open_questions?.length ? card('','purple',L.questions,
      `<ul class="result-list result-q-list">${s.open_questions.map(q=>`<li>${esc(q)}</li>`).join('')}</ul>`,
      s.open_questions.length) : ''}
    ${s.next_meeting ? card('','gray',L.next,`<div class="result-next">${esc(s.next_meeting)}</div>`) : ''}
  `;
}

function card(extra, dot, title, content, count) {
  return `<div class="result-card ${extra}">
    <div class="result-card-header">
      <div class="result-card-dot" style="background:${{accent:'#3b82f6',blue:'#60a5fa',green:'#10b981',orange:'#f59e0b',purple:'#8b5cf6',gray:'#64748b'}[dot]}"></div>
      <span class="result-card-title">${title}</span>
      ${count!=null?`<span class="result-card-count">${count}</span>`:''}
    </div>${content}</div>`;
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
