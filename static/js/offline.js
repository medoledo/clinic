/**
 * offline.js — MediTrack Offline Mode
 * Network detection, IndexedDB storage, background sync
 */
(function () {
    'use strict';

    const DB_NAME = 'meditrack_offline';
    const DB_VERSION = 1;
    const STORE_NAME = 'pending_visits';

    // ── UI Elements ──
    const offlineBanner = document.getElementById('offline-banner');
    const onlineBanner = document.getElementById('online-banner');
    const networkDot = document.getElementById('network-dot');
    const networkDotTop = document.getElementById('network-dot-top');
    const networkLabel = document.getElementById('network-label');
    const pendingBadge = document.getElementById('pending-badge');
    const pendingBadgeMobile = document.getElementById('pending-badge-mobile');

    // ── IndexedDB Helper ──
    let db = null;

    function openDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = e => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    const store = db.createObjectStore(STORE_NAME, { keyPath: 'offline_id', autoIncrement: true });
                    store.createIndex('patient_id', 'patient_id', { unique: false });
                    store.createIndex('synced', 'synced', { unique: false });
                }
            };
            req.onsuccess = e => resolve(e.target.result);
            req.onerror = e => reject(e.target.error);
        });
    }

    async function getDB() {
        if (!db) db = await openDB();
        return db;
    }

    async function saveVisit(visitData) {
        const db = await getDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const record = { ...visitData, synced: false, created_at: new Date().toISOString() };
            const req = store.add(record);
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function getAllPending() {
        const db = await getDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const idx = store.index('synced');
            const req = idx.getAll(false);
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function markSynced(offlineId) {
        const db = await getDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const getReq = store.get(offlineId);
            getReq.onsuccess = () => {
                const rec = getReq.result;
                if (rec) {
                    rec.synced = true;
                    store.put(rec);
                }
                resolve();
            };
            getReq.onerror = () => reject(getReq.error);
        });
    }

    async function syncAll() {
        const pending = await getAllPending();
        if (pending.length === 0) return;

        showSyncProgress(`Syncing ${pending.length} pending visit${pending.length > 1 ? 's' : ''}...`);
        let successCount = 0;
        let failCount = 0;

        for (const visit of pending) {
            try {
                const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
                const res = await fetch('/sync-offline-visit/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ ...visit, offline_id: visit.offline_id }),
                });
                if (res.ok) {
                    await markSynced(visit.offline_id);
                    successCount++;
                } else {
                    failCount++;
                }
            } catch (e) {
                failCount++;
            }
        }

        if (failCount === 0) {
            showSyncProgress(`✅ All ${successCount} visit${successCount > 1 ? 's' : ''} synced successfully`);
        } else {
            showSyncProgress(`⚠️ ${successCount} synced, ${failCount} failed. Will retry.`);
        }
        setTimeout(hideSyncProgress, 4000);
        updatePendingBadge();
    }

    function showSyncProgress(msg) {
        const el = document.getElementById('sync-progress');
        if (el) { el.textContent = msg; el.classList.remove('hidden'); }
        if (onlineBanner) { onlineBanner.textContent = msg; onlineBanner.style.display = 'block'; }
        setTimeout(() => { if (onlineBanner) onlineBanner.style.display = 'none'; }, 3000);
    }
    function hideSyncProgress() {
        const el = document.getElementById('sync-progress');
        if (el) el.classList.add('hidden');
    }

    async function updatePendingBadge() {
        try {
            const pending = await getAllPending();
            const count = pending.length;
            [pendingBadge, pendingBadgeMobile].forEach(badge => {
                if (!badge) return;
                if (count > 0) {
                    badge.textContent = count;
                    badge.classList.remove('hidden');
                } else {
                    badge.classList.add('hidden');
                }
            });
        } catch (e) { }
    }

    // ── Network Status ──
    function setOnline() {
        if (offlineBanner) offlineBanner.style.display = 'none';
        if (onlineBanner) { onlineBanner.style.display = 'block'; setTimeout(() => { onlineBanner.style.display = 'none'; }, 3000); }
        [networkDot, networkDotTop].forEach(d => {
            if (d) { d.classList.remove('bg-danger'); d.classList.add('bg-success'); }
        });
        if (networkLabel) networkLabel.textContent = 'Online';
        syncAll();
    }

    function setOffline() {
        if (offlineBanner) { offlineBanner.style.display = 'block'; setTimeout(() => { offlineBanner.style.display = 'none'; }, 3000); }
        if (onlineBanner) onlineBanner.style.display = 'none';
        [networkDot, networkDotTop].forEach(d => {
            if (d) { d.classList.remove('bg-success'); d.classList.add('bg-danger'); }
        });
        if (networkLabel) networkLabel.textContent = 'Offline';
    }

    window.addEventListener('online', setOnline);
    window.addEventListener('offline', setOffline);

    if (!navigator.onLine) setOffline();

    // ── Expose API ──
    window.offlineDB = { saveVisit, getAllPending, markSynced, syncAll };

    // Initial badge update
    updatePendingBadge();

    // Register service worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => { });
    }
})();
