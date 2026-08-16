/* ==========================================================================
   EL AL-NOOR AI - MAIN APPLICATION CORE CONTROLLER & ROUTER (app.js)
   ========================================================================== */

let socket = null;
let currentActiveView = 'liveView';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Localization
    setLanguage(currentLanguage);

    // 2. Setup Navigation Tabs
    setupNavigation();

    // 3. Setup Clock
    startClock();

    // 4. Initialize Sub-modules
    initLiveInspection();
    initHistoryView();
    initAuditView();
    initOperatorsView();
    initSettingsView();

    // 5. Connect WebSocket
    connectLiveWebSocket();

    // 6. Language Toggle Button
    const langBtn = document.getElementById('langToggleBtn');
    if (langBtn) {
        langBtn.addEventListener('click', () => {
            toggleLanguage();
        });
    }

    // 7. Initial Fetch of Latest Panel and Stats
    refreshDashboardStats();
    fetchInitialPanel();
});

// ----------------- WEBSOCKET CONNECTION -----------------

function connectLiveWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/live`;

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("🟢 Connected to EL AL-NOOR AI Real-time Engine.");
        updateWatcherStatusBadge(true);
    };

    socket.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleIncomingEvent(msg);
        } catch (err) {
            console.error("Error parsing WebSocket event:", err);
        }
    };

    socket.onclose = () => {
        console.warn("🔴 WebSocket disconnected. Reconnecting in 3s...");
        updateWatcherStatusBadge(false);
        setTimeout(connectLiveWebSocket, 3000);
    };

    socket.onerror = (err) => {
        console.error("WebSocket error:", err);
        socket.close();
    };
}

function handleIncomingEvent(msg) {
    if (msg.type === 'NEW_INSPECTION') {
        showToast(`تم استقبال لوح جديد [${msg.data.panel_id}] وتم تحليله بالـ AI!`, 'success');
        displayInspection(msg.data);
        if (msg.stats) updateStatsUI(msg.stats);
        if (currentActiveView === 'historyView') loadHistoryData();
        if (currentActiveView === 'auditView') loadAuditData();
    } else if (msg.type === 'INIT_STATE') {
        updateWatcherStatusBadge(msg.watcher_running);
        if (msg.stats) updateStatsUI(msg.stats);
        if (msg.latest_inspection && !currentInspectionData) {
            displayInspection(msg.latest_inspection);
        }
    } else if (msg.type === 'DECISION_UPDATED') {
        if (msg.stats) updateStatsUI(msg.stats);
        if (currentActiveView === 'historyView') loadHistoryData();
        if (currentActiveView === 'auditView') loadAuditData();
    } else if (msg.type === 'DATABASE_CLEARED') {
        if (msg.stats) updateStatsUI(msg.stats);
        if (currentActiveView === 'historyView') loadHistoryData();
        if (currentActiveView === 'auditView') loadAuditData();
    }
}

function updateWatcherStatusBadge(isRunning) {
    const dot = document.getElementById('watcherStatusDot');
    const text = document.getElementById('watcherStatusText');
    if (dot) {
        dot.className = isRunning ? 'status-dot' : 'status-dot stopped';
    }
    if (text) {
        text.textContent = isRunning ? t('sys_status_listening') : t('sys_status_stopped');
    }
}

// ----------------- NAVIGATION ROUTER -----------------

function setupNavigation() {
    const tabBtns = document.querySelectorAll('.nav-tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetViewId = btn.getAttribute('data-target');
            if (targetViewId) switchNavTab(targetViewId);
        });
    });
}

function switchNavTab(viewId) {
    currentActiveView = viewId;

    // Update Tab Buttons
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        if (btn.getAttribute('data-target') === viewId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Switch View Containers
    document.querySelectorAll('.view-section').forEach(view => {
        if (view.id === viewId) {
            view.style.display = 'block';
        } else {
            view.style.display = 'none';
        }
    });

    // Refresh view data if needed
    if (viewId === 'historyView') loadHistoryData();
    if (viewId === 'auditView') loadAuditData();
    if (viewId === 'operatorsView') loadOperatorsData();
    if (viewId === 'settingsView') loadSettingsData();
}

// ----------------- STATS & INITIAL FETCH -----------------

async function refreshDashboardStats() {
    try {
        const res = await fetch('/api/stats');
        const stats = await res.json();
        updateStatsUI(stats);
    } catch (err) {
        console.error("Error refreshing stats:", err);
    }
}

function updateStatsUI(stats) {
    if (!stats) return;

    const totalEl = document.getElementById('statTotal');
    const passCountEl = document.getElementById('statPassCount');
    const passPctEl = document.getElementById('statPassPercent');
    const failCountEl = document.getElementById('statFailCount');
    const failPctEl = document.getElementById('statFailPercent');
    const disCountEl = document.getElementById('statDisagreementCount');

    if (totalEl) totalEl.textContent = stats.total || 0;
    if (passCountEl) passCountEl.textContent = stats.pass_count || 0;
    if (passPctEl) passPctEl.textContent = `${stats.pass_percent || 0}% ${t('of_total')}`;
    if (failCountEl) failCountEl.textContent = stats.fail_count || 0;
    if (failPctEl) failPctEl.textContent = `${stats.fail_percent || 0}% ${t('of_total')}`;
    if (disCountEl) disCountEl.textContent = stats.mismatch_count || 0;
}

async function fetchInitialPanel() {
    try {
        const res = await fetch('/api/inspections/latest');
        if (res.ok) {
            const data = await res.json();
            displayInspection(data);
        }
    } catch (e) {
        // No panels yet
    }
}

// ----------------- UTILITIES & TOASTS -----------------

function startClock() {
    const timeDisplay = document.getElementById('timeDisplaySpan');
    function update() {
        const now = new Date();
        if (timeDisplay) {
            timeDisplay.textContent = now.toLocaleTimeString('en-GB');
        }
    }
    update();
    setInterval(update, 1000);
}

function showToast(message, type = 'info') {
    let container = document.getElementById('appToastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'appToastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `app-toast ${type}`;

    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'error') icon = 'exclamation-circle';
    if (type === 'warning') icon = 'exclamation-triangle';

    toast.innerHTML = `<i class="fas fa-${icon}"></i> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
