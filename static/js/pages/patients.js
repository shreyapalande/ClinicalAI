async function renderPatients() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem">
      <h1>Patients</h1>
      <button class="btn btn-primary" onclick="Router.go('record')">+ New Record</button>
    </div>
    <div id="patient-list"><div class="spinner"></div></div>
  `;

  try {
    const patients = await API.get('/api/patients/');
    const list = document.getElementById('patient-list');
    if (!patients.length) {
      list.innerHTML = `<div class="empty-state"><div class="icon">🏥</div><p>No patients yet. Start by recording a consultation.</p></div>`;
      return;
    }
    list.innerHTML = patients.map(p => `
      <div class="card" onclick="Router.go('patient', ${p.id})">
        <div style="display:flex;align-items:center;gap:1rem">
          <div class="patient-avatar">${(p.name || '?')[0].toUpperCase()}</div>
          <div>
            <strong>${p.name || 'Unknown'}</strong>
            <div class="patient-meta">
              <span style="color:var(--accent);font-size:0.78rem;font-weight:600">ID: ${p.id}</span>
              ${p.age ? ` · ${p.age} yrs` : ''}
              ${p.gender ? ` · ${p.gender}` : ''}
              ${p.blood_type ? ` · ${p.blood_type}` : ''}
            </div>
            <small>Added ${formatDate(p.created_at)}</small>
          </div>
        </div>
      </div>
    `).join('');
  } catch (e) {
    document.getElementById('patient-list').innerHTML = `<p style="color:var(--danger)">${e.message}</p>`;
  }
}
