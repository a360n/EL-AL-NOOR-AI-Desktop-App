/* ==========================================================================
   EL AL-NOOR AI - OPERATOR & ENGINEER MANAGEMENT CONTROLLER
   ========================================================================== */

let editingOperatorId = null;

function initOperatorsView() {
    setupOperatorModal();
    loadOperatorsData();
}

async function loadOperatorsData() {
    const tbody = document.getElementById('operatorsTableBody');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:30px; color:#888;"><i class="fas fa-spinner fa-spin"></i> جاري تحميل بيانات المشغلين...</td></tr>`;

    try {
        const res = await fetch('/api/operators?active_only=false');
        const operators = await res.json();

        renderOperatorsTable(operators);
        updateTopBarOperators(operators);
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:30px; color:#e74c3c;"><i class="fas fa-exclamation-triangle"></i> تعذر تحميل بيانات المشغلين</td></tr>`;
    }
}

function renderOperatorsTable(operators) {
    const tbody = document.getElementById('operatorsTableBody');
    if (!tbody) return;

    if (!operators || operators.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:30px; color:#888;">لا يوجد مشغلين مسجلين</td></tr>`;
        return;
    }

    tbody.innerHTML = operators.map(op => {
        const isActive = op.is_active === 1 || op.is_active === true;
        const statusBadge = isActive
            ? `<span style="background:#2ecc71; color:#fff; padding:3px 8px; border-radius:3px; font-size:0.75rem; font-weight:700;">${t('active')}</span>`
            : `<span style="background:#888; color:#fff; padding:3px 8px; border-radius:3px; font-size:0.75rem; font-weight:700;">${t('inactive')}</span>`;

        return `
            <tr>
                <td><code>${op.code || '-'}</code></td>
                <td><strong>${op.name}</strong></td>
                <td><span style="color:var(--primary); font-weight:600;">${op.role}</span></td>
                <td>${statusBadge}</td>
                <td>
                    <div style="display:flex; gap:6px;">
                        <button class="btn btn-dark" style="padding:4px 8px; font-size:0.75rem;" onclick="openEditOperatorModal(${op.id}, '${escapeHtml(op.name)}', '${escapeHtml(op.role)}', '${escapeHtml(op.code || '')}', ${isActive})">
                            <i class="fas fa-edit"></i> تعديل
                        </button>
                        ${isActive ? `
                        <button class="btn btn-dark" style="padding:4px 8px; font-size:0.75rem; color:#e74c3c;" onclick="deleteOperator(${op.id})">
                            <i class="fas fa-trash-alt"></i> حذف
                        </button>` : ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function updateTopBarOperators(operators) {
    const select = document.getElementById('operatorSelect');
    if (!select) return;

    const currentVal = select.value;
    const activeOps = (operators || []).filter(o => o.is_active === 1 || o.is_active === true);

    select.innerHTML = activeOps.map(op => `
        <option value="${escapeHtml(op.name)}">${escapeHtml(op.name)} (${escapeHtml(op.role)})</option>
    `).join('');

    if (currentVal && activeOps.some(o => o.name === currentVal)) {
        select.value = currentVal;
    }
}

function setupOperatorModal() {
    const modal = document.getElementById('operatorModal');
    const btnAdd = document.getElementById('btnAddOperator');
    const btnClose = document.getElementById('closeOperatorModal');
    const btnCancel = document.getElementById('cancelOperatorModal');
    const form = document.getElementById('operatorForm');

    if (btnAdd) {
        btnAdd.addEventListener('click', () => {
            editingOperatorId = null;
            document.getElementById('modalOperatorTitle').textContent = t('btn_add_operator');
            document.getElementById('opNameInput').value = '';
            document.getElementById('opRoleInput').value = 'مهندس رقابة جودة';
            document.getElementById('opCodeInput').value = '';
            modal.classList.add('active');
        });
    }

    if (btnClose) btnClose.addEventListener('click', () => modal.classList.remove('active'));
    if (btnCancel) btnCancel.addEventListener('click', () => modal.classList.remove('active'));

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('opNameInput')?.value.trim();
            const role = document.getElementById('opRoleInput')?.value.trim() || 'مهندس جودة';
            const code = document.getElementById('opCodeInput')?.value.trim() || null;

            if (!name) {
                showToast('يرجى كتابة اسم المشغل', 'warning');
                return;
            }

            try {
                let res;
                if (editingOperatorId) {
                    res = await fetch(`/api/operators/${editingOperatorId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, role, code, is_active: true })
                    });
                } else {
                    res = await fetch('/api/operators', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, role, code, is_active: true })
                    });
                }

                const data = await res.json();
                if (data.success) {
                    showToast(t('save_success'), 'success');
                    modal.classList.remove('active');
                    loadOperatorsData();
                } else {
                    showToast('Failed to save operator', 'error');
                }
            } catch (err) {
                console.error(err);
                showToast('Error connecting to server', 'error');
            }
        });
    }
}

function openEditOperatorModal(id, name, role, code, isActive) {
    editingOperatorId = id;
    const modal = document.getElementById('operatorModal');
    if (!modal) return;

    document.getElementById('modalOperatorTitle').textContent = 'تعديل بيانات المشغل';
    document.getElementById('opNameInput').value = name;
    document.getElementById('opRoleInput').value = role;
    document.getElementById('opCodeInput').value = code;

    modal.classList.add('active');
}

async function deleteOperator(id) {
    if (confirm('هل أنت متأكد من تعطيل/حذف هذا المشغل؟')) {
        try {
            const res = await fetch(`/api/operators/${id}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                showToast('تم حذف المشغل بنجاح', 'success');
                loadOperatorsData();
            }
        } catch (err) {
            showToast('Error deleting operator', 'error');
        }
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
