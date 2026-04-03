/**
 * shortcuts.js — MediTrack Keyboard Shortcuts
 */
(function () {
    'use strict';

    document.addEventListener('keydown', function (e) {
        const ctrl = e.ctrlKey || e.metaKey;
        if (!ctrl) return;

        switch (e.key.toLowerCase()) {
            case 'm':
                e.preventDefault();
                if (window._voiceToggle) window._voiceToggle();
                break;
            case 's':
                // Only prevent default on visit form page
                if (document.getElementById('visit-form')) {
                    e.preventDefault();
                    const btn = document.getElementById('save-visit-btn');
                    if (btn && !btn.disabled) btn.click();
                }
                break;
            case 'f':
                if (document.getElementById('dashboard-search')) {
                    e.preventDefault();
                    if (window._focusSearch) window._focusSearch();
                }
                break;
        }
    });
})();
