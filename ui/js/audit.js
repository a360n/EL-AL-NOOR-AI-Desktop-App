/* ==========================================================================
   EL AL-NOOR AI - AI AUDIT & ACCURACY ENGINE CONTROLLER
   ========================================================================== */

function initAuditView() {
    loadAuditData();
    setupAuditExports();
}

async function loadAuditData() {
    const tbody = document.getElementById('auditTableBody');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:30px; color:#888;"><i class="fas fa-spinner fa-spin"></i> جاري تحميل بيانات التدقيق...</td></tr>`;

    try {
        const [statsRes, inspRes] = await Promise.all([
            fetch('/api/stats'),
            fetch('/api/inspections?limit=100')
        ]);

        const stats = await statsRes.json();
        const inspections = await inspRes.json();

        // Update Audit KPI Cards
        const totalEl = document.getElementById('auditTotal');
        const matchEl = document.getElementById('auditMatchCount');
        const mismatchEl = document.getElementById('auditMismatchCount');
        const accEl = document.getElementById('auditAccuracyRate');

        if (totalEl) totalEl.textContent = stats.total || 0;
        if (matchEl) matchEl.textContent = stats.match_count || 0;
        if (mismatchEl) mismatchEl.textContent = stats.mismatch_count || 0;
        if (accEl) accEl.textContent = `${stats.accuracy_rate || 100}%`;

        renderAuditTable(inspections.items);
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:30px; color:#e74c3c;"><i class="fas fa-exclamation-triangle"></i> تعذر تحميل سجل التدقيق</td></tr>`;
    }
}

function renderAuditTable(items) {
    const tbody = document.getElementById('auditTableBody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:40px; color:#888;"><i class="fas fa-clipboard-check" style="font-size:2rem; opacity:0.5; margin-bottom:10px;"></i><br>لا توجد بيانات تدقيق حتى الآن</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => {
        const isMatch = item.match_status === 'MATCH';
        const matchBadge = isMatch
            ? `<span style="color:#2ecc71; font-weight:700;"><i class="fas fa-check-circle"></i> ${t('match_yes')}</span>`
            : `<span style="color:#dc3545; font-weight:700;"><i class="fas fa-times-circle"></i> ${t('match_no')}</span>`;

        const aiDefects = item.ai_defects && item.ai_defects.length > 0
            ? item.ai_defects.join(', ')
            : 'سليم (Healthy)';

        let operatorNotes = '-';
        if (!isMatch && item.manual_correction) {
            const corr = item.manual_correction;
            const cells = corr.defective_cells ? corr.defective_cells.join(', ') : 'بدون';
            operatorNotes = `<strong>النوع:</strong> ${corr.defect_type || 'Unknown'} | <strong>الخلايا:</strong> ${cells}`;
        } else {
            operatorNotes = item.human_status || 'سليم';
        }

        return `
            <tr>
                <td><strong>${item.panel_id}</strong><br><small style="color:#888;">${item.serial_number || '-'}</small></td>
                <td>${matchBadge}</td>
                <td>
                    <div style="font-size:0.85rem;">
                        <span style="color:var(--accent); font-weight:700;">${item.ai_status}</span>
                        <div style="color:#A0AEC0; font-size:0.75rem; margin-top:2px;">الخلايا: ${aiDefects}</div>
                    </div>
                </td>
                <td>
                    <div style="font-size:0.85rem; color:#E2E8F0;">
                        ${operatorNotes}
                        <div style="color:#888; font-size:0.72rem; margin-top:2px;">المشغل: ${item.operator_name || '-'} (${item.timestamp})</div>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function setupAuditExports() {
    const btnExport = document.getElementById('btnExportAudit');
    const btnExportPDF = document.getElementById('btnExportAuditPDF');

    if (btnExport) {
        btnExport.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/inspections?limit=500');
                const data = await res.json();
                generateAuditHtmlReport(data.items);
            } catch (err) {
                showToast('Audit export failed', 'error');
            }
        });
    }

    if (btnExportPDF) {
        btnExportPDF.addEventListener('click', () => {
            window.print();
        });
    }
}

function generateAuditHtmlReport(items) {
    const reportHtml = `
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>سجل تدقيق وتطابق الذكاء الاصطناعي - معمل النور</title>
            <style>
                body { font-family: 'Cairo', sans-serif; padding: 30px; color: #111; direction: rtl; }
                h1 { color: #0D8A95; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: right; }
                th { background-color: #f4f4f4; color: #333; }
                .match { color: green; font-weight: bold; }
                .mismatch { color: red; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>معمل النور للألواح الشمسية - سجل تدقيق مطابقة الذكاء الاصطناعي (AI Audit)</h1>
            <p>تاريخ الاستخراج: ${new Date().toLocaleString('ar')}</p>
            <table>
                <thead>
                    <tr>
                        <th>رقم اللوحة</th>
                        <th>المطابقة للواقع</th>
                        <th>تشخيص الذكاء الاصطناعي</th>
                        <th>قرار وتصحيح المشغل</th>
                        <th>التاريخ والمراقب</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map(i => `
                        <tr>
                            <td>${i.panel_id}</td>
                            <td class="${i.match_status === 'MATCH' ? 'match' : 'mismatch'}">${i.match_status}</td>
                            <td>${i.ai_status} (${(i.ai_defects || []).join(', ')})</td>
                            <td>${i.human_status}</td>
                            <td>${i.operator_name} - ${i.timestamp}</td>
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
    a.download = `EL_ALNOOR_AI_Audit_${Date.now()}.html`;
    a.click();
    URL.revokeObjectURL(url);
}
