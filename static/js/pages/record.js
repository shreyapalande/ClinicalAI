let mediaRecorder = null;
let audioChunks = [];
let timerInterval = null;
let seconds = 0;
let selectedPatient = null; // null = new patient, object = existing patient

function renderRecord() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <h1 style="margin-bottom:1.5rem">New Record</h1>

    <!-- Step 1: Patient Selection -->
    <div class="card" id="patient-select-card">
      <h2 style="margin-bottom:1rem">Step 1 — Select Patient</h2>
      <div style="display:flex;gap:0.7rem;margin-bottom:1rem">
        <input type="text" id="patient-search" placeholder="Search by name or ID…" style="flex:1" oninput="searchPatients()" />
        <button class="btn btn-ghost" onclick="selectNewPatient()">+ New Patient</button>
      </div>
      <div id="patient-search-results"></div>
      <div id="selected-patient-banner" style="display:none"></div>
    </div>

    <!-- Step 2: Recording (hidden until patient selected) -->
    <div id="record-step2" style="display:none;margin-top:1.2rem">
      <div class="card" style="margin-bottom:1rem">
        <h2 style="margin-bottom:0.2rem">Step 2 — Record or Upload</h2>
        <small id="recording-for-label" style="color:var(--text-muted)"></small>
      </div>

      <div style="display:flex;gap:1rem;margin-bottom:1.5rem">
        <button class="btn btn-primary" id="tab-audio" onclick="switchTab('audio')">🎙 Record Audio</button>
        <button class="btn btn-ghost" id="tab-upload" onclick="switchTab('upload')">📁 Upload File</button>
        <button class="btn btn-ghost" id="tab-text" onclick="switchTab('text')">✏️ Paste Transcript</button>
      </div>
      <div id="tab-content"></div>
    </div>

    <div id="record-result" style="margin-top:1.5rem"></div>
  `;
  searchPatients();
}

async function searchPatients() {
  const q = document.getElementById('patient-search').value.trim();
  const results = document.getElementById('patient-search-results');

  if (!q) {
    results.innerHTML = '';
    return;
  }

  try {
    const patients = await API.get(`/api/patients/?q=${encodeURIComponent(q)}`);
    if (!patients.length) {
      results.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem;padding:0.5rem 0">No patients found — choose "New Patient" to create one.</p>`;
      return;
    }
    results.innerHTML = patients.map(p => `
      <div class="card" style="margin-bottom:0.5rem;cursor:pointer;padding:0.9rem 1.1rem" onclick="selectExistingPatient(${p.id}, '${(p.name||'').replace(/'/g,"\\'")}', ${p.age||'null'}, '${p.gender||''}')">
        <div style="display:flex;align-items:center;gap:0.8rem">
          <div class="patient-avatar" style="width:36px;height:36px;font-size:1rem">${(p.name||'?')[0].toUpperCase()}</div>
          <div>
            <strong>${p.name}</strong>
            <div style="font-size:0.8rem;color:var(--text-muted)">ID: ${p.id}${p.age ? ' · ' + p.age + ' yrs' : ''}${p.gender ? ' · ' + p.gender : ''}</div>
          </div>
          <span style="margin-left:auto;font-size:0.78rem;color:var(--accent)">Select →</span>
        </div>
      </div>
    `).join('');
  } catch (e) {
    results.innerHTML = `<p style="color:var(--danger);font-size:0.85rem">${e.message}</p>`;
  }
}

function selectExistingPatient(id, name, age, gender) {
  selectedPatient = { id, name, age, gender };
  showPatientBanner(`Existing patient: <strong>${name}</strong> (ID: ${id})`, 'var(--accent)');
  showStep2(`Recording for: ${name} (ID ${id})`);
  document.getElementById('patient-search-results').innerHTML = '';
  document.getElementById('patient-search').value = name;
}

function selectNewPatient() {
  selectedPatient = null;
  showPatientBanner('New patient — details will be extracted from the transcript', 'var(--success)');
  showStep2('Recording for: New Patient');
}

function showPatientBanner(html, color) {
  const banner = document.getElementById('selected-patient-banner');
  banner.style.display = 'block';
  banner.innerHTML = `
    <div style="margin-top:0.8rem;padding:0.6rem 0.9rem;background:var(--surface2);border:1px solid ${color};border-radius:8px;font-size:0.88rem;display:flex;align-items:center;justify-content:space-between">
      <span>${html}</span>
      <button class="btn btn-ghost btn-sm" onclick="resetPatientSelection()">Change</button>
    </div>`;
}

function resetPatientSelection() {
  selectedPatient = undefined;
  document.getElementById('patient-search').value = '';
  document.getElementById('selected-patient-banner').style.display = 'none';
  document.getElementById('record-step2').style.display = 'none';
  document.getElementById('record-result').innerHTML = '';
  document.getElementById('patient-search-results').innerHTML = '';
}

function showStep2(label) {
  document.getElementById('record-step2').style.display = 'block';
  document.getElementById('recording-for-label').textContent = label;
  switchTab('audio');
}

function switchTab(tab) {
  ['audio', 'upload', 'text'].forEach(t => {
    document.getElementById(`tab-${t}`).className = t === tab ? 'btn btn-primary' : 'btn btn-ghost';
  });

  const content = document.getElementById('tab-content');
  if (tab === 'audio') {
    content.innerHTML = `
      <div class="recorder-box" id="recorder-box">
        <div class="recorder-icon" id="rec-icon">🎙</div>
        <div class="timer" id="rec-timer">0:00</div>
        <p style="color:var(--text-muted);margin:0.6rem 0 1.2rem">Click to start recording the consultation</p>
        <button class="btn btn-primary" id="rec-btn" onclick="toggleRecord()">Start Recording</button>
      </div>
    `;
  } else if (tab === 'upload') {
    content.innerHTML = `
      <div class="card">
        <div class="form-group">
          <label>Audio File (mp3, wav, webm, m4a)</label>
          <input type="file" id="audio-file" accept="audio/*" />
        </div>
        <button class="btn btn-primary" onclick="submitUpload()">Process File</button>
      </div>
    `;
  } else {
    content.innerHTML = `
      <div class="card">
        <div class="form-group">
          <label>Paste or type a consultation transcript</label>
          <textarea id="transcript-text" rows="8" placeholder="Doctor: Good morning. How are you feeling today?&#10;Patient: I've had a headache for 3 days..."></textarea>
        </div>
        <button class="btn btn-primary" onclick="submitTranscript()">Extract & Save</button>
      </div>
    `;
  }
}

async function toggleRecord() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    stopRecording();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = handleRecordingStop;
    mediaRecorder.start();

    seconds = 0;
    timerInterval = setInterval(() => {
      seconds++;
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      const el = document.getElementById('rec-timer');
      if (el) el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
    }, 1000);

    document.getElementById('recorder-box').classList.add('recording');
    document.getElementById('rec-icon').textContent = '🔴';
    document.getElementById('rec-btn').textContent = 'Stop Recording';
    document.getElementById('rec-btn').className = 'btn btn-danger';
  } catch (e) {
    toast('Microphone access denied', 'error');
  }
}

function stopRecording() {
  if (mediaRecorder) {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    clearInterval(timerInterval);
    document.getElementById('recorder-box').classList.remove('recording');
    document.getElementById('rec-btn').textContent = 'Processing...';
    document.getElementById('rec-btn').disabled = true;
  }
}

async function handleRecordingStop() {
  const blob = new Blob(audioChunks, { type: 'audio/webm' });
  const formData = new FormData();
  formData.append('audio', blob, 'recording.webm');
  if (selectedPatient) formData.append('patient_id', selectedPatient.id);
  await submitAudioForm(formData);
}

async function submitUpload() {
  const file = document.getElementById('audio-file').files[0];
  if (!file) { toast('Please select a file', 'error'); return; }
  const formData = new FormData();
  formData.append('audio', file);
  if (selectedPatient) formData.append('patient_id', selectedPatient.id);
  await submitAudioForm(formData);
}

async function submitAudioForm(formData) {
  showProcessing();
  try {
    const result = await API.postForm('/api/record/', formData);
    showResult(result);
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
    hideProcessing();
  }
}

async function submitTranscript() {
  const text = document.getElementById('transcript-text').value.trim();
  if (!text) { toast('Please enter a transcript', 'error'); return; }
  showProcessing();
  const formData = new FormData();
  formData.append('transcript', text);
  if (selectedPatient) formData.append('patient_id', selectedPatient.id);
  try {
    const result = await API.postForm('/api/record/transcript', formData);
    showResult(result);
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
    hideProcessing();
  }
}

function showProcessing() {
  document.getElementById('record-result').innerHTML = `
    <div class="card" style="text-align:center;padding:2rem">
      <div class="spinner" style="width:32px;height:32px;border-width:3px"></div>
      <p style="margin-top:1rem;color:var(--text-muted)">Transcribing & extracting medical data…</p>
    </div>
  `;
}

function hideProcessing() {
  document.getElementById('record-result').innerHTML = '';
}

function showResult(result) {
  const v = result.extracted.visit;
  document.getElementById('record-result').innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
        <div>
          <h2 style="margin:0">Visit Saved</h2>
          <small style="color:var(--text-muted)">Linked to: <strong>${result.patient_name}</strong> (ID: ${result.patient_id})</small>
        </div>
        <button class="btn btn-primary btn-sm" onclick="Router.go('patient', ${result.patient_id})">View Patient →</button>
      </div>
      <hr />
      <div class="grid-2">
        <div>
          <h3>Chief Complaint</h3>
          <p>${v.chief_complaint || '—'}</p>
        </div>
        <div>
          <h3>Symptoms</h3>
          ${renderTags(v.symptoms, 'tag-symptom')}
        </div>
      </div>
      <div class="grid-2" style="margin-top:1rem">
        <div>
          <h3>Diagnoses</h3>
          ${renderTags(v.diagnoses, 'tag-diagnosis')}
        </div>
        <div>
          <h3>Prescriptions</h3>
          ${v.prescriptions && v.prescriptions.length
            ? v.prescriptions.map(rx => `<span class="tag tag-drug">${rx.drug} ${rx.dose || ''} ${rx.frequency || ''}</span>`).join('')
            : '—'}
        </div>
      </div>
      ${v.notes ? `<div style="margin-top:1rem"><h3>Notes</h3><p>${v.notes}</p></div>` : ''}
      ${v.follow_up ? `<p style="margin-top:0.6rem"><small>Follow-up: ${v.follow_up}</small></p>` : ''}
    </div>
  `;
  toast('Visit saved successfully', 'success');
}
