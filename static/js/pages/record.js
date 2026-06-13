let mediaRecorder = null;
let audioChunks = [];
let timerInterval = null;
let seconds = 0;

function renderRecord() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <h1 style="margin-bottom:1.5rem">New Record</h1>

    <div style="display:flex;gap:1rem;margin-bottom:1.5rem">
      <button class="btn btn-primary" id="tab-audio" onclick="switchTab('audio')">🎙 Record Audio</button>
      <button class="btn btn-ghost" id="tab-upload" onclick="switchTab('upload')">📁 Upload File</button>
      <button class="btn btn-ghost" id="tab-text" onclick="switchTab('text')">✏️ Paste Transcript</button>
    </div>

    <div id="tab-content"></div>
    <div id="record-result" style="margin-top:1.5rem"></div>
  `;
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
        <p style="color:var(--text-muted);margin:0.6rem 0 1.2rem">Click to start recording your consultation</p>
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
  await submitAudioForm(formData);
}

async function submitUpload() {
  const file = document.getElementById('audio-file').files[0];
  if (!file) { toast('Please select a file', 'error'); return; }
  const formData = new FormData();
  formData.append('audio', file);
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
  console.log('[submitTranscript] called, text length:', text.length);
  if (!text) { toast('Please enter a transcript', 'error'); return; }
  showProcessing();
  const formData = new FormData();
  formData.append('transcript', text);
  console.log('[submitTranscript] sending POST to /api/record/transcript');
  try {
    const result = await API.postForm('/api/record/transcript', formData);
    console.log('[submitTranscript] success:', result);
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
  const p = result.extracted.patient;
  document.getElementById('record-result').innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
        <h2 style="margin:0">Record Created</h2>
        <button class="btn btn-primary btn-sm" onclick="Router.go('patient', ${result.patient_id})">View Patient →</button>
      </div>
      <div class="grid-2">
        <div>
          <h3>Patient</h3>
          <strong>${p.name || 'Unknown'}</strong>
          <p style="color:var(--text-muted);font-size:0.85rem">${p.age ? p.age + ' yrs' : ''} ${p.gender || ''}</p>
        </div>
        <div>
          <h3>Chief Complaint</h3>
          <p>${v.chief_complaint || '—'}</p>
        </div>
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
      ${v.prescriptions && v.prescriptions.length ? `
        <div style="margin-top:1rem">
          <h3>Prescriptions</h3>
          ${v.prescriptions.map(rx => `<span class="tag tag-drug">${rx.drug} ${rx.dose || ''} ${rx.frequency || ''}</span>`).join('')}
        </div>` : ''}
      ${v.notes ? `<div style="margin-top:1rem"><h3>Notes</h3><p>${v.notes}</p></div>` : ''}
    </div>
  `;
  toast('Record saved successfully', 'success');
}
