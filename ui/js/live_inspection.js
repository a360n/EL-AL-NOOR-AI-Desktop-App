/* ==========================================================================
   EL AL-NOOR AI - LIVE INSPECTION & DUAL COMPARISON VIEW CONTROLLER
   ========================================================================== */

let currentInspectionData = null;
let currentZoom = 1.0;
let isPanning = false;
let startX = 0, startY = 0;
let translateX = 0, translateY = 0;
let manualDefectCells = new Set();

function initLiveInspection() {
    setupZoomControls();
    setupDecisionForm();
    setupMatrixModal();
    setupStarRating();
}

// ----------------- DUAL VIEW & ZOOM ENGINE -----------------

function setupZoomControls() {
    const containers = [
        document.getElementById('humanZoomContainer'),
        document.getElementById('aiZoomContainer')
    ];

    containers.forEach(container => {
        if (!container) return;

        container.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY < 0 ? 0.15 : -0.15;
            setZoom(currentZoom + delta);
        }, { passive: false });

        container.addEventListener('mousedown', (e) => {
            if (currentZoom <= 1.0) return;
            isPanning = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            container.style.cursor = 'grabbing';
        });

        window.addEventListener('mouseup', () => {
            isPanning = false;
            if (container) container.style.cursor = currentZoom > 1.0 ? 'grab' : 'default';
        });

        window.addEventListener('mousemove', (e) => {
            if (!isPanning) return;
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            applyTransform();
        });
    });

    const btnReset = document.getElementById('btnZoomReset');
    if (btnReset) {
        btnReset.addEventListener('click', () => {
            setZoom(1.0);
            translateX = 0;
            translateY = 0;
            applyTransform();
        });
    }

    const btnIn = document.getElementById('btnZoomIn');
    if (btnIn) btnIn.addEventListener('click', () => setZoom(currentZoom + 0.25));

    const btnOut = document.getElementById('btnZoomOut');
    if (btnOut) btnOut.addEventListener('click', () => setZoom(currentZoom - 0.25));
}

function setZoom(val) {
    currentZoom = Math.min(Math.max(val, 0.75), 4.0);
    if (currentZoom === 1.0) {
        translateX = 0;
        translateY = 0;
    }
    const zoomValEl = document.getElementById('zoomVal');
    if (zoomValEl) zoomValEl.textContent = `${Math.round(currentZoom * 100)}%`;
    applyTransform();
}

function applyTransform() {
    const humanImg = document.getElementById('humanDisplayImage');
    const aiImg = document.getElementById('aiDisplayImage');
    const transformStr = `translate(${translateX}px, ${translateY}px) scale(${currentZoom})`;

    if (humanImg) humanImg.style.transform = transformStr;
    if (aiImg) aiImg.style.transform = transformStr;
}

// ----------------- DISPLAY INSPECTION DATA -----------------

function displayInspection(panelData) {
    if (!panelData) return;
    currentInspectionData = panelData;

    // Switch placeholders to active view
    const formPlaceholder = document.getElementById('formPlaceholder');
    const decisionForm = document.getElementById('operatorDecisionForm');
    if (formPlaceholder) formPlaceholder.style.display = 'none';
    if (decisionForm) decisionForm.style.display = 'flex';

    // Panel info fields
    const screenPanelId = document.getElementById('screenPanelId');
    const screenSerial = document.getElementById('screenPanelSerial');
    const formSerial = document.getElementById('formPanelSerial');
    const aiConfidence = document.getElementById('aiDiagnosisConfidence');
    const aiDefectsList = document.getElementById('aiDiagnosisDefects');
    const statusBadge = document.getElementById('statusBadge');

    if (screenPanelId) screenPanelId.textContent = panelData.panel_id || 'ANM-READY';
    if (screenSerial) screenSerial.textContent = panelData.serial_number || 'ID-READY';
    if (formSerial) formSerial.textContent = panelData.serial_number || 'ANM XXXXXXXXX';

    // AI Confidence & Defects
    const confVal = panelData.ai_confidence || 0.0;
    if (aiConfidence) {
        aiConfidence.textContent = `${t('confidence')}: ${confVal.toFixed(1)}%`;
    }

    const aiDefects = panelData.ai_defects || [];
    if (aiDefectsList) {
        if (aiDefects.length > 0) {
            aiDefectsList.innerHTML = aiDefects.map(d => `<span class="badge badge-defect" style="background:#e74c3c; color:#fff; padding:2px 6px; border-radius:3px; font-size:0.75rem; margin-right:4px;">${d}</span>`).join(' ');
        } else {
            aiDefectsList.innerHTML = `<span style="color:#2ecc71; font-weight:700;"><i class="fas fa-check-circle"></i> ${t('no_defects')}</span>`;
        }
    }

    // Set Images
    const humanImg = document.getElementById('humanDisplayImage');
    const aiImg = document.getElementById('aiDisplayImage');

    if (humanImg && panelData.human_overlay_image_path) {
        humanImg.src = `/api/image?path=${encodeURIComponent(panelData.human_overlay_image_path)}&t=${Date.now()}`;
    }
    if (aiImg && panelData.ai_overlay_image_path) {
        aiImg.src = `/api/image?path=${encodeURIComponent(panelData.ai_overlay_image_path)}&t=${Date.now()}`;
    }

    // Reset Zoom & Pan
    setZoom(1.0);
    translateX = 0;
    translateY = 0;
    applyTransform();

    // Default match state
    const isDefective = (panelData.human_status && panelData.human_status.includes('FAIL')) || (panelData.ai_status && panelData.ai_status.includes('FAIL'));
    if (statusBadge) {
        statusBadge.textContent = isDefective ? 'معيب (FAIL)' : 'سليم (PASS)';
        statusBadge.style.color = isDefective ? '#e74c3c' : '#2ecc71';
        statusBadge.style.borderColor = isDefective ? '#e74c3c' : '#2ecc71';
    }

    // Set default rating & action
    setRating(panelData.rating || (isDefective ? 0 : 3));
    const repairAction = document.getElementById('repairAction');
    if (repairAction) {
        repairAction.value = isDefective ? 'Repair' : 'Pass to Production';
    }

    // Default Match toggle
    setMatchToggle(panelData.match_status === 'MISMATCH' ? 'no' : 'yes');

    // Play Alert Sound if enabled and defective
    const soundEnabled = localStorage.getItem('sound_alerts') !== 'false';
    if (soundEnabled && isDefective) {
        playBeepAlert();
    }
}

// ----------------- DECISION FORM & MATCH TOGGLE -----------------

function setupDecisionForm() {
    const btnYes = document.getElementById('verifyYes');
    const btnNo = document.getElementById('verifyNo');
    const isAiMatchInput = document.getElementById('isAiMatch');

    if (btnYes) {
        btnYes.addEventListener('click', () => {
            setMatchToggle('yes');
        });
    }

    if (btnNo) {
        btnNo.addEventListener('click', () => {
            setMatchToggle('no');
            openManualCorrectionModal();
        });
    }

    const form = document.getElementById('operatorDecisionForm');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!currentInspectionData || !currentInspectionData.id) {
                showToast(t('waiting_for_stream'), 'warning');
                return;
            }

            const operatorName = document.getElementById('operatorSelect')?.value || 'المهندس/ محمد أحمد';
            const isMatch = isAiMatchInput?.value === 'yes';
            const action = document.getElementById('repairAction')?.value || 'Pass to Production';
            const rating = parseInt(document.getElementById('panelRating')?.value || '0', 10);
            const notes = document.getElementById('decisionNotes')?.value || '';

            const payload = {
                operator_name: operatorName,
                match_status: isMatch ? 'MATCH' : 'MISMATCH',
                operator_action: action,
                rating: rating,
                manual_correction: isMatch ? null : {
                    defect_type: document.getElementById('correctDefectType')?.value || 'Cracks',
                    defective_cells: Array.from(manualDefectCells),
                },
                notes: notes
            };

            try {
                const res = await fetch(`/api/inspections/${currentInspectionData.id}/decision`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await res.json();
                if (result.success) {
                    showToast(t('save_success'), 'success');
                    refreshDashboardStats();
                } else {
                    showToast('Error saving decision', 'error');
                }
            } catch (err) {
                console.error(err);
                showToast('Network error saving decision', 'error');
            }
        });
    }
}

function setMatchToggle(val) {
    const btnYes = document.getElementById('verifyYes');
    const btnNo = document.getElementById('verifyNo');
    const isAiMatchInput = document.getElementById('isAiMatch');

    if (isAiMatchInput) isAiMatchInput.value = val;

    if (val === 'yes') {
        if (btnYes) btnYes.classList.add('active');
        if (btnNo) btnNo.classList.remove('active');
    } else {
        if (btnYes) btnYes.classList.remove('active');
        if (btnNo) btnNo.classList.add('active');
    }
}

// ----------------- STAR RATING -----------------

function setupStarRating() {
    const stars = document.querySelectorAll('#ratingStars i');
    stars.forEach(star => {
        star.addEventListener('click', () => {
            const val = parseInt(star.getAttribute('data-value'), 10);
            setRating(val);
        });
    });
}

function setRating(val) {
    const ratingInput = document.getElementById('panelRating');
    const ratingDesc = document.getElementById('ratingDescription');
    if (ratingInput) ratingInput.value = val;

    const stars = document.querySelectorAll('#ratingStars i');
    stars.forEach((star, idx) => {
        if (idx < val) {
            star.classList.remove('far');
            star.classList.add('fas', 'selected');
        } else {
            star.classList.remove('fas', 'selected');
            star.classList.add('far');
        }
    });

    if (ratingDesc) {
        const descKey = `stars_${val}`;
        ratingDesc.textContent = t(descKey) || `${val} / 3 stars`;
    }
}

// ----------------- 144-CELL MATRIX CORRECTION MODAL -----------------

function setupMatrixModal() {
    const modal = document.getElementById('matrixModal');
    const btnClose = document.getElementById('closeMatrixModal');
    const btnCancel = document.getElementById('cancelMatrixModal');
    const btnConfirm = document.getElementById('confirmMatrixModal');

    if (btnClose) btnClose.addEventListener('click', () => modal.classList.remove('active'));
    if (btnCancel) btnCancel.addEventListener('click', () => modal.classList.remove('active'));

    if (btnConfirm) {
        btnConfirm.addEventListener('click', () => {
            modal.classList.remove('active');
            showToast(`تم حفظ تحديد ${manualDefectCells.size} خلايا معيبة يدوياً`, 'success');
        });
    }
}

function openManualCorrectionModal() {
    const modal = document.getElementById('matrixModal');
    const matrixGrid = document.getElementById('matrixGridContainer');
    if (!modal || !matrixGrid) return;

    matrixGrid.innerHTML = '';
    manualDefectCells.clear();

    // Populate currently detected AI defect cells initially
    if (currentInspectionData && currentInspectionData.ai_defects) {
        currentInspectionData.ai_defects.forEach(c => manualDefectCells.add(c));
    }

    const cols = ['A', 'B', 'C', 'D', 'E', 'F'];

    for (let r = 1; r <= 24; r++) {
        for (let c = 0; c < 6; c++) {
            const cellId = `${cols[c]}${r}`;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'matrix-cell-btn';
            btn.textContent = cellId;

            if (manualDefectCells.has(cellId)) {
                btn.classList.add('selected-defect');
            }

            btn.addEventListener('click', () => {
                if (manualDefectCells.has(cellId)) {
                    manualDefectCells.delete(cellId);
                    btn.classList.remove('selected-defect');
                } else {
                    manualDefectCells.add(cellId);
                    btn.classList.add('selected-defect');
                }
                updateMatrixDefectCount();
            });

            matrixGrid.appendChild(btn);
        }
    }

    updateMatrixDefectCount();
    modal.classList.add('active');
}

function updateMatrixDefectCount() {
    const countEl = document.getElementById('matrixDefectCount');
    if (countEl) {
        countEl.textContent = `${manualDefectCells.size} ${manualDefectCells.size === 1 ? 'خلية' : 'خلايا'}`;
    }
}

// ----------------- SOUND ALERT -----------------

function playBeepAlert() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.25);
    } catch (e) {
        // AudioContext not allowed before user gesture
    }
}
