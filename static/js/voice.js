let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let recordBtn = null;

const TRANSCRIBE_URL = '/transcribe-visit/';
const CSRF_TOKEN = document.querySelector('[name=csrfmiddlewaretoken]')?.value || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';

function setStatus(message, type = 'info') {
    const statusEl = document.getElementById('voice-status');
    if (!statusEl) return;
    statusEl.innerText = message;
    statusEl.className = `voice-status voice-status--${type}`;
}

function fillFields(fields) {
    Object.entries(fields).forEach(([fieldId, value]) => {
        if (!value || !value.trim()) return;
        const field = document.getElementById(fieldId);
        if (!field) return;
        const space = field.value && !field.value.endsWith(' ') ? ' ' : '';
        field.value += space + value.trim();
        field.dispatchEvent(new Event('input'));
    });
}

function resetStatusUi() {
    setStatus('', 'info');
    document.querySelectorAll('.form-textarea').forEach(ta => ta.classList.remove('voice-active'));
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            stream.getTracks().forEach(t => t.stop());
            await sendRecording();
        };

        mediaRecorder.start();
        isRecording = true;
        recordBtn.classList.add('recording');
        recordBtn.innerHTML = '⏹️ إيقاف التسجيل';
        setStatus('🎙️ جاري التسجيل... تكلم الآن', 'recording');

    } catch (err) {
        setStatus('❌ لا يمكن الوصول للميكروفون', 'error');
        console.error('Microphone error:', err);
    }
}

function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        recordBtn.classList.remove('recording');
        recordBtn.innerHTML = '🎙️ تسجيل الزيارة';
        setStatus('⏳ جاري التحليل عبر الذكاء الاصطناعي...', 'loading');
    }
}

async function sendRecording() {
    if (audioChunks.length === 0) return;
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', audioBlob, 'visit.webm');

    try {
        const response = await fetch(TRANSCRIBE_URL, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF_TOKEN },
            body: formData
        });

        const data = await response.json();

        if (data.success && data.fields) {
            fillFields(data.fields);
            setStatus('✅ تم تعبئة الحقول بنجاح', 'success');
            setTimeout(resetStatusUi, 4000);
        } else {
            setStatus(`❌ ${data.error || 'حدث خطأ'}`, 'error');
            setTimeout(resetStatusUi, 6000);
        }

    } catch (err) {
        setStatus('❌ خطأ في الاتصال بالخادم', 'error');
        console.error('Send error:', err);
        setTimeout(resetStatusUi, 6000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    recordBtn = document.getElementById('visit-record-btn');
    if (!recordBtn) return;

    recordBtn.addEventListener('click', () => {
        if (!isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    });

    // Press ESC to cancel without processing
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && isRecording) {
             if (mediaRecorder) {
                 // Prevent the normal onstop data send
                 mediaRecorder.onstop = function () {
                     if (mediaRecorder.stream) mediaRecorder.stream.getTracks().forEach(t => t.stop());
                 };
                 mediaRecorder.stop();
             }
             isRecording = false;
             recordBtn.classList.remove('recording');
             recordBtn.innerHTML = '🎙️ تسجيل الزيارة';
             setStatus('تم الإلغاء', 'error');
             setTimeout(resetStatusUi, 3000);
        }
    });
});
