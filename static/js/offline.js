/**
 * offline.js — MediTrack Network Status Only
 */
(function () {
    'use strict';

    const networkDot = document.getElementById('network-dot');
    const networkDotTop = document.getElementById('network-dot-top');
    const networkLabel = document.getElementById('network-label');
    const onlineBanner = document.getElementById('online-banner');

    function setOnline() {
        if (onlineBanner) {
            onlineBanner.style.display = 'block';
            setTimeout(() => { onlineBanner.style.display = 'none'; }, 3000);
        }
        [networkDot, networkDotTop].forEach(d => {
            if (d) { d.classList.remove('bg-danger'); d.classList.add('bg-success'); }
        });
        if (networkLabel) networkLabel.textContent = 'Online';
    }

    function setOffline() {
        if (onlineBanner) onlineBanner.style.display = 'none';
        [networkDot, networkDotTop].forEach(d => {
            if (d) { d.classList.remove('bg-success'); d.classList.add('bg-danger'); }
        });
        if (networkLabel) networkLabel.textContent = 'Offline';
    }

    window.addEventListener('online', setOnline);
    window.addEventListener('offline', setOffline);

    if (!navigator.onLine) setOffline();
    
    // Minimal API to avoid breaking other scripts that check for it
    window.offlineDB = { 
        saveVisit: () => Promise.resolve(),
        syncAll: () => Promise.resolve(),
        getAllPending: () => Promise.resolve([]) 
    };
})();
