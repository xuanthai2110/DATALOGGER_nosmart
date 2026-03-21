let syncProjects = [];
let currentUser = null;

async function loadSync() {
    console.log("loadSync called");
    // 1. Get current user info (for role)
    currentUser = await apiCall('/auth/me');
    console.log("Current user for sync:", currentUser);
    if (!currentUser) {
        console.error("Failed to get current user info for sync");
        return;
    }

    // 2. Load projects
    const data = await apiCall('/projects');
    syncProjects = (data && data.projects) || [];

    const select = document.getElementById('sync-project-select');
    select.innerHTML = '<option value="">-- Chọn dự án --</option>' + 
        syncProjects.map(p => `<option value="${p.id}">${p.name} (${p.sync_status || 'pending'})</option>`).join('');
}

async function loadSyncProjectDetails() {
    const projId = document.getElementById('sync-project-select').value;
    const detailsDiv = document.getElementById('sync-details');
    const msg = document.getElementById('sync-status-msg');
    msg.innerText = "";

    if (!projId) {
        detailsDiv.classList.add('hidden');
        return;
    }

    const project = syncProjects.find(p => String(p.id) === String(projId));
    if (!project) return;

    // Fetch inverters for this project
    const inverters = await apiCall('/inverters'); // This gets ALL, filter locally or update API
    const projectInverters = inverters.filter(inv => String(inv.project_id) === String(projId));

    const tbody = document.getElementById('sync-inverters-body');
    tbody.innerHTML = projectInverters.map(inv => `
        <tr>
            <td>${inv.serial_number}</td>
            <td>${inv.model}</td>
            <td><span class="badge ${inv.sync_status === 'approved' ? 'success' : 'warning'}">${inv.sync_status || 'pending'}</span></td>
            <td>${inv.server_id ? 'ID: ' + inv.server_id : (inv.server_request_id ? 'Req: ' + inv.server_request_id : '-')}</td>
        </tr>
    `).join('');

    // Update button text or status based on role
    const syncBtn = document.getElementById('btn-sync-action');
    if (currentUser.role === 'admin') {
        syncBtn.innerHTML = '<i class="fas fa-cloud-upload-alt"></i> ĐỒNG BỘ LÊN SERVER (ADMIN)';
    } else {
        syncBtn.innerHTML = '<i class="fas fa-paper-plane"></i> GỬI YÊU CẦU ĐỒNG BỘ (USER)';
    }

    detailsDiv.classList.remove('hidden');
}

async function handleSync() {
    const projId = document.getElementById('sync-project-select').value;
    if (!projId) return;

    const msg = document.getElementById('sync-status-msg');
    const btn = document.getElementById('btn-sync-action');

    msg.innerText = "Đang xử lý đồng bộ...";
    msg.className = "text-primary";
    btn.disabled = true;

    try {
        const res = await apiCall(`/sync/project/${projId}`, 'POST');
        if (res && res.ok) {
            msg.innerText = res.message || "Đồng bộ thành công!";
            msg.className = "text-success";
            alert(res.message);
            loadSync(); // Refresh lists
            loadSyncProjectDetails();
        } else {
            msg.innerText = "Đồng bộ thất bại: " + (res ? res.detail : "Lỗi không xác định");
            msg.className = "text-danger";
        }
    } catch (e) {
        msg.innerText = "Lỗi kết nối: " + e.message;
        msg.className = "text-danger";
    } finally {
        btn.disabled = false;
    }
}
