async function renderPatientDetail(id) {
  const app = document.getElementById('app');
  app.innerHTML = `
    <a href="#" onclick="Router.go('patients');return false" style="color:var(--text-muted);font-size:0.85rem">← Back to patients</a>
    <div id="detail-content" style="margin-top:1.2rem"><div class="spinner"></div></div>
  `;

  try {
    const p = await API.get(`/api/patients/${id}`);
    const initials = (p.name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

    document.getElementById('detail-content').innerHTML = `
      <div class="patient-header">
        <div class="patient-avatar">${initials}</div>
        <div>
          <h1>${p.name || 'Unknown'}</h1>
          <div class="patient-meta">
            ${p.age ? `${p.age} yrs` : ''}
            ${p.gender ? ` · ${p.gender}` : ''}
            ${p.blood_type ? ` · Blood: ${p.blood_type}` : ''}
            ${p.contact ? ` · ${p.contact}` : ''}
          </div>
          ${p.allergies && p.allergies.length ? `<div style="margin-top:0.4rem">${p.allergies.map(a => `<span class="tag tag-allergy">${a}</span>`).join('')}</div>` : ''}
        </div>
        <button class="btn btn-ghost btn-sm" style="margin-left:auto" onclick="editPatient(${p.id})">Edit</button>
      </div>

      <h2>Visit Timeline</h2>
      ${p.visits && p.visits.length ? `
        <div class="timeline">
          ${p.visits.map(v => renderVisitCard(v)).join('')}
        </div>
      ` : `<div class="empty-state"><p>No visits recorded.</p></div>`}
    `;
  } catch (e) {
    document.getElementById('detail-content').innerHTML = `<p style="color:var(--danger)">${e.message}</p>`;
  }
}

function renderVisitCard(v) {
  const rx = v.prescriptions && v.prescriptions.length
    ? v.prescriptions.map(p => `<span class="tag tag-drug">${p.drug || p}</span>`).join('')
    : '—';

  return `
    <div class="timeline-item">
      <div class="card" style="cursor:default">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <strong>${v.chief_complaint || 'No complaint recorded'}</strong>
            <div><small>${formatDate(v.created_at)}</small></div>
          </div>
          <button class="btn btn-ghost btn-sm" onclick="showVisitEdit(${v.id}, ${v.patient_id})">Edit</button>
        </div>
        <hr />
        <div class="grid-2">
          <div>
            <h3>Symptoms</h3>
            ${renderTags(v.symptoms, 'tag-symptom')}
          </div>
          <div>
            <h3>Diagnoses</h3>
            ${renderTags(v.diagnoses, 'tag-diagnosis')}
          </div>
        </div>
        <div style="margin-top:1rem">
          <h3>Prescriptions</h3>
          ${rx}
        </div>
        ${v.notes ? `<div style="margin-top:1rem"><h3>Notes</h3><p>${v.notes}</p></div>` : ''}
        ${v.follow_up ? `<div style="margin-top:0.6rem"><small>Follow-up: ${v.follow_up}</small></div>` : ''}
        ${v.transcript ? `
          <details style="margin-top:1rem">
            <summary style="cursor:pointer;color:var(--text-muted);font-size:0.82rem">Show transcript</summary>
            <p style="margin-top:0.6rem;font-size:0.85rem;color:var(--text-muted)">${v.transcript}</p>
          </details>` : ''}
      </div>
    </div>
  `;
}

function editPatient(id) {
  toast('Patient editing coming soon', 'info');
}

async function showVisitEdit(visitId, patientId) {
  toast('Visit editing coming soon', 'info');
}
