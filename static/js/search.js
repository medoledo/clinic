/**
 * search.js — MediTrack AJAX Patient Search
 * Debounced, minimum 2 chars, Enter opens first result
 */
(function () {
    'use strict';

    const input = document.getElementById('dashboard-search');
    const results = document.getElementById('search-results');
    if (!input || !results) return;

    let debounceTimer = null;
    let currentResults = [];

    function doSearch(query) {
        if (query.length < 2) {
            results.classList.add('hidden');
            results.innerHTML = '';
            return;
        }

        fetch(`/search-patients/?q=${encodeURIComponent(query)}`)
            .then(r => r.json())
            .then(data => {
                currentResults = data.results || [];
                renderResults(currentResults, query);
            })
            .catch(() => {
                results.innerHTML = '<div class="px-4 py-3 text-sm text-muted">Search unavailable.</div>';
                results.classList.remove('hidden');
            });
    }

    function renderResults(patients, query) {
        if (patients.length === 0) {
            results.innerHTML = `<div class="px-4 py-4 text-sm text-muted text-center">
        No patients found matching "<strong>${escHtml(query)}</strong>"
      </div>`;
        } else {
            results.innerHTML = patients.map((p, i) => `
        <a href="/patients/${p.id}/" class="search-result flex items-center gap-3 px-4 py-3 hover:bg-blue-50 transition-colors border-b border-border last:border-0 block" data-index="${i}">
          <div class="w-9 h-9 rounded-full bg-blue-100 text-primary flex items-center justify-center font-bold text-sm flex-shrink-0">
            ${escHtml(p.name.charAt(0).toUpperCase())}
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-semibold text-sm text-textmain">${highlightMatch(p.name, query)}</div>
            <div class="text-xs text-muted">${p.phone ? highlightMatch(p.phone, query) : 'No phone'}${p.age ? ' · ' + p.age + ' yrs' : ''}</div>
          </div>
          <div class="text-xs text-muted flex-shrink-0">${p.last_visit_date ? 'Last: ' + p.last_visit_date : 'No visits'}</div>
        </a>
      `).join('');
        }
        results.classList.remove('hidden');
    }

    function highlightMatch(text, query) {
        const safe = escHtml(text);
        const safeQ = escHtml(query);
        const re = new RegExp(`(${safeQ.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return safe.replace(re, '<mark class="bg-yellow-100 rounded px-0.5">$1</mark>');
    }

    function escHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        const q = this.value.trim();
        debounceTimer = setTimeout(() => doSearch(q), 300);
    });

    // Enter → open first result
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && currentResults.length > 0) {
            e.preventDefault();
            window.location.href = `/patients/${currentResults[0].id}/`;
        }
        if (e.key === 'Escape') {
            results.classList.add('hidden');
            this.blur();
        }
    });

    // Close on outside click
    document.addEventListener('click', function (e) {
        if (!input.contains(e.target) && !results.contains(e.target)) {
            results.classList.add('hidden');
        }
    });

    // Expose focus for Ctrl+F shortcut
    window._focusSearch = function () { input.focus(); input.select(); };
})();
