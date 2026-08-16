/* ==========================================================================
   EL AL-NOOR AI - INSPECTION HISTORY & QUALITY REPORTS CONTROLLER
   ========================================================================== */

let historyPage = 0;
const historyLimit = 25;

function initHistoryView() {
    setupHistoryFilters();
    setupHistoryExports();
    setupDetailModal();
    loadHistoryData();
}

function setupHistoryFilters() {
    const searchInput = document.getElementById('historySearchInput');
    const statusFilter = document.getElementById('historyStatusFilter');
    const matchFilter = document.getElementById('historyMatchFilter');

    let debounceTimer;
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                historyPage = 0;
                loadHistoryData();
            }, 300);
        });
    }

    if (statusFilter) {
        statusFilter.addEventListener('change', () => {
            historyPage = 0;
            loadHistoryData();
        });
    }

    if (matchFilter) {
        matchFilter.addEventListener('change', () => {
            historyPage = 0;
            loadHistoryData();
        });
    }
}

async function loadHistoryData() {
    const q = document.getElementById('historySearchInput')?.value || '';
    const status = document.getElementById('historyStatusFilter')?.value || 'ALL';
    const match = document.getElementById('historyMatchFilter')?.value || 'ALL';

    const tbody = document.getElementById('qualityTableBody');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:30px; color:#888;"><i class="fas fa-spinner fa-spin" style="font-size:1.5rem; color:var(--primary); margin-bottom:8px;"></i><br>جاري تحميل سجلات الجودة...</td></tr>`;

    try {
        const offset = historyPage * historyLimit;
        const res = await fetch(`/api/inspections?q=${encodeURIComponent(q)}&status=${status}&match=${match}&limit=${historyLimit}&offset=${offset}`);
        const data = await res.json();

        renderHistoryTable(data.items, data.total);
        renderPagination(data.total);
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:30px; color:#e74c3c;"><i class="fas fa-exclamation-triangle"></i> حدث خطأ أثناء تحميل السجلات</td></tr>`;
    }
}

function renderHistoryTable(items, total) {
    const tbody = document.getElementById('qualityTableBody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:40px; color:#888;"><i class="fas fa-folder-open" style="font-size:2rem; margin-bottom:10px; opacity:0.5;"></i><br>لا توجد سجلات فحص مطابقة للبحث</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => {
        const isPass = item.human_status && item.human_status.includes('PASS');
        const statusBadge = isPass
            ? `<span class="badge badge-pass" style="background:#2ecc71; color:#fff; padding:4px 8px; border-radius:3px; font-weight:700; font-size:0.75rem;">PASS (سليم)</span>`
            : `<span class="badge badge-fail" style="background:#e74c3c; color:#fff; padding:4px 8px; border-radius:3px; font-weight:700; font-size:0.75rem;">FAIL (معيب)</span>`;

        const isMatch = item.match_status === 'MATCH';
        const matchBadge = isMatch
            ? `<span style="color:#2ecc71; font-weight:700;"><i class="fas fa-check-circle"></i> مطابق</span>`
            : `<span style="color:#e74c3c; font-weight:700;"><i class="fas fa-times-circle"></i> غير مطابق</span>`;

        const defects = item.human_defects || [];
        const defectStr = defects.length > 0
            ? defects.slice(0, 3).join(', ') + (defects.length > 3 ? ` (+${defects.length - 3})` : '')
            : '<span style="color:#888;">بدون عيوب</span>';

        return `
            <tr style="cursor:pointer;" onclick="openDetailModal(${item.id})">
                <td><strong>${item.panel_id || '-'}</strong></td>
                <td><code style="background:rgba(255,255,255,0.06); padding:2px 6px; border-radius:3px;">${item.serial_number || '-'}</code></td>
                <td>${statusBadge}</td>
                <td>${matchBadge}</td>
                <td>${defectStr}</td>
                <td><span style="font-size:0.82rem; font-weight:600;">${item.operator_action || 'Pass to Production'}</span></td>
                <td>${item.operator_name || '-'}</td>
                <td style="font-size:0.8rem; color:#888;">${item.timestamp || '-'}</td>
                <td>
                    <button class="btn btn-dark" style="padding:4px 10px; font-size:0.75rem;" onclick="event.stopPropagation(); openDetailModal(${item.id})">
                        <i class="fas fa-eye"></i> معاينة
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderPagination(total) {
    const totalPages = Math.ceil(total / historyLimit);
    const container = document.getElementById('historyPagination');
    if (!container) return;

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 0;">
            <span style="font-size:0.82rem; color:#888;">عرض الصفحة ${historyPage + 1} من ${totalPages} (إجمالي ${total} سجل)</span>
            <div style="display:flex; gap:6px;">
                <button class="btn btn-dark" ${historyPage === 0 ? 'disabled' : ''} onclick="changeHistoryPage(${historyPage - 1})">
                    <i class="fas fa-chevron-right"></i> السابق
                </button>
                <button class="btn btn-dark" ${historyPage >= totalPages - 1 ? 'disabled' : ''} onclick="changeHistoryPage(${historyPage + 1})">
                    التالي <i class="fas fa-chevron-left"></i>
                </button>
            </div>
        </div>
    `;
}

function changeHistoryPage(p) {
    historyPage = p;
    loadHistoryData();
}

// ----------------- DETAIL COMPARISON MODAL -----------------

function setupDetailModal() {
    const modal = document.getElementById('detailModal');
    const btnClose = document.getElementById('closeDetailModal');
    if (btnClose) btnClose.addEventListener('click', () => modal.classList.remove('active'));
}

async function openDetailModal(inspId) {
    const modal = document.getElementById('detailModal');
    if (!modal) return;

    try {
        const res = await fetch(`/api/inspections/${inspId}`);
        const data = await res.json();

        document.getElementById('modalPanelId').textContent = data.panel_id || '-';
        document.getElementById('modalSerial').textContent = data.serial_number || '-';
        document.getElementById('modalTimestamp').textContent = data.timestamp || '-';
        document.getElementById('modalOperator').textContent = data.operator_name || '-';
        document.getElementById('modalMatchStatus').textContent = data.match_status === 'MATCH' ? 'مطابق للواقع' : 'غير مطابق';
        document.getElementById('modalAction').textContent = data.operator_action || '-';

        const humanImg = document.getElementById('modalHumanImg');
        const aiImg = document.getElementById('modalAiImg');

        if (humanImg && data.human_overlay_image_path) {
            humanImg.src = `/api/image?path=${encodeURIComponent(data.human_overlay_image_path)}&t=${Date.now()}`;
        }
        if (aiImg && data.ai_overlay_image_path) {
            aiImg.src = `/api/image?path=${encodeURIComponent(data.ai_overlay_image_path)}&t=${Date.now()}`;
        }

        modal.classList.add('active');
    } catch (err) {
        console.error(err);
        showToast('Error loading panel detail', 'error');
    }
}

// ----------------- EXPORT & CLEAR -----------------

function setupHistoryExports() {
    const btnExport = document.getElementById('btnExport');
    const btnExportPDF = document.getElementById('btnExportPDF');
    const btnClear = document.getElementById('btnClear');

    if (btnExport) {
        btnExport.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/inspections?limit=500');
                const data = await res.json();
                generateHtmlReport(data.items);
            } catch (err) {
                showToast('Export failed', 'error');
            }
        });
    }

    if (btnExportPDF) {
        btnExportPDF.addEventListener('click', () => {
            window.print();
        });
    }

    if (btnClear) {
        btnClear.addEventListener('click', async () => {
            if (confirm(t('delete_confirm'))) {
                try {
                    await fetch('/api/inspections/clear', { method: 'DELETE' });
                    showToast('تم مسح كافة السجلات بنجاح', 'success');
                    loadHistoryData();
                    refreshDashboardStats();
                } catch (e) {
                    showToast('Error clearing records', 'error');
                }
            }
        });
    }
}

function generateHtmlReport(items) {
    const reportHtml = `
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>تقرير فحص جودة الألواح الشمسية - معمل النور</title>
            <style>
                body { font-family: 'Cairo', sans-serif; padding: 30px; color: #111; direction: rtl; }
                h1 { color: #0D8A95; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: right; }
                th { background-color: #f4f4f4; color: #333; }
                .pass { color: green; font-weight: bold; }
                .fail { color: red; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>معمل النور للألواح الشمسية - تقرير فحص الجودة الشامل</h1>
            <p>تاريخ استخراج التقرير: ${new Date().toLocaleString('ar')}</p>
            <p>إجمالي الألواح المفحوصة: ${items.length}</p>
            <table>
                <thead>
                    <tr>
                        <th>رقم اللوحة</th>
                        <th>الرقم التسلسلي</th>
                        <th>التشخيص البشري</th>
                        <th>تشخيص الذكاء الاصطناعي</th>
                        <th>المطابقة</th>
                        <th>المسار</th>
                        <th>المراقب</th>
                        <th>التاريخ والوقت</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map(i => `
                        <tr>
                            <td>${i.panel_id}</td>
                            <td>${i.serial_number}</td>
                            <td class="${i.human_status.includes('PASS') ? 'pass' : 'fail'}">${i.human_status}</td>
                            <td class="${i.ai_status.includes('PASS') ? 'pass' : 'fail'}">${i.ai_status}</td>
                            <td>${i.match_status}</td>
                            <td>${i.operator_action}</td>
                            <td>${i.operator_name}</td>
                            <td>${i.timestamp}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </body>
        </html>
    `;

    const blob = new Blob([reportHtml], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `EL_ALNOOR_Quality_Report_${Date.now()}.html`;
    a.click();
    URL.revokeObjectURL(url);
}
