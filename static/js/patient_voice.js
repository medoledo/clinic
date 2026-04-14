let patientMediaRecorder = null;
let patientAudioChunks = [];
let isPatientRecording = false;
let patientRecordBtn = null;

// --- Offline fallback state ---
let patientOfflineRecognition = null;
let isPatientOfflineMode = false;

const PATIENT_TRANSCRIBE_URL = '/transcribe-patient/';

// --- i18n strings ---
const PATIENT_STRINGS = {
    listening: '🎤 جاري الاستماع... تكلم الآن',
    listeningEn: '🎤 Listening... Speak now',
    processing: '⏳ جاري التحليل...',
    processingEn: '⏳ Processing...',
    success: '✅ تم تعبئة الحقول بنجاح',
    successEn: '✅ Fields filled successfully',
    errorMic: '❌ لا يمكن الوصول للميكروفون',
    errorMicEn: '❌ Microphone access denied',
    errorConnection: '❌ خطأ في الاتصال بالخادم',
    errorConnectionEn: '❌ Server connection error',
    offline: '🎤 وضع بدون إنترنت — جاري الاستماع...',
    offlineEn: '🎤 Offline mode — Listening...',
    offlineDone: '⚠️ تم التعبيئة بوضع بدون إنترنت — الدقة أقل من المعتاد',
    offlineDoneEn: '⚠️ Offline processing complete — lower accuracy',
    empty: '❌ لم يتم التعرف على أي كلام',
    emptyEn: '❌ No speech detected',
    btnRecord: '🎤 تسجيل بيانات المريض',
    btnRecordEn: '🎤 Record Patient Info',
    btnStop: '⏹️ إيقاف التسجيل',
    btnStopEn: '⏹️ Stop Recording'
};

function getPatientCSRFToken() {
    const hiddenInput = document.querySelector('[name="csrfmiddlewaretoken"]');
    if (hiddenInput) return hiddenInput.value;
    const cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
    if (cookieMatch) return cookieMatch[1];
    return '';
}

function setPatientStatus(message, type = 'info') {
    const statusEl = document.getElementById('patient-voice-status');
    if (!statusEl) return;
    statusEl.innerText = message;
    statusEl.className = `patient-voice-status patient-voice-status--${type}`;
}

function fillPatientFields(fields) {
    Object.entries(fields).forEach(([fieldId, value]) => {
        if (!value || !value.trim()) return;
        const field = document.getElementById(fieldId) || document.querySelector(`[name="${fieldId}"]`);
        if (!field) return;

        field.value = value.trim();
        field.dispatchEvent(new Event('input'));
        field.dispatchEvent(new Event('change'));
    });
}

function resetPatientStatusUI() {
    setPatientStatus('Ready to record', 'info');
}

async function startPatientRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        patientAudioChunks = [];
        patientMediaRecorder = new MediaRecorder(stream);

        patientMediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) patientAudioChunks.push(e.data);
        };

        patientMediaRecorder.onstop = async () => {
            stream.getTracks().forEach(t => t.stop());
            await sendPatientRecording();
        };

        patientMediaRecorder.start();
        isPatientRecording = true;
        
        if (patientRecordBtn) {
            patientRecordBtn.classList.add('recording');
            patientRecordBtn.innerHTML = PATIENT_STRINGS.btnStopEn;
        }
        setPatientStatus(PATIENT_STRINGS.listeningEn, 'recording');

    } catch (err) {
        setPatientStatus(PATIENT_STRINGS.errorMicEn, 'error');
        console.error('Microphone error:', err);
    }
}

function stopPatientRecording() {
    if (patientMediaRecorder && isPatientRecording) {
        patientMediaRecorder.stop();
        isPatientRecording = false;
        if (patientRecordBtn) {
            patientRecordBtn.classList.remove('recording');
            patientRecordBtn.innerHTML = PATIENT_STRINGS.btnRecordEn;
        }
        setPatientStatus(PATIENT_STRINGS.processingEn, 'loading');
    }
}

async function sendPatientRecording() {
    if (patientAudioChunks.length === 0) return;
    const audioBlob = new Blob(patientAudioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', audioBlob, 'patient.webm');

    try {
        const response = await fetch(PATIENT_TRANSCRIBE_URL, {
            method: 'POST',
            headers: { 'X-CSRFToken': getPatientCSRFToken() },
            body: formData
        });

        const data = await response.json();

        if (data.success && data.fields) {
            fillPatientFields(data.fields);
            setPatientStatus(PATIENT_STRINGS.successEn, 'success');
            setTimeout(resetPatientStatusUI, 4000);
        } else {
            setPatientStatus(`${PATIENT_STRINGS.errorConnectionEn}${data.error ? ': ' + data.error : ''}`, 'error');
            setTimeout(resetPatientStatusUI, 6000);
        }

    } catch (err) {
        setPatientStatus(PATIENT_STRINGS.errorConnectionEn, 'error');
        console.error('Send error:', err);
        setTimeout(resetPatientStatusUI, 6000);
    }
}

// --- Offline fallback ---
function startPatientOfflineRecording() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        setPatientStatus(PATIENT_STRINGS.errorMicEn, 'error');
        return;
    }
    isPatientOfflineMode = true;
    patientOfflineRecognition = new SpeechRecognition();
    patientOfflineRecognition.lang = 'ar';
    patientOfflineRecognition.continuous = true;
    patientOfflineRecognition.interimResults = true;
    let fullTranscript = '';

    patientOfflineRecognition.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const text = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                fullTranscript += text + ' ';
            } else {
                interim = text;
            }
        }
        setPatientStatus(PATIENT_STRINGS.offlineEn + ' ' + (interim || fullTranscript), 'recording');
    };

    patientOfflineRecognition.onerror = (event) => {
        setPatientStatus(PATIENT_STRINGS.errorConnectionEn + ': ' + event.error, 'error');
        stopPatientOfflineRecording();
    };

    patientOfflineRecognition.onend = () => {
        if (isPatientOfflineMode && fullTranscript.trim()) {
            fillPatientFieldsOffline(fullTranscript.trim());
        }
    };

    patientOfflineRecognition.start();
    if (patientRecordBtn) {
        patientRecordBtn.classList.add('recording');
        patientRecordBtn.innerHTML = PATIENT_STRINGS.btnStopEn;
    }
    setPatientStatus(PATIENT_STRINGS.offlineEn, 'recording');
}

function stopPatientOfflineRecording() {
    if (patientOfflineRecognition) {
        isPatientOfflineMode = false;
        patientOfflineRecognition.stop();
        patientOfflineRecognition = null;
        if (patientRecordBtn) {
            patientRecordBtn.classList.remove('recording');
            patientRecordBtn.innerHTML = PATIENT_STRINGS.btnRecordEn;
        }
        setPatientStatus(PATIENT_STRINGS.processingEn, 'loading');
    }
}

function fillPatientFieldsOffline(transcript) {
    // Basic regex-based extraction as fallback
    let fields = {};
    const phoneMatch = transcript.match(/01[0125]\d{8}/);
    if (phoneMatch) fields['phone'] = phoneMatch[0];
    
    // Attempt notes extraction
    const notesKeywords = ['ملاحظات', 'ملاحظات عامة', 'notes'];
    for (const kw of notesKeywords) {
        const idx = transcript.indexOf(kw);
        if (idx !== -1) {
            fields['notes'] = transcript.substring(idx + kw.length).trim();
            break;
        }
    }
    
    fillPatientFields(fields);
    setPatientStatus(PATIENT_STRINGS.offlineDoneEn, 'warning');
    setTimeout(resetPatientStatusUI, 6000);
}

// Global initialization function
window.initPatientVoice = function() {
    patientRecordBtn = document.getElementById('patient-record-btn');
    if (!patientRecordBtn) return;

    // Reset UI
    patientRecordBtn.innerHTML = PATIENT_STRINGS.btnRecordEn;
    patientRecordBtn.classList.remove('recording');
    isPatientRecording = false;
    isPatientOfflineMode = false;

    // Remove existing listener (simple way)
    const newBtn = patientRecordBtn.cloneNode(true);
    patientRecordBtn.parentNode.replaceChild(newBtn, patientRecordBtn);
    patientRecordBtn = newBtn;

    patientRecordBtn.addEventListener('click', () => {
        if (!isPatientRecording && !isPatientOfflineMode) {
            if (!navigator.onLine) {
                startPatientOfflineRecording();
            } else {
                startPatientRecording();
            }
        } else if (isPatientRecording) {
            stopPatientRecording();
        } else if (isPatientOfflineMode) {
            stopPatientOfflineRecording();
        }
    });
};

// Auto-init on load if button is present
window.addEventListener('load', () => {
    if (document.getElementById('patient-record-btn')) {
        window.initPatientVoice();
    }
});
