let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let recordBtn = null;

// --- Offline fallback state ---
let offlineRecognition = null;
let isOfflineMode = false;

const TRANSCRIBE_URL = '/transcribe-visit/';
const SUGGESTIONS_URL = '/check-suggestions/';
const SAVE_CORRECTION_URL = '/save-correction/';

// --- i18n strings from template data attributes ---
const recorderContainer = document.querySelector('.visit-recorder');
const STRINGS = recorderContainer ? {
    listening: recorderContainer.dataset.statusListeningEn || recorderContainer.dataset.statusListening,
    processing: recorderContainer.dataset.statusProcessingEn || recorderContainer.dataset.statusProcessing,
    success: recorderContainer.dataset.statusSuccessEn || recorderContainer.dataset.statusSuccess,
    errorMic: recorderContainer.dataset.statusErrorMicEn || recorderContainer.dataset.statusErrorMic,
    errorConnection: recorderContainer.dataset.statusErrorConnectionEn || recorderContainer.dataset.statusErrorConnection,
    offline: recorderContainer.dataset.statusOfflineEn || recorderContainer.dataset.statusOffline,
    offlineDone: recorderContainer.dataset.statusOfflineDoneEn || recorderContainer.dataset.statusOfflineDone,
    empty: recorderContainer.dataset.statusEmptyEn || recorderContainer.dataset.statusEmpty,
    btnRecord: recorderContainer.dataset.btnRecordEn || recorderContainer.dataset.btnRecord,
    btnStop: recorderContainer.dataset.btnStopEn || recorderContainer.dataset.btnStop,
    suggest: recorderContainer.dataset.lblSuggestEn || recorderContainer.dataset.lblSuggest,
    instead: recorderContainer.dataset.lblInsteadEn || recorderContainer.dataset.lblInstead,
    yes: recorderContainer.dataset.lblYesEn || recorderContainer.dataset.lblYes,
    no: recorderContainer.dataset.lblNoEn || recorderContainer.dataset.lblNo,
} : {};

function getCSRFToken() {
    // Try cookie first
    const cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
    if (cookieMatch) return cookieMatch[1];
    // Fallback to meta tag
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) return metaTag.getAttribute('content');
    // Fallback to hidden input
    const hiddenInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (hiddenInput) return hiddenInput.value;
    return '';
}
const CSRF_TOKEN = getCSRFToken();

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

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

        // Special handling for date fields
        if (field.type === 'date' || field.type === 'datetime-local') {
            // Check if value is already in YYYY-MM-DD or similar
            // If it's something like "24-2027", we might want to fix it, but for now we just set it.
            // If the browser rejects it, it won't show, but it might still submit.
            field.value = value.trim();
        } else {
            const space = field.value && !field.value.endsWith(' ') ? ' ' : '';
            field.value += space + value.trim();
        }
        field.dispatchEvent(new Event('input'));
    });
}


function resetStatusUI() {
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
        recordBtn.innerHTML = STRINGS.btnStop;
        setStatus(STRINGS.listening, 'recording');

    } catch (err) {
        setStatus(STRINGS.errorMic, 'error');
        console.error('Microphone error:', err);
        isRecording = false;
        if (recordBtn) {
            recordBtn.classList.remove('recording');
            recordBtn.innerHTML = STRINGS.btnRecord;
        }
    }
}

function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        recordBtn.classList.remove('recording');
        recordBtn.innerHTML = STRINGS.btnRecord;
        setStatus(STRINGS.processing, 'loading');
    }
}

async function sendRecording() {
    if (audioChunks.length === 0) return;

    // If still offline, don't attempt the fetch — just inform the user
    if (!navigator.onLine) {
        setStatus('🎙️ Audio recorded — connect to internet to transcribe', 'warning');
        setTimeout(resetStatusUI, 5000);
        return;
    }

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
            setStatus(STRINGS.success, 'success');
            setTimeout(resetStatusUI, 4000);
            // Check for suggestions after fields are filled
            await checkAllFieldsForSuggestions(data.fields);
        } else {
            setStatus(`${STRINGS.errorConnection}${data.error ? ': ' + data.error : ''}`, 'error');
            setTimeout(resetStatusUI, 6000);
        }

    } catch (err) {
        setStatus(STRINGS.errorConnection, 'error');
        console.error('Send error:', err);
        setTimeout(resetStatusUI, 6000);
    }
}

// Track active popups
let activePopup = null;

function closeActivePopup() {
    if (activePopup) {
        activePopup.remove();
        activePopup = null;
    }
}

function showSuggestionPopup(fieldEl, originalWord, suggestedWord, onConfirm) {
    closeActivePopup();

    const popup = document.createElement('div');
    popup.className = 'suggestion-popup';
    popup.innerHTML = `
        <span class="suggestion-popup__text">
            ${STRINGS.suggest} <strong>${suggestedWord}</strong> ${STRINGS.instead} "${originalWord}"؟
        </span>
        <button class="suggestion-popup__yes" type="button">${STRINGS.yes}</button>
        <button class="suggestion-popup__no" type="button">${STRINGS.no}</button>
    `;

    // Position popup near the field
    const rect = fieldEl.getBoundingClientRect();
    popup.style.position = 'fixed';
    popup.style.top = `${rect.bottom + window.scrollY + 6}px`;
    popup.style.left = `${rect.left + window.scrollX}px`;
    popup.style.zIndex = '9999';

    document.body.appendChild(popup);
    activePopup = popup;

    popup.querySelector('.suggestion-popup__yes').addEventListener('click', () => {
        onConfirm(true);
        closeActivePopup();
    });

    popup.querySelector('.suggestion-popup__no').addEventListener('click', () => {
        onConfirm(false);
        closeActivePopup();
    });

    // Auto-close after 8 seconds
    setTimeout(closeActivePopup, 8000);
}

async function processSuggestions(suggestions, fieldId) {
    if (!suggestions || suggestions.length === 0) return;

    const fieldEl = document.getElementById(fieldId);
    if (!fieldEl) return;

    // Process suggestions one at a time sequentially
    for (const suggestion of suggestions) {
        await new Promise((resolve) => {
            showSuggestionPopup(
                fieldEl,
                suggestion.original,
                suggestion.suggestion,
                async (confirmed) => {
                    if (confirmed) {
                        // Replace in field
                        fieldEl.value = fieldEl.value.replace(
                            new RegExp(escapeRegex(suggestion.original), 'g'),
                            suggestion.suggestion
                        );
                        fieldEl.dispatchEvent(new Event('input'));

                        // Save correction permanently
                        try {
                            await fetch(SAVE_CORRECTION_URL, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': CSRF_TOKEN
                                },
                                body: JSON.stringify({
                                    wrong_word: suggestion.original,
                                    correct_word: suggestion.suggestion
                                })
                            });
                        } catch (err) {
                            console.error('Failed to save correction:', err);
                        }
                    }
                    resolve();
                }
            );
        });
    }
}

async function checkAllFieldsForSuggestions(fields) {
    // Check each populated field for suggestions
    const fieldIds = Object.keys(fields).filter(k => fields[k] && fields[k].trim());

    for (const fieldId of fieldIds) {
        const text = fields[fieldId];
        if (!text || text.trim().length < 3) continue;

        try {
            const response = await fetch(SUGGESTIONS_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({ text: text })  // send FULL field text, not individual words
            });

            const data = await response.json();

            if (data.success) {
                // Apply auto-corrections silently first
                if (data.corrected_text && data.corrected_text !== text) {
                    const fieldEl = document.getElementById(fieldId);
                    if (fieldEl) {
                        fieldEl.value = data.corrected_text;
                        fieldEl.dispatchEvent(new Event('input'));
                    }
                }

                // Then show popup suggestions for remaining uncertain words
                if (data.suggestions && data.suggestions.length > 0) {
                    await processSuggestions(data.suggestions, fieldId);
                }
            }
        } catch (err) {
            console.error('Suggestion check failed for field', fieldId, err);
        }
    }
}

// --- Offline fallback: use raw audio recording ---
// SpeechRecognition always requires network (Google servers), so offline we
// record audio normally and inform the user it will be transcribed when online.

function startOfflineRecording() {
    // SpeechRecognition requires Google servers, cannot work offline.
    // Use standard MediaRecorder directly. startRecording() sets all UI state.
    isOfflineMode = true;
    startRecording();
}


function stopOfflineRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        isOfflineMode = false;
        recordBtn.classList.remove('recording');
        recordBtn.innerHTML = STRINGS.btnRecord;
        setStatus(STRINGS.offlineDone, 'warning');
        setTimeout(resetStatusUI, 5000);
    }
}

function fillFieldsOffline(transcript) {
    const fieldMap = {
        'chief_complaint': ['شكوى', 'الشكوى', 'شكوة'],
        'symptoms': ['أعراض', 'الأعراض', 'علامات'],
        'diagnosis': ['تشخيص', 'التشخيص', 'تشخيصي'],
        'treatment': ['علاج', 'العلاج', 'وصفة', 'الوصفة', 'دواء'],
        'doctor_notes': ['ملاحظات', 'ملاحظات خاصة', 'نوت', 'نوتس']
    };
    const fields = {};
    const triggers = [];
    for (const [fieldId, keywords] of Object.entries(fieldMap)) {
        for (const keyword of keywords) {
            const idx = transcript.indexOf(keyword);
            if (idx !== -1) triggers.push({ fieldId, keyword, idx });
        }
    }
    triggers.sort((a, b) => a.idx - b.idx);
    for (let i = 0; i < triggers.length; i++) {
        const current = triggers[i];
        const next = triggers[i + 1];
        const start = current.idx + current.keyword.length;
        const end = next ? next.idx : transcript.length;
        const content = transcript.slice(start, end).trim();
        if (content) fields[current.fieldId] = content;
    }
    fillFields(fields);
    setStatus(STRINGS.offlineDone, 'warning');
    setTimeout(() => setStatus('', 'info'), 6000);
}

document.addEventListener('DOMContentLoaded', () => {
    recordBtn = document.getElementById('visit-record-btn');
    if (!recordBtn) return;
    recordBtn.innerHTML = STRINGS.btnRecord;

    recordBtn.addEventListener('click', () => {
        if (!isRecording && !isOfflineMode) {
            if (!navigator.onLine) {
                setStatus('Connect to the internet first', 'error');
                return;
            } else {
                startRecording();
            }
        } else if (isRecording) {
            stopRecording();
        } else if (isOfflineMode) {
            stopOfflineRecording();
        }
    });

    // Press ESC to cancel without processing
    document.addEventListener('keydown', function (e) {
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
            recordBtn.innerHTML = STRINGS.btnRecord;
            setStatus('Cancelled', 'error');
            setTimeout(resetStatusUI, 3000);
        }
    });
});
