function renderSearch() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <h1 style="margin-bottom:1.5rem">Semantic Search</h1>
    <div class="search-bar">
      <input type="text" id="search-input" placeholder='e.g. "patients with diabetes medications" or "recurring headache"' />
      <button class="btn btn-primary" onclick="doSearch()">Search</button>
    </div>
    <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">
      Searches by meaning — not just keywords. Try symptoms, conditions, drugs, or plain descriptions.
    </p>
    <div id="search-results"></div>
  `;

  document.getElementById('search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') doSearch();
  });
}

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
