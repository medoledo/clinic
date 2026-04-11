let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let recordBtn = null;

const TRANSCRIBE_URL = '/transcribe-visit/';
const SUGGESTIONS_URL = '/check-suggestions/';
const SAVE_CORRECTION_URL = '/save-correction/';
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
            method = 'POST',
            headers: { 'X-CSRFToken': CSRF_TOKEN },
            body: formData
        });

        const data = await response.json();

        if (data.success && data.fields) {
            fillFields(data.fields);
            setStatus('✅ تم تعبئة الحقول بنجاح', 'success');
            setTimeout(resetStatusUI, 4000);
            // Check for suggestions after fields are filled
            await checkAllFieldsForSuggestions(data.fields);
        } else {
            setStatus(`❌ ${data.error || 'حدث خطأ'}`, 'error');
            setTimeout(resetStatusUI, 6000);
        }

    } catch (err) {
        setStatus('❌ خطأ في الاتصال بالخادم', 'error');
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
            هل تقصد: <strong>${suggestedWord}</strong> بدلاً من "${originalWord}"؟
        </span>
        <button class="suggestion-popup__yes" type="button">✓ نعم</button>
        <button class="suggestion-popup__no" type="button">✗ لا</button>
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
                            new RegExp(suggestion.original, 'g'),
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
                body: JSON.stringify({ text })
            });

            const data = await response.json();

            if (data.success) {
                // Apply auto-corrections silently first
                if (data.corrected_text !== text) {
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
            console.error('Suggestion check failed:', err);
        }
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
             setTimeout(resetStatusUI, 3000);
        }
    });
});
