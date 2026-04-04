/**
 * voice.js — MediTrack Voice Transcription System (Refined)
 * Focused on field-level recording with a sticky status indicator.
 */
(function () {
  'use strict';

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    document.getElementById('voice-not-supported')?.classList.remove('hidden');
    return;
  }

  // State
  let recognition = null;
  let isRunning = false;
  let currentFieldId = null;
  let pendingFieldId = null;
  let originalFieldValue = "";
  let selectedLang = localStorage.getItem('meditrack_lang') || 'en-US';

  // UI Elements
  const recordingStatus = document.getElementById('recording-status');
  const waveAnim = document.getElementById('wave-animation');

  // Initialization
  function initRecognition() {
    recognition = new SpeechRecognition();
    recognition.lang = selectedLang;
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onstart = () => {
      isRunning = true;
      updateStatusUI(true);
    };

    recognition.onresult = (event) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        let transcriptText = event.results[i][0].transcript;
        // Strip out punctuation (.,?!؛،؟)
        transcriptText = transcriptText.replace(/[.,?!؛،؟]/g, '');
        
        if (event.results[i].isFinal) {
          finalTranscript += transcriptText;
        } else {
          interimTranscript += transcriptText;
        }
      }

      if (currentFieldId) {
        const field = document.getElementById(currentFieldId);
        if (field) {
          // REAL-TIME TRANSCRIPT RENDERING
          if (finalTranscript) {
              const space = field.value && !field.value.endsWith(' ') ? ' ' : '';
              field.value += space + finalTranscript;
          }
          
          // Interim text is diverted to the grey element below the field
          let interimEl = document.getElementById(currentFieldId + '-interim');
          if (interimEl) {
              interimEl.innerText = interimTranscript ? interimTranscript : (finalTranscript ? '...' : '');
          }
          
          field.dispatchEvent(new Event('input'));
          
          if (finalTranscript) {
              finalTranscript = ''; 
          }
        }
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error', event.error);
      if (event.error === 'not-allowed') {
        document.getElementById('mic-denied-msg')?.classList.remove('hidden');
      }
      stopAll();
    };

    recognition.onend = () => {
      if (pendingFieldId) {
        // A field switch was queued! Start it up immediately.
        const nextField = pendingFieldId;
        pendingFieldId = null;
        startRecording(nextField);
      } else if (isRunning) {
        // Restart if it stopped unexpectedly (e.g. silence or language toggle)
        try { recognition.start(); } catch(e) {}
      } else {
        updateStatusUI(false);
      }
    };
  }

  function startRecording(fieldId) {
    if (isRunning) {
      if (currentFieldId === fieldId) {
        // Toggle OFF current field
        stopAll();
        return;
      }
      // Toggle TO new field
      // We must stop the mic asynchronously, wait for onend, and then start the new field.
      pendingFieldId = fieldId;
      stopAll(); 
      return;
    }

    currentFieldId = fieldId;
    const field = document.getElementById(fieldId);
    if (field) {
        originalFieldValue = field.value;
        if (originalFieldValue && !originalFieldValue.endsWith(' ')) {
            originalFieldValue += ' ';
        }
        
        let interimEl = document.getElementById(fieldId + '-interim');
        if (!interimEl) {
            interimEl = document.createElement('div');
            interimEl.id = fieldId + '-interim';
            interimEl.className = 'text-gray-400 text-sm font-semibold italic mt-1.5 min-h-[20px] opacity-75';
            field.parentNode.appendChild(interimEl);
        }
        interimEl.innerText = 'Listening...';
        interimEl.style.display = 'block';
    } else {
        originalFieldValue = "";
    }

    if (!recognition) initRecognition();

    highlightField(fieldId);
    try {
        recognition.lang = selectedLang;
        recognition.start();
    } catch(e) {}
  }

  function stopAll() {
    isRunning = false;
    if (currentFieldId) {
        let interimEl = document.getElementById(currentFieldId + '-interim');
        if (interimEl) interimEl.remove();
    }
    currentFieldId = null;
    if (recognition) {
        try { recognition.stop(); } catch(e) {}
    }
    unhighlightAll();
    updateStatusUI(false);
  }

  function updateStatusUI(active) {
    if (active) {
      recordingStatus?.classList.remove('hidden');
      waveAnim?.classList.remove('hidden');
      waveAnim?.classList.add('flex');
    } else {
      recordingStatus?.classList.add('hidden');
      waveAnim?.classList.add('hidden');
      waveAnim?.classList.remove('flex');
    }
  }

  function highlightField(fieldId) {
    unhighlightAll();
    const el = document.getElementById(fieldId);
    if (el) el.classList.add('voice-active');

    document.querySelectorAll('.field-mic').forEach(btn => {
      if (btn.dataset.target === fieldId) {
        btn.classList.add('recording');
        btn.innerHTML = '<svg class="w-4 h-4 text-red-500 animate-pulse" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"/></svg>'; 
      } else {
        btn.classList.remove('recording');
        btn.innerHTML = '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8h-2a5 5 0 01-10 0H3a7.001 7.001 0 006 6.93V17H6v2h8v-2h-3v-2.07z" clip-rule="evenodd"/></svg>';
      }
    });
  }

  function unhighlightAll() {
    document.querySelectorAll('.form-textarea').forEach(ta => ta.classList.remove('voice-active'));
    document.querySelectorAll('.field-mic').forEach(btn => {
      btn.classList.remove('recording');
      btn.innerHTML = '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8h-2a5 5 0 01-10 0H3a7.001 7.001 0 006 6.93V17H6v2h8v-2h-3v-2.07z" clip-rule="evenodd"/></svg>';
    });
  }

  // Global Language Setter
  window.setLang = function (lang) {
    selectedLang = lang;
    localStorage.setItem('meditrack_lang', lang);
    if (recognition) {
      recognition.lang = lang;
      if (isRunning) {
        // Stop current recognition, `onend` will automatically restart it because `isRunning` is true
        try { recognition.stop(); } catch(e) {}
      }
    }
    // UI Toggle Update
    const btnEn = document.getElementById('lang-en');
    const btnAr = document.getElementById('lang-ar');
    
    if (btnEn && btnAr) {
      if (lang === 'en-US') {
        btnEn.className = 'px-5 py-2.5 bg-primary text-white font-bold transition-all';
        btnAr.className = 'px-5 py-2.5 bg-white text-muted hover:bg-gray-50 font-bold transition-all';
      } else {
        btnAr.className = 'px-5 py-2.5 bg-primary text-white font-bold transition-all';
        btnEn.className = 'px-5 py-2.5 bg-white text-muted hover:bg-gray-50 font-bold transition-all';
      }
    }
  };

  // Button Listeners
  document.querySelectorAll('.field-mic').forEach(btn => {
    btn.addEventListener('click', () => {
      startRecording(btn.dataset.target);
    });
  });

  // Init lang UI from storage
  window.addEventListener('DOMContentLoaded', () => {
    window.setLang(selectedLang);
  });

  // Global Hotkey for Language Toggling (Ctrl + Space)
  document.addEventListener('keydown', function(e) {
      if (e.ctrlKey && e.code === 'Space') {
          e.preventDefault();
          const currentLang = localStorage.getItem('meditrack_lang') || 'en-US';
          const newLang = currentLang === 'en-US' ? 'ar-EG' : 'en-US';
          if (window.setLang) {
              window.setLang(newLang);
          }
      }
      if (e.key === 'Escape' && isRunning) stopAll();
  });

})();
