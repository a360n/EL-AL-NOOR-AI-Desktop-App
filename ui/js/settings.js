/* ==========================================================================
   EL AL-NOOR AI - SETTINGS & CONNECTIVITY ENGINE CONTROLLER
   ========================================================================== */

function initSettingsView() {
    loadSettingsData();
    setupSettingsForm();
    setupSimulator();
}

async function loadSettingsData() {
    try {
        const res = await fetch('/api/settings');
        const settings = await res.json();

        const watchInput = document.getElementById('watchFolderInput');
        const outputInput = document.getElementById('outputFolderInput');
        const autoProcessCheck = document.getElementById('autoProcessCheck');
        const soundAlertCheck = document.getElementById('soundAlertCheck');

        if (watchInput && settings.watch_folder) watchInput.value = settings.watch_folder;
        if (outputInput && settings.output_folder) outputInput.value = settings.output_folder;
        if (autoProcessCheck) autoProcessCheck.checked = settings.auto_process !== 'false';
        if (soundAlertCheck) soundAlertCheck.checked = settings.sound_alerts !== 'false';

    } catch (err) {
        console.error('Failed to load settings:', err);
    }
}

function setupSettingsForm() {
    const form = document.getElementById('settingsForm');
    const btnScanNow = document.getElementById('btnScanNow');

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const watch_folder = document.getElementById('watchFolderInput')?.value.trim();
            const output_folder = document.getElementById('outputFolderInput')?.value.trim();
            const auto_process = document.getElementById('autoProcessCheck')?.checked ? 'true' : 'false';
            const sound_alerts = document.getElementById('soundAlertCheck')?.checked ? 'true' : 'false';

            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        watch_folder,
                        output_folder,
                        auto_process,
                        sound_alerts
                    })
                });
                const data = await res.json();
                if (data.success) {
                    localStorage.setItem('sound_alerts', sound_alerts);
                    showToast(t('save_success'), 'success');
                }
            } catch (err) {
                console.error(err);
                showToast('Error saving settings', 'error');
            }
        });
    }

    if (btnScanNow) {
        btnScanNow.addEventListener('click', async () => {
            btnScanNow.disabled = true;
            btnScanNow.innerHTML = `<i class="fas fa-spinner fa-spin"></i> جاري فحص المجلد...`;
            try {
                const res = await fetch('/api/inspections/scan-now', { method: 'POST' });
                const data = await res.json();
                showToast(`تم فحص المجلد ومعالجة ${data.processed_count} ألواح جديدة`, 'success');
                refreshDashboardStats();
            } catch (err) {
                showToast('Scan failed', 'error');
            } finally {
                btnScanNow.disabled = false;
                btnScanNow.innerHTML = `<i class="fas fa-search-plus"></i> ${t('btn_scan_now')}`;
            }
        });
    }
}

function setupSimulator() {
    const btnSimulate = document.getElementById('btnSimulateSample');
    const sampleSelect = document.getElementById('sampleSelect');

    if (btnSimulate) {
        btnSimulate.addEventListener('click', async () => {
            btnSimulate.disabled = true;
            btnSimulate.innerHTML = `<i class="fas fa-spinner fa-spin"></i> جاري البث والتحليل بالـ AI...`;

            const panelName = sampleSelect?.value || '1';

            try {
                const res = await fetch('/api/simulate-sample', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ panel_name: panelName })
                });
                const data = await res.json();
                if (data.success) {
                    showToast(`تم بث ومعالجة اللوح [${data.panel.panel_id}] بنجاح!`, 'success');
                    displayInspection(data.panel);
                    // Switch to live inspection tab
                    switchNavTab('liveView');
                } else {
                    showToast('Simulation failed: ' + (data.detail || 'Unknown error'), 'error');
                }
            } catch (err) {
                console.error(err);
                showToast('Simulation error', 'error');
            } finally {
                btnSimulate.disabled = false;
                btnSimulate.innerHTML = `<i class="fas fa-play"></i> ${t('btn_simulate')}`;
            }
        });
    }
}
