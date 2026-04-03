/**
 * voice.js — MediTrack Voice Transcription System
 * Uses Web Speech API (works in Chrome/Edge only)
 */
(function () {
  'use strict';

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  // Elements
  const masterBtn = document.getElementById('master-mic-btn');
  const masterText = document.getElementById('master-mic-text');
  const masterIcon = document.getElementById('master-mic-icon');
  const waveAnim = document.getElementById('wave-animation');
  const recordingStatus = document.getElementById('recording-status');
  const voiceNotSupported = document.getElementById('voice-not-supported');
  const micDeniedMsg = document.getElementById('mic-denied-msg');
  const voiceNetworkMsg = document.getElementById('voice-network-msg');

  if (!SpeechRecognition) {
    if (voiceNotSupported) voiceNotSupported.classList.remove('hidden');
    return;
  }

  let recognition = null;
  let isRunning = false;
  let currentFieldId = null;
  let interimSpan = null;
  let currentLang = 'ar-EG';

  // ── Language toggle ──
  window.setLang = function (lang) {
    currentLang = lang;
    if (document.getElementById('lang-mix')) {
      document.getElementById('lang-mix').className = lang === 'ar-EG' 
        ? 'px-4 py-2 bg-primary text-white transition-colors' 
        : 'px-4 py-2 bg-white text-muted hover:bg-gray-50 transition-colors';
    }
    if (document.getElementById('lang-ar')) {
      document.getElementById('lang-ar').className = lang === 'ar-SA' 
        ? 'px-4 py-2 bg-primary text-white transition-colors' 
        : 'px-4 py-2 bg-white text-muted hover:bg-gray-50 transition-colors';
    }
    if (document.getElementById('lang-en')) {
      document.getElementById('lang-en').className = lang === 'en-US' 
        ? 'px-4 py-2 bg-primary text-white transition-colors' 
        : 'px-4 py-2 bg-white text-muted hover:bg-gray-50 transition-colors';
    }
    if (isRunning && recognition) {
      recognition.lang = lang;
    }
  };

  function createRecognition() {
    const rec = new SpeechRecognition();
    rec.lang = currentLang;
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onresult = function (event) {
      if (!currentFieldId) return;
      const textarea = document.getElementById(currentFieldId);
      if (!textarea) return;

      let interim = '';
      let finalText = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }

      // Append final text
      if (finalText) {
        const current = textarea.value;
        textarea.value = (current ? current + ' ' : '') + finalText.trim();
        if (interimSpan) interimSpan.remove();
        interimSpan = null;
      }

      // Show interim in a span
      if (interim) {
        if (!interimSpan) {
          interimSpan = document.createElement('span');
          interimSpan.className = 'interim-text';
          interimSpan.id = 'interim-preview';
        }
        interimSpan.textContent = interim;
        // show below textarea
        const container = textarea.parentElement;
        const existing = container.querySelector('#interim-preview');
        if (!existing) container.appendChild(interimSpan);
      }
    };

    rec.onerror = function (event) {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        stopAll();
        if (micDeniedMsg) micDeniedMsg.classList.remove('hidden');
      } else if (event.error === 'network') {
        stopAll();
        if (voiceNetworkMsg) voiceNetworkMsg.classList.remove('hidden');
      } else if (event.error === 'no-speech') {
        // silence — auto-restart
        if (isRunning) {
          try { rec.start(); } catch (e) {}
        }
      } else {
        const status = document.createElement('div');
        status.className = 'text-danger text-xs mt-1';
        status.textContent = 'Recognition error: ' + event.error + '. Try again.';
        if (currentFieldId) {
          const ta = document.getElementById(currentFieldId);
          if (ta) ta.parentElement.appendChild(status);
          setTimeout(() => status.remove(), 3000);
        }
      }
    };

    rec.onend = function () {
      if (interimSpan) interimSpan.remove();
      interimSpan = null;
      // Auto-restart if still should be running
      if (isRunning && currentFieldId) {
        try { rec.start(); } catch (e) {}
      } else if (!isRunning) {
        setMasterStopped();
      }
    };

    return rec;
  }

  function startRecording(fieldId) {
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
    }
    recognition = createRecognition();
    isRunning = true;
    currentFieldId = fieldId;

    try {
      recognition.start();
    } catch (e) {
      if (voiceNetworkMsg) voiceNetworkMsg.classList.remove('hidden');
      isRunning = false;
      return;
    }

    setMasterRunning();
    highlightField(fieldId);
  }

  function stopAll() {
    isRunning = false;
    currentFieldId = null;
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
      recognition = null;
    }
    if (interimSpan) { interimSpan.remove(); interimSpan = null; }
    setMasterStopped();
    unhighlightAll();
    document.querySelectorAll('.mic-btn.recording').forEach(b => {
      b.classList.remove('recording');
      b.textContent = '🎤';
    });
  }

  function setMasterRunning() {
    if (!masterBtn) return;
    masterBtn.classList.add('!border-danger', '!text-danger', '!bg-red-50');
    masterIcon.textContent = '🔴';
    masterText.textContent = 'Stop Recording';
    if (waveAnim) waveAnim.classList.remove('hidden');
    waveAnim.classList.add('flex');
    if (recordingStatus) recordingStatus.classList.remove('hidden');
  }

  function setMasterStopped() {
    if (!masterBtn) return;
    masterBtn.classList.remove('!border-danger', '!text-danger', '!bg-red-50');
    masterIcon.textContent = '🎤';
    masterText.textContent = 'Start Recording';
    if (waveAnim) { waveAnim.classList.add('hidden'); waveAnim.classList.remove('flex'); }
    if (recordingStatus) recordingStatus.classList.add('hidden');
  }

  function highlightField(fieldId) {
    unhighlightAll();
    const el = document.getElementById(fieldId);
    if (el) el.classList.add('voice-active');
    // Mark the correct mic button
    document.querySelectorAll('.field-mic').forEach(b => {
      if (b.dataset.target === fieldId) {
        b.classList.add('recording');
        b.textContent = '🔴';
      } else {
        b.classList.remove('recording');
        b.textContent = '🎤';
      }
    });
  }

  function unhighlightAll() {
    document.querySelectorAll('.form-textarea').forEach(ta => ta.classList.remove('voice-active'));
  }

  // Master mic button
  if (masterBtn) {
    masterBtn.addEventListener('click', () => {
      if (isRunning) {
        stopAll();
      } else {
        // Start on first field
        const firstMic = document.querySelector('.field-mic');
        const firstField = firstMic ? firstMic.dataset.target : null;
        if (firstField) startRecording(firstField);
        else startRecording('chief_complaint');
      }
    });
  }

  // Per-field mic buttons
  document.querySelectorAll('.field-mic').forEach(btn => {
    btn.addEventListener('click', () => {
      const fieldId = btn.dataset.target;
      if (currentFieldId === fieldId && isRunning) {
        stopAll();
      } else {
        startRecording(fieldId);
      }
    });
  });

  // Keyboard: ESC stops
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && isRunning) stopAll();
  });

  // Expose for shortcuts.js
  window._voiceToggle = function () {
    if (isRunning) stopAll();
    else if (masterBtn) masterBtn.click();
  };

  // Auto-stop after 10s of silence handled by onerror 'no-speech' + recognition.maxResults
})();
