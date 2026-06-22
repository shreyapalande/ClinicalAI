// ── SEARCH PAGE ──────────────────────────────────────────────────────────────

// Persist last query + rendered results so the back button can restore them
const _searchState = { query: '', resultsHTML: '' };

function renderSearch(restoreState = false) {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div style="margin-bottom:1.5rem">
      <h1 style="margin:0 0 0.4rem">Search</h1>
      <p style="color:var(--text-muted);font-size:0.88rem;margin:0">
        Ask anything in plain English — the agent combines filters, semantic search, and patient records to answer.
      </p>
    </div>

    <div class="search-bar">
      <div class="search-input-wrap">
        <span class="search-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </span>
        <input type="text" id="agent-input"
               placeholder='e.g. "patients with diabetes and hypertension" or "who needs renal monitoring?"' />
      </div>
      <button class="btn btn-primary" onclick="doAgentQuery()">Ask</button>
    </div>

    <div id="agent-results"></div>
  `;

  const input = document.getElementById('agent-input');
  input.addEventListener('keydown', e => { if (e.key === 'Enter') doAgentQuery(); });

  if (restoreState && _searchState.query) {
    input.value = _searchState.query;
    document.getElementById('agent-results').innerHTML = _searchState.resultsHTML;
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
    _searchState.query = q;
    _searchState.resultsHTML = document.getElementById('agent-results').innerHTML;
  } catch (e) {
    resultsEl.innerHTML = `<p style="color:var(--danger)">${e.message}</p>`;
  }
}

function _mdToHtml(md) {
  // Split into blocks on blank lines
  const blocks = md.trim().split(/\n{2,}/);
  return blocks.map(block => {
    const lines = block.split('\n');
    // Detect bullet list block (lines starting with * or -)
    if (lines.every(l => /^\s*[\*\-]\s+/.test(l) || l.trim() === '')) {
      const items = lines
        .filter(l => /^\s*[\*\-]\s+/.test(l))
        .map(l => `<li>${_inlineMd(l.replace(/^\s*[\*\-]\s+/, ''))}</li>`)
        .join('');
      return `<ul>${items}</ul>`;
    }
    // Detect numbered list block
    if (lines.every(l => /^\s*\d+\.\s+/.test(l) || l.trim() === '')) {
      const items = lines
        .filter(l => /^\s*\d+\.\s+/.test(l))
        .map(l => `<li>${_inlineMd(l.replace(/^\s*\d+\.\s+/, ''))}</li>`)
        .join('');
      return `<ol>${items}</ol>`;
    }
    // Plain paragraph — join lines with a space
    return `<p>${_inlineMd(lines.join(' '))}</p>`;
  }).join('');
}

function _inlineMd(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')  // **bold**
    .replace(/\*(.+?)\*/g, '<em>$1</em>');              // *italic*
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
      <div class="agent-answer-text">${_mdToHtml(answer)}</div>
    </div>
    ${patients.length ? `
      <h3 style="margin:1.5rem 0 0.8rem;color:var(--text-muted);font-size:0.8rem;text-transform:uppercase;letter-spacing:0.8px">
        Matched Patients (${patients.length})
      </h3>
      ${patientCards}` : ''}
  `;
}
