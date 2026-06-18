async function renderPatientDetail(id) {
  const app = document.getElementById('app');
  app.innerHTML = `
    <a href="#" onclick="Router.go('patients');return false" style="color:var(--text-muted);font-size:0.85rem">← Back to patients</a>
    <div id="detail-content" style="margin-top:1.2rem"><div class="spinner"></div></div>
  `;

  try {
    const p = await API.get(`/api/patients/${id}`);
    _renderDetail(p);
  } catch (e) {
    document.getElementById('detail-content').innerHTML = `<p style="color:var(--danger)">${e.message}</p>`;
  }
}

function _renderDetail(p) {
  const initials = (p.name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  document.getElementById('detail-content').innerHTML = `
    <div class="patient-header">
      <div class="patient-avatar">${initials}</div>
      <div>
        <h1>${p.name || 'Unknown'}</h1>
        <div class="patient-meta">
          <span style="color:var(--accent);font-size:0.78rem;font-weight:600;letter-spacing:0.5px">ID: ${p.id}</span>
          ${p.age ? ` · ${p.age} yrs` : ''}
          ${p.gender ? ` · ${p.gender}` : ''}
          ${p.blood_type ? ` · Blood: ${p.blood_type}` : ''}
          ${p.contact ? ` · ${p.contact}` : ''}
        </div>
        ${p.allergies && p.allergies.length
          ? `<div style="margin-top:0.4rem">${p.allergies.map(a => `<span class="tag tag-allergy">${a}</span>`).join('')}</div>`
          : ''}
      </div>
      <div style="margin-left:auto;display:flex;gap:0.5rem">
        <button class="btn btn-ghost btn-sm" onclick="editPatient(${p.id})">Edit Patient</button>
        <button class="btn btn-primary btn-sm" onclick="Router.go('record')">+ New Visit</button>
      </div>
    </div>

    <h2>Visit Timeline</h2>
    ${p.visits && p.visits.length
      ? `<div class="timeline">${p.visits.map(v => renderVisitCard(v)).join('')}</div>`
      : `<div class="empty-state"><p>No visits recorded yet.</p></div>`}
  `;
}

function renderVisitCard(v) {
  const rx = v.prescriptions && v.prescriptions.length
    ? v.prescriptions.map(p => `<span class="tag tag-drug">${p.drug || p}${p.dose ? ' ' + p.dose : ''}</span>`).join('')
    : '—';

  return `
    <div class="timeline-item">
      <div class="card" style="cursor:default">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <strong>${v.chief_complaint || 'No complaint recorded'}</strong>
            <div><small>${formatDate(v.created_at)}</small></div>
          </div>
          <button class="btn btn-ghost btn-sm" onclick="showVisitEdit(${v.id}, ${v.patient_id})">Edit Visit</button>
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
        ${v.vitals && Object.values(v.vitals).some(Boolean) ? `
          <div style="margin-top:1rem">
            <h3>Vitals</h3>
            <div style="font-size:0.85rem;color:var(--text-muted);display:flex;gap:1rem;flex-wrap:wrap">
              ${v.vitals.bp ? `<span>BP: ${v.vitals.bp}</span>` : ''}
              ${v.vitals.hr ? `<span>HR: ${v.vitals.hr}</span>` : ''}
              ${v.vitals.temp ? `<span>Temp: ${v.vitals.temp}</span>` : ''}
              ${v.vitals.weight ? `<span>Wt: ${v.vitals.weight}</span>` : ''}
              ${v.vitals.height ? `<span>Ht: ${v.vitals.height}</span>` : ''}
            </div>
          </div>` : ''}
        ${v.notes ? `<div style="margin-top:1rem"><h3>Notes</h3><p>${v.notes}</p></div>` : ''}
        ${v.follow_up ? `<p style="margin-top:0.6rem"><small>Follow-up: ${v.follow_up}</small></p>` : ''}
        ${v.transcript ? `
          <details style="margin-top:1rem">
            <summary style="cursor:pointer;color:var(--text-muted);font-size:0.82rem">Show transcript</summary>
            <p style="margin-top:0.6rem;font-size:0.85rem;color:var(--text-muted);white-space:pre-wrap">${v.transcript}</p>
          </details>` : ''}
      </div>
    </div>
  `;
}

// ── PATIENT EDIT ────────────────────────────────────────────────────────────

async function editPatient(id) {
  const p = await API.get(`/api/patients/${id}`);

  openModal(`
    <div class="modal-header">
      <h2>Edit Patient</h2>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-group">
      <label>Full Name</label>
      <input id="ep-name" type="text" value="${p.name || ''}" />
    </div>
    <div class="grid-2">
      <div class="form-group">
        <label>Age</label>
        <input id="ep-age" type="number" value="${p.age || ''}" />
      </div>
      <div class="form-group">
        <label>Gender</label>
        <select id="ep-gender">
          <option value="">—</option>
          <option value="Male" ${p.gender === 'Male' ? 'selected' : ''}>Male</option>
          <option value="Female" ${p.gender === 'Female' ? 'selected' : ''}>Female</option>
          <option value="Other" ${p.gender === 'Other' ? 'selected' : ''}>Other</option>
        </select>
      </div>
    </div>
    <div class="grid-2">
      <div class="form-group">
        <label>Contact</label>
        <input id="ep-contact" type="text" value="${p.contact || ''}" />
      </div>
      <div class="form-group">
        <label>Blood Type</label>
        <input id="ep-blood" type="text" value="${p.blood_type || ''}" placeholder="e.g. A+" />
      </div>
    </div>
    <div class="form-group">
      <label>Allergies <small>(comma-separated)</small></label>
      <input id="ep-allergies" type="text" value="${(p.allergies || []).join(', ')}" placeholder="Penicillin, Sulfa…" />
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="savePatient(${id})">Save Changes</button>
    </div>
  `);
}

async function savePatient(id) {
  const allergies = document.getElementById('ep-allergies').value
    .split(',').map(s => s.trim()).filter(Boolean);

  const data = {
    name: document.getElementById('ep-name').value.trim() || undefined,
    age: document.getElementById('ep-age').value ? parseInt(document.getElementById('ep-age').value) : undefined,
    gender: document.getElementById('ep-gender').value || undefined,
    contact: document.getElementById('ep-contact').value.trim() || undefined,
    blood_type: document.getElementById('ep-blood').value.trim() || undefined,
    allergies,
  };

  try {
    await API.patch(`/api/patients/${id}`, data);
    closeModal();
    toast('Patient updated', 'success');
    const p = await API.get(`/api/patients/${id}`);
    _renderDetail(p);
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ── VISIT EDIT ───────────────────────────────────────────────────────────────

async function showVisitEdit(visitId, patientId) {
  const p = await API.get(`/api/patients/${patientId}`);
  const v = p.visits.find(x => x.id === visitId);
  if (!v) { toast('Visit not found', 'error'); return; }

  const rxText = (v.prescriptions || [])
    .map(r => `${r.drug || ''}|${r.dose || ''}|${r.frequency || ''}|${r.duration || ''}`)
    .join('\n');

  openModal(`
    <div class="modal-header">
      <h2>Edit Visit</h2>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="form-group">
      <label>Chief Complaint</label>
      <input id="ev-complaint" type="text" value="${v.chief_complaint || ''}" />
    </div>
    <div class="form-group">
      <label>Symptoms <small>(comma-separated)</small></label>
      <input id="ev-symptoms" type="text" value="${(v.symptoms || []).join(', ')}" />
    </div>
    <div class="form-group">
      <label>Diagnoses <small>(comma-separated)</small></label>
      <input id="ev-diagnoses" type="text" value="${(v.diagnoses || []).join(', ')}" />
    </div>
    <div class="form-group">
      <label>Prescriptions <small>(one per line: drug | dose | frequency | duration)</small></label>
      <textarea id="ev-rx" rows="4" placeholder="Amoxicillin|500mg|3x daily|7 days">${rxText}</textarea>
    </div>
    <div class="grid-2">
      <div class="form-group">
        <label>BP</label>
        <input id="ev-bp" type="text" value="${v.vitals?.bp || ''}" placeholder="120/80" />
      </div>
      <div class="form-group">
        <label>Heart Rate</label>
        <input id="ev-hr" type="text" value="${v.vitals?.hr || ''}" placeholder="72 bpm" />
      </div>
    </div>
    <div class="grid-2">
      <div class="form-group">
        <label>Temperature</label>
        <input id="ev-temp" type="text" value="${v.vitals?.temp || ''}" placeholder="98.6°F" />
      </div>
      <div class="form-group">
        <label>Weight</label>
        <input id="ev-weight" type="text" value="${v.vitals?.weight || ''}" placeholder="70 kg" />
      </div>
    </div>
    <div class="form-group">
      <label>Notes</label>
      <textarea id="ev-notes" rows="3">${v.notes || ''}</textarea>
    </div>
    <div class="form-group">
      <label>Follow-up</label>
      <input id="ev-followup" type="text" value="${v.follow_up || ''}" placeholder="2 weeks" />
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveVisit(${patientId}, ${visitId})">Save Changes</button>
    </div>
  `);
}

async function saveVisit(patientId, visitId) {
  const prescriptions = document.getElementById('ev-rx').value
    .split('\n').map(line => {
      const [drug, dose, frequency, duration] = line.split('|').map(s => s.trim());
      return drug ? { drug, dose: dose || '', frequency: frequency || '', duration: duration || '' } : null;
    }).filter(Boolean);

  const data = {
    chief_complaint: document.getElementById('ev-complaint').value.trim(),
    symptoms: document.getElementById('ev-symptoms').value.split(',').map(s => s.trim()).filter(Boolean),
    diagnoses: document.getElementById('ev-diagnoses').value.split(',').map(s => s.trim()).filter(Boolean),
    prescriptions,
    vitals: {
      bp: document.getElementById('ev-bp').value.trim() || null,
      hr: document.getElementById('ev-hr').value.trim() || null,
      temp: document.getElementById('ev-temp').value.trim() || null,
      weight: document.getElementById('ev-weight').value.trim() || null,
      height: null,
    },
    notes: document.getElementById('ev-notes').value.trim(),
    follow_up: document.getElementById('ev-followup').value.trim() || null,
  };

  try {
    await API.patch(`/api/patients/${patientId}/visits/${visitId}`, data);
    closeModal();
    toast('Visit updated', 'success');
    const p = await API.get(`/api/patients/${patientId}`);
    _renderDetail(p);
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ── MODAL HELPERS ────────────────────────────────────────────────────────────

function openModal(html) {
  closeModal();
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'modal-overlay';
  overlay.innerHTML = `<div class="modal">${html}</div>`;
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  document.body.appendChild(overlay);
}

function closeModal() {
  document.getElementById('modal-overlay')?.remove();
}
