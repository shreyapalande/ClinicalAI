// ── SEARCH PAGE ──────────────────────────────────────────────────────────────

let _searchMode = 'semantic'; // 'semantic' | 'agent'

function renderSearch() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap">
      <h1 style="margin:0">Search</h1>
      <div class="mode-tabs">
        <button id="tab-semantic" class="mode-tab ${_searchMode === 'semantic' ? 'active' : ''}"
                onclick="switchMode('semantic')">Semantic</button>
        <button id="tab-agent" class="mode-tab ${_searchMode === 'agent' ? 'active' : ''}"
                onclick="switchMode('agent')">AI Agent</button>
      </div>
    </div>

    <div id="semantic-panel" style="display:${_searchMode === 'semantic' ? 'block' : 'none'}">
      <div class="search-bar">
        <div class="search-input-wrap">
          <span class="search-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </span>
          <input type="text" id="search-input"
                 placeholder='e.g. "patients with diabetes" or "recurring headache"' />
        </div>
        <button class="btn btn-primary" onclick="doSearch()">Search</button>
      </div>
      <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">
        Searches by meaning — not just keywords. Try symptoms, conditions, drugs, or plain descriptions.
      </p>
      <div id="search-results"></div>
    </div>

    <div id="agent-panel" style="display:${_searchMode === 'agent' ? 'block' : 'none'}">
      <div class="search-bar">
        <div class="search-input-wrap">
          <span class="search-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
            </svg>
          </span>
          <input type="text" id="agent-input"
                 placeholder='e.g. "adult patients with hypertension prescribed beta-blockers"' />
        </div>
        <button class="btn btn-primary" onclick="doAgentQuery()">Ask Agent</button>
      </div>
      <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">
        Ask complex questions in plain English. The agent combines filters, semantic search, and patient records to answer.
      </p>
      <div id="agent-results"></div>
    </div>
  `;

  document.getElementById('search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') doSearch();
  });
  document.getElementById('agent-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') doAgentQuery();
  });
}

function switchMode(mode) {
  _searchMode = mode;
  document.getElementById('tab-semantic').classList.toggle('active', mode === 'semantic');
  document.getElementById('tab-agent').classList.toggle('active', mode === 'agent');
  document.getElementById('semantic-panel').style.display = mode === 'semantic' ? 'block' : 'none';
  document.getElementById('agent-panel').style.display = mode === 'agent' ? 'block' : 'none';
}

// ── SEMANTIC SEARCH ──────────────────────────────────────────────────────────

async function doSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;

  const results = document.getElementById('search-results');
  results.innerHTML = '<div class="spinner"></div>';

  try {
    const data = await API.get(`/api/search/?q=${encodeURIComponent(q)}`);
    if (!data.results.length) {
      results.innerHTML = `<div class="empty-state"><div class="icon">🔍</div><p>No matching records found.</p></div>`;
      return;
    }
    results.innerHTML = data.results.map(r => `
      <div class="card" onclick="Router.go('patient', ${r.patient_id})" style="cursor:pointer">
        <div style="display:flex;align-items:flex-start;justify-content:space-between">
          <div>
            <strong>${r.patient_name}</strong>
            <div style="color:var(--text-muted);font-size:0.82rem;margin-top:0.2rem">${formatDate(r.created_at)}</div>
          </div>
          <span class="result-score">${(r.score * 100).toFixed(1)}% match</span>
        </div>
        <hr />
        <p style="font-size:0.9rem">${r.chief_complaint || '—'}</p>
        <div style="margin-top:0.6rem">
          ${renderTags(r.symptoms, 'tag-symptom')}
          ${renderTags(r.diagnoses, 'tag-diagnosis')}
          ${r.prescriptions ? r.prescriptions.map(p => `<span class="tag tag-drug">${p.drug || p}</span>`).join('') : ''}
        </div>
      </div>
    `).join('');
  } catch (e) {
    results.innerHTML = `<p style="color:var(--danger)">${e.message}</p>`;
  }
}

// ── AI AGENT ─────────────────────────────────────────────────────────────────

async function doAgentQuery() {
  const q = document.getElementById('agent-input').value.trim();
  if (!q) return;

  const resultsEl = document.getElementById('agent-results');
  resultsEl.innerHTML = `
    <div style="display:flex;align-items:center;gap:0.8rem;padding:1.2rem 0;color:var(--text-muted)">
      <div class="spinner" style="width:1.2rem;height:1.2rem;border-width:2px"></div>
      <span>Agent is querying your patient database…</span>
    </div>`;

  try {
    const data = await API.post('/api/agent/query', { query: q });
    _renderAgentResults(data);
  } catch (e) {
    resultsEl.innerHTML = `<p style="color:var(--danger)">${e.message}</p>`;
  }
}

function _renderAgentResults({ answer, patients }) {
  const resultsEl = document.getElementById('agent-results');

  const patientCards = patients.length
    ? patients.map(p => {
        const initials = (p.name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
        const latestVisit = p.visits && p.visits.length ? p.visits[0] : null;
        return `
          <div class="card" onclick="Router.go('patient', ${p.id})" style="cursor:pointer">
            <div style="display:flex;align-items:center;gap:0.8rem">
              <div class="patient-avatar" style="width:2.4rem;height:2.4rem;font-size:0.85rem;flex-shrink:0">${initials}</div>
              <div style="flex:1;min-width:0">
                <div style="display:flex;align-items:baseline;gap:0.6rem">
                  <strong>${p.name}</strong>
                  <span style="color:var(--accent);font-size:0.75rem;font-weight:600">ID: ${p.id}</span>
                  ${p.age ? `<span style="color:var(--text-muted);font-size:0.82rem">${p.age} yrs</span>` : ''}
                  ${p.gender ? `<span style="color:var(--text-muted);font-size:0.82rem">· ${p.gender}</span>` : ''}
                </div>
                ${p.allergies && p.allergies.length
                  ? `<div style="margin-top:0.3rem">${p.allergies.map(a => `<span class="tag tag-allergy">${a}</span>`).join('')}</div>`
                  : ''}
                ${latestVisit ? `
                  <div style="margin-top:0.4rem;font-size:0.85rem;color:var(--text-muted)">
                    Latest: <em>${latestVisit.chief_complaint || 'No complaint'}</em>
                    · ${formatDate(latestVisit.created_at)}
                  </div>` : ''}
              </div>
              <div style="text-align:right;flex-shrink:0">
                <div style="font-size:0.78rem;color:var(--text-muted)">${p.visits ? p.visits.length : 0} visit${p.visits && p.visits.length !== 1 ? 's' : ''}</div>
              </div>
            </div>
          </div>`;
      }).join('')
    : '';

  resultsEl.innerHTML = `
    <div class="agent-answer">
      <div class="agent-answer-label">Agent</div>
      <div class="agent-answer-text">${answer.replace(/\n/g, '<br>')}</div>
    </div>
    ${patients.length ? `
      <h3 style="margin:1.5rem 0 0.8rem;color:var(--text-muted);font-size:0.8rem;text-transform:uppercase;letter-spacing:0.8px">
        Matched Patients (${patients.length})
      </h3>
      ${patientCards}` : ''}
  `;
}
