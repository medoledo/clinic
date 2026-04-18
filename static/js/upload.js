/**
 * upload.js — MediTrack File Upload System
 * Drag & drop, image preview, type/size validation, multi-file
 */
(function () {
    'use strict';

    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    if (!dropZone || !fileInput) return;

    const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'application/pdf'];
    const ALLOWED_EXT = ['.jpg', '.jpeg', '.png', '.pdf'];
    const MAX_SIZE = 10 * 1024 * 1024; // 10MB

    let selectedFiles = new DataTransfer();

    // Click to open file picker
    dropZone.addEventListener('click', () => fileInput.click());

    // Drag events
    dropZone.addEventListener('dragover', e => {
        e.preventDefault();
        dropZone.classList.add('border-primary', 'bg-blue-50');
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-primary', 'bg-blue-50');
    });
    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('border-primary', 'bg-blue-50');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', () => {
        handleFiles(fileInput.files);
    });

    function handleFiles(files) {
        Array.from(files).forEach(file => {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (!ALLOWED_EXT.includes(ext)) {
                showError(`"${file.name}": Only JPG, PNG, and PDF files are allowed.`);
                return;
            }
            if (file.size > MAX_SIZE) {
                showError(`"${file.name}": File too large. Please choose a file under 10MB.`);
                return;
            }
            addFileToList(file);
            selectedFiles.items.add(file);
        });
        fileInput.files = selectedFiles.files;
    }

    function addFileToList(file) {
        const id = 'file-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);
        const isImage = file.type.startsWith('image/');
        const item = document.createElement('div');
        item.className = 'file-item card p-4';
        item.id = id;

        item.innerHTML = `
      <div class="flex items-start gap-3">
        <div class="file-preview w-16 h-16 rounded-lg border border-border flex items-center justify-center bg-gray-50 flex-shrink-0 overflow-hidden">
          ${isImage
                ? '<img class="w-full h-full object-cover" alt="" />'
                : '<svg class="w-8 h-8 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>'}
        </div>
        <div class="flex-1 min-w-0 space-y-2">
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold text-textmain truncate">${escHtml(file.name)}</span>
            <span class="text-xs text-muted flex-shrink-0">${formatSize(file.size)}</span>
          </div>
          <input type="text" name="file_title" placeholder="File title (required)" required
            class="form-input !py-2 !text-sm" value="${escHtml(file.name.split('.').slice(0, -1).join('.'))}" />
          <select name="file_type" class="form-input !py-2 !text-sm">
            <option value="lab_result">Lab Result</option>
            <option value="xray">X-Ray</option>
            <option value="prescription">Prescription</option>
            <option value="scan">Scan</option>
            <option value="other" selected>Other</option>
          </select>
          <input type="text" name="file_notes" placeholder="Notes (optional)" class="form-input !py-2 !text-sm" />
        </div>
        <button type="button" onclick="removeFile('${id}', '${escHtml(file.name)}')"
          class="text-danger hover:text-red-700 text-lg font-bold flex-shrink-0 p-1" title="Remove">✕</button>
      </div>
    `;

        // Image preview
        if (isImage) {
            const reader = new FileReader();
            reader.onload = e => {
                const img = item.querySelector('.file-preview img');
                if (img) img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }

        fileList.appendChild(item);
    }

    window.removeFile = function (itemId, fileName) {
        const item = document.getElementById(itemId);
        if (item) item.remove();
        // Rebuild DataTransfer without this file
        const dt = new DataTransfer();
        Array.from(selectedFiles.files).forEach(f => {
            if (f.name !== fileName) dt.items.add(f);
        });
        selectedFiles = dt;
        fileInput.files = selectedFiles.files;
    };

    function showError(msg) {
        const err = document.createElement('div');
        err.className = 'p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm font-medium mt-2';
        err.textContent = msg;
        dropZone.parentElement.insertBefore(err, dropZone.nextSibling);
        setTimeout(() => err.remove(), 5000);
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function escHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ── #12 Upload progress bar ──────────────────────────────────────────────
    // Intercepts the parent form's submit and shows a progress bar while
    // the multipart upload is in progress, preventing double-click submissions.
    (function initUploadProgress() {
        var form = document.getElementById('visit-form');
        if (!form) return;

        // Create progress bar container
        var progressWrap = document.createElement('div');
        progressWrap.id = 'upload-progress-wrap';
        progressWrap.style.cssText = 'display:none;margin-top:12px;';
        progressWrap.innerHTML =
            '<div style="font-size:13px;color:#475569;font-weight:600;margin-bottom:6px;" id="upload-progress-label">Uploading files...</div>' +
            '<div style="background:#E2E8F0;border-radius:8px;height:10px;overflow:hidden;">' +
              '<div id="upload-progress-bar" style="height:100%;background:#2563EB;width:0%;transition:width .2s;border-radius:8px;"></div>' +
            '</div>' +
            '<div style="font-size:12px;color:#64748B;margin-top:4px;" id="upload-progress-pct">0%</div>';

        var dropZoneParent = dropZone ? dropZone.parentElement : null;
        if (dropZoneParent) dropZoneParent.appendChild(progressWrap);

        // Only intercept if there are files selected
        form.addEventListener('submit', function (e) {
            var fileItems = document.querySelectorAll('#file-list .file-item');
            if (!fileItems.length) return; // no files — let normal submit proceed

            e.preventDefault();
            var submitBtn = document.getElementById('save-visit-btn');
            if (submitBtn) { submitBtn.disabled = true; submitBtn.classList.add('opacity-75'); }

            progressWrap.style.display = 'block';

            var fd = new FormData(form);
            var xhr = new XMLHttpRequest();

            xhr.upload.onprogress = function (ev) {
                if (ev.lengthComputable) {
                    var pct = Math.round((ev.loaded / ev.total) * 100);
                    document.getElementById('upload-progress-bar').style.width = pct + '%';
                    document.getElementById('upload-progress-pct').textContent = pct + '%';
                    if (pct === 100) {
                        document.getElementById('upload-progress-label').textContent = 'Processing...';
                    }
                }
            };

            xhr.onload = function () {
                // Server redirect on success — follow it
                if (xhr.status >= 200 && xhr.status < 400) {
                    window.location.href = xhr.responseURL || '/dashboard/';
                } else {
                    progressWrap.style.display = 'none';
                    if (submitBtn) { submitBtn.disabled = false; submitBtn.classList.remove('opacity-75'); }
                    alert('Upload failed. Please try again.');
                }
            };

            xhr.onerror = function () {
                progressWrap.style.display = 'none';
                if (submitBtn) { submitBtn.disabled = false; submitBtn.classList.remove('opacity-75'); }
                alert('Network error during upload. Please check your connection.');
            };

            xhr.open('POST', form.action || window.location.pathname);
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.send(fd);
        });
    })();
})();
