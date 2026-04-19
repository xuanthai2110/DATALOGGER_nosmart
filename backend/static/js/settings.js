let settingsProjects = [];
let settingsComms = [];
let settingsInverters = [];
let settingsMeters = [];
let foundInverters = [];
let foundMeters = [];
let scanPollInterval = null;
let meterScanPollInterval = null;
let scanSelections = {};
let meterScanSelections = {};
let availableModels = { "Sungrow": [], "Huawei": [] };
let availableMeterModels = { "Chint": ["DTSU666"], "Acrel": ["DTSD1352"] };

async function loadSettings() {
    console.log("DEBUG: loadSettings started");
    try {
        const [pData, cData, iData, mData, accData, evnData] = await Promise.all([
            apiCall('/projects'),
            apiCall('/comm'),
            apiCall('/inverters'),
            apiCall('/scan/models'),
            apiCall('/server-accounts'),
            apiCall('/evn/settings')
        ]);

        console.log("DEBUG: pData:", pData);
        console.log("DEBUG: cData:", cData);
        console.log("DEBUG: mData:", mData);

        settingsProjects = (pData && pData.projects) || [];
        settingsComms = cData || [];
        settingsInverters = iData || [];
        
        if (mData) {
            availableModels = mData;
            updateModels();
        }

        if (accData) {
            updateProjectAccountDropdown(accData);
        }

        if (evnData) {
            const hostEl = document.getElementById('evn-host');
            const portEl = document.getElementById('evn-port');
            const enabledEl = document.getElementById('evn-enabled');
            if (hostEl) hostEl.value = evnData.host || '0.0.0.0';
            if (portEl) portEl.value = evnData.port || 502;
            if (enabledEl) enabledEl.checked = evnData.enabled || false;
        }

        // Render bảng Dự án và Truyền thông
        const projectBody = document.getElementById('body-settings-projects');
        if (projectBody) {
            projectBody.innerHTML = settingsProjects.map(p => `<tr><td>${p.name}</td><td class="action-btns"><button class="action-btn edit" onclick='editProject(${JSON.stringify(p)})'><i class="fas fa-edit"></i></button><button class="action-btn delete" onclick="deleteProject(${p.id})"><i class="fas fa-trash"></i></button></td></tr>`).join('');
        }
        
        const commBody = document.getElementById('body-settings-comm');
        if (commBody) {
            commBody.innerHTML = settingsComms.map(c => `<tr><td>${c.driver}</td><td>${c.comm_type}</td><td class="action-btns"><button class="action-btn edit" onclick='editComm(${JSON.stringify(c)})'><i class="fas fa-edit"></i></button><button class="action-btn delete" onclick="deleteComm(${c.id})"><i class="fas fa-trash"></i></button></td></tr>`).join('');
        }
        
        // --- ĐIỀN DROPDOWN DỰ ÁN ---
        const projOptions = ['<option value="">-- Chọn dự án --</option>', ...settingsProjects.map(p => `<option value="${p.id}">${p.name}</option>`)].join('');
        
        ['inv-mgmt-project-filter', 'meter-mgmt-project-filter', 'inv-proj-select', 'meter-proj-select'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.innerHTML = projOptions;
                console.log(`DEBUG: Populated project dropdown #${id} with ${settingsProjects.length} projects`);
            } else {
                console.warn(`DEBUG: Element #${id} not found for project dropdown population`);
            }
        });

        // --- ĐIỀN DROPDOWN TRUYỀN THÔNG ---
        let commOptions = '<option value="">-- Chọn truyền thông --</option>';
        if (settingsComms.length > 0) {
            commOptions = settingsComms.map(c => `<option value="${c.id}">${getCommLabel(c)}</option>`).join('');
        }

        ['inv-comm-select', 'meter-comm-select', 'meter-scan-comm-select'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.innerHTML = commOptions;
                console.log(`DEBUG: Populated comm dropdown #${id} with ${settingsComms.length} configs`);
            } else {
                console.warn(`DEBUG: Element #${id} not found for comm dropdown population`);
            }
        });

        renderInvertersByProject();
        renderMetersByProject();
        renderScanResults();
        renderMeterScanResults();

    } catch (err) {
        console.error("ERROR in loadSettings:", err);
    }
}

function renderInvertersByProject() {
    const filterEl = document.getElementById('inv-mgmt-project-filter');
    const tbody = document.getElementById('body-settings-inverters');
    if (!filterEl || !tbody) return;
    
    const projId = filterEl.value;
    console.log("Filtering inverters for project ID:", projId);
    
    if (!projId) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; opacity:0.5;">Vui lòng chọn dự án...</td></tr>';
        return;
    }

    const filtered = settingsInverters.filter(inv => String(inv.project_id) === String(projId));
    console.log("Filtered inverters:", filtered);
    
    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; opacity:0.5;">Dự án này chưa có Inverter nào.</td></tr>';
    } else {
        tbody.innerHTML = filtered.map(inv => `
            <tr>
                <td>${inv.serial_number}</td>
                <td>${inv.slave_id}</td>
                <td class="action-btns">
                    <button class="action-btn edit" onclick=\'editInverter(${JSON.stringify(inv)})\' title="Sửa"><i class="fas fa-edit"></i></button>
                    <button class="action-btn delete" onclick="deleteInverter(${inv.id})" title="Xóa"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `).join('');
    }
}

async function saveInverter() {
    const id = document.getElementById('inv-id').value;
    const body = {
        project_id: parseInt(document.getElementById('inv-proj-select').value),
        comm_id: parseInt(document.getElementById('inv-comm-select').value),
        serial_number: document.getElementById('inv-sn').value,
        slave_id: parseInt(document.getElementById('inv-slave').value),
        brand: document.getElementById('inv-brand').value,
        model: document.getElementById('inv-model').value,
        capacity_kw: parseFloat(document.getElementById('inv-cap').value),
        phase_count: parseInt(document.getElementById('inv-phase').value)
    };

    if (!body.project_id || !body.comm_id || !body.serial_number || isNaN(body.slave_id)) {
        return alert("Vui lòng nhập đầy đủ thông tin bắt buộc!");
    }

    const m = id ? 'PATCH' : 'POST';
    const url = id ? `/inverters/${id}` : '/inverters';
    
    const r = await apiCall(url, m, body);
    if (r) {
        alert("Lưu thông tin Inverter vào máy Pi thành công!");
        resetInverterForm();
        loadSettings(); // Tải lại dữ liệu để cập nhật danh sách
    }
}

function editInverter(inv) {
    document.getElementById('inv-id').value = inv.id;
    document.getElementById('inv-proj-select').value = inv.project_id || "";
    document.getElementById('inv-comm-select').value = inv.comm_id || "";
    document.getElementById('inv-sn').value = inv.serial_number;
    document.getElementById('inv-slave').value = inv.slave_id;
    document.getElementById('inv-brand').value = inv.brand || "";
    document.getElementById('inv-model').value = inv.model || "";
    document.getElementById('inv-cap').value = inv.capacity_kw || 0;
    document.getElementById('inv-phase').value = inv.phase_count || 3;
    
    document.getElementById('form-inverter').classList.remove('hidden');
    document.getElementById('inv-sn').focus();
}

function resetInverterForm() {
    document.getElementById('inv-id').value = "";
    document.getElementById('inv-sn').value = "";
    document.getElementById('inv-slave').value = 1;
    document.getElementById('inv-brand').value = "";
    document.getElementById('inv-model').value = "";
    document.getElementById('inv-cap').value = 0;
    document.getElementById('inv-phase').value = 3;
    document.getElementById('form-inverter').classList.add('hidden');
}

async function deleteInverter(id) {
    if (confirm("Xoá inverter này?")) {
        await apiCall(`/inverters/${id}`, 'DELETE');
        loadSettings();
    }
}

async function deleteInverterFromForm() {
    const id = document.getElementById('inv-id').value;
    if (!id) return;
    await deleteInverter(id);
    resetInverterForm();
}

async function saveProject() {
    const id = document.getElementById('proj-id').value;
    const body = {
        server_account_id: parseInt(document.getElementById('proj-account-id').value) || 1,
        name: document.getElementById('proj-name').value,
        elec_meter_no: document.getElementById('proj-meter').value,
        elec_price_per_kwh: parseFloat(document.getElementById('proj-price').value),
        location: document.getElementById('proj-loc').value,
        lat: parseFloat(document.getElementById('proj-lat').value) || 0,
        lon: parseFloat(document.getElementById('proj-lon').value) || 0,
        capacity_kwp: parseFloat(document.getElementById('proj-dc').value) || 0,
        ac_capacity_kw: parseFloat(document.getElementById('proj-ac').value) || 0,
        inverter_count: parseInt(document.getElementById('proj-inv-count').value) || 0
    };

    if (!body.name || !body.location || !body.elec_meter_no || isNaN(body.elec_price_per_kwh) || body.capacity_kwp <= 0 || body.ac_capacity_kw <= 0) {
        return alert("Vui lÃ²ng nháº­p Ä‘áº§y Ä‘á»§ cÃ¡c trÆ°á»ng báº¯t buá»™c (*): TÃªn, Äá»‹a Ä‘iá»ƒm, Meter No, GiÃ¡ Ä‘iá»‡n, CÃ´ng suáº¥t DC/AC!");
    }

    const r = id ? await apiCall(`/projects/${id}`, 'PATCH', body) : await apiCall('/projects', 'POST', body);
    if (r) {
        alert("Lưu dự án thành công!");
        resetProjectForm();
        loadSettings();
    }
}

function editProject(p) {
    document.getElementById('proj-id').value = p.id;
    document.getElementById('proj-account-id').value = p.server_account_id || 1;
    document.getElementById('proj-name').value = p.name;
    document.getElementById('proj-meter').value = p.elec_meter_no || "";
    document.getElementById('proj-price').value = p.elec_price_per_kwh;
    document.getElementById('proj-loc').value = p.location || "";
    document.getElementById('proj-lat').value = p.lat || 0;
    document.getElementById('proj-lon').value = p.lon || 0;
    document.getElementById('proj-dc').value = p.capacity_kwp || 0;
    document.getElementById('proj-ac').value = p.ac_capacity_kw || 0;
    document.getElementById('proj-inv-count').value = p.inverter_count || 0;
    document.getElementById('proj-name').focus();
}

function resetProjectForm() {
    document.getElementById('proj-id').value = "";
    document.getElementById('proj-account-id').value = 1;
    document.getElementById('proj-name').value = "";
    document.getElementById('proj-meter').value = "";
    document.getElementById('proj-price').value = 1783;
    document.getElementById('proj-loc').value = "";
    document.getElementById('proj-lat').value = 0;
    document.getElementById('proj-lon').value = 0;
    document.getElementById('proj-dc').value = 0;
    document.getElementById('proj-ac').value = 0;
    document.getElementById('proj-inv-count').value = 0;
}

async function deleteProject(id) {
    if (confirm("Xoá dự án?")) {
        await apiCall(`/projects/${id}`, 'DELETE');
        loadSettings();
    }
}

async function saveComm() {
    const id = document.getElementById('comm-id').value;
    const body = {
        driver: document.getElementById('comm-driver').value,
        comm_type: document.getElementById('comm-type-select').value,
        host: document.getElementById('comm-host').value,
        port: parseInt(document.getElementById('comm-port').value),
        com_port: document.getElementById('comm-com').value,
        baudrate: parseInt(document.getElementById('comm-baud').value),
        databits: parseInt(document.getElementById('comm-data').value) || 8,
        parity: document.getElementById('comm-parity').value || 'N',
        stopbits: parseInt(document.getElementById('comm-stop').value) || 1,
        timeout: 1.0,
        slave_id_start: parseInt(document.getElementById('comm-start').value),
        slave_id_end: parseInt(document.getElementById('comm-end').value)
    };
    const r = id ? await apiCall(`/comm/${id}`, 'PATCH', body) : await apiCall('/comm', 'POST', body);
    if (r) {
        alert("Lưu cấu hình thành công!");
        resetCommForm();
        loadSettings();
    }
}

function editComm(c) {
    document.getElementById('comm-id').value = c.id || "";
    document.getElementById('comm-driver').value = c.driver;
    
    const brandEl = document.getElementById('comm-brand');
    const modelEl = document.getElementById('comm-model');
    if (brandEl) {
        brandEl.value = c.driver === "Sungrow" ? "Sungrow" : "Huawei";
        updateModels();
    }
    
    document.getElementById('comm-type-select').value = c.comm_type;
    document.getElementById('comm-host').value = c.host;
    document.getElementById('comm-port').value = c.port;
    document.getElementById('comm-com').value = c.com_port;
    document.getElementById('comm-baud').value = c.baudrate;
    document.getElementById('comm-data').value = c.databits || 8;
    document.getElementById('comm-parity').value = c.parity || 'N';
    document.getElementById('comm-stop').value = c.stopbits || 1;
    document.getElementById('comm-start').value = c.slave_id_start;
    document.getElementById('comm-end').value = c.slave_id_end;
    toggleCommFields();
    renderScanResults();
}

function updateModels() {
    const brand = document.getElementById('comm-brand')?.value;
    const modelSelect = document.getElementById('comm-model');
    const driverSelect = document.getElementById('comm-driver');
    if (!modelSelect || !brand) return;
    
    if (driverSelect) driverSelect.value = brand;

    const models = availableModels[brand] || [];
    modelSelect.innerHTML = models.map(m => `<option value="${m}">${m}</option>`).join('');
}

async function startScan() {
    const btn = document.getElementById('btn-scan');
    const comm = {
        brand: document.getElementById('comm-brand')?.value,
        model: document.getElementById('comm-model')?.value,
        driver: document.getElementById('comm-driver').value,
        comm_type: document.getElementById('comm-type-select').value,
        host: document.getElementById('comm-host').value,
        port: parseInt(document.getElementById('comm-port').value),
        com_port: document.getElementById('comm-com').value,
        baudrate: parseInt(document.getElementById('comm-baud').value),
        databits: parseInt(document.getElementById('comm-data').value),
        parity: document.getElementById('comm-parity').value,
        stopbits: parseInt(document.getElementById('comm-stop').value),
        slave_id_start: parseInt(document.getElementById('comm-start').value),
        slave_id_end: parseInt(document.getElementById('comm-end').value)
    };

    const res = await apiCall('/scan/start', 'POST', { comm });
    if (res && res.ok) {
        scanSelections = {};
        foundInverters = [];
        btn.disabled = true;
        document.getElementById('scan-results').classList.remove('hidden');
        document.getElementById('scan-list').innerHTML = "";
        document.getElementById('scan-progress-bar').style.width = "0%";
        document.getElementById('btn-stop-scan').classList.remove('hidden');

        if (scanPollInterval) clearInterval(scanPollInterval);
        scanPollInterval = setInterval(pollScanStatus, 1000);
    } else {
        alert("Lỗi: " + (res ? res.error : "Không thể bắt đầu quét"));
    }
}

async function pollScanStatus() {
    const res = await apiCall('/scan/status');
    if (!res) return;

    const [pData, cData] = await Promise.all([
        apiCall('/projects'),
        apiCall('/comm')
    ]);
    settingsProjects = (pData && pData.projects) || [];
    settingsComms = cData || [];

    const progress = res.total > 0 ? (res.progress / res.total * 100) : 0;
    document.getElementById('scan-progress-bar').style.width = `${progress}%`;
    document.getElementById('scan-status-text').innerText = res.is_running ? `Đang quét Slave ID: ${res.progress}/${res.total}` : 'Quét hoàn tất';

    foundInverters = res.inverters || [];
    renderScanResults();

    if (!res.is_running) {
        clearInterval(scanPollInterval);
        scanPollInterval = null;
        document.getElementById('btn-scan').disabled = false;
        document.getElementById('btn-stop-scan').classList.add('hidden');
        if (foundInverters.length === 0 && !res.stop_requested) {
            document.getElementById('scan-list').innerHTML = '<p style="text-align:center; padding:10px; opacity:0.6">Không tìm thấy thiết bị nào.</p>';
        } else if (res.stop_requested) {
            document.getElementById('scan-status-text').innerText = 'Đã dừng quét';
        }
    }
}

async function stopScan() {
    if (confirm("Dừng quá trình quét?")) {
        await apiCall('/scan/stop', 'POST');
    }
}

async function saveFoundInverter(idx) {
    const inv = foundInverters[idx];
    const key = getScanKey(inv, idx);

    captureScanSelections();

    const projId = scanSelections[key]?.project_id || document.getElementById(`scan-proj-${idx}`)?.value;
    const commId = scanSelections[key]?.comm_id || document.getElementById(`scan-comm-${idx}`)?.value;

    if (!projId) return alert("Chọn dự án!");
    if (!commId) return alert("Chọn cấu hình truyền thông!");

    const body = {
        inverters: [{
            ...inv,
            project_id: parseInt(projId),
            comm_id: parseInt(commId)
        }]
    };
    const r = await apiCall('/scan/save', 'POST', body);
    if (r && r.ok) {
        alert("ÄÃ£ lÆ°u!");
        loadDashboard();
        loadSettings();
    }
}

function resetCommForm() {
    document.getElementById('comm-id').value = "";
    document.getElementById('comm-driver').value = "Huawei";
    document.getElementById('comm-type-select').value = "TCP";
    document.getElementById('comm-data').value = 8;
    document.getElementById('comm-parity').value = 'N';
    document.getElementById('comm-stop').value = 1;
    document.getElementById('scan-results').classList.add('hidden');
    if (scanPollInterval) clearInterval(scanPollInterval);
    toggleCommFields();
    renderScanResults();
}

async function deleteComm(id) {
    if (confirm("Xoá cấu hình?")) {
        await apiCall(`/comm/${id}`, 'DELETE');
        loadSettings();
    }
}

function getScanKey(inv, idx) {
    return `${inv.serial_number || 'unknown'}-${inv.slave_id ?? idx}`;
}

function captureScanSelections() {
    foundInverters.forEach((inv, idx) => {
        const key = getScanKey(inv, idx);
        const projEl = document.getElementById(`scan-proj-${idx}`);
        const commEl = document.getElementById(`scan-comm-${idx}`);
        const current = scanSelections[key] || {};
        scanSelections[key] = {
            project_id: projEl ? projEl.value : current.project_id || "",
            comm_id: commEl ? commEl.value : current.comm_id || ""
        };
    });
}

function getCommLabel(comm) {
    try {
        if (!comm) return "Cấu hình trống";
        const endpoint = comm.comm_type === 'TCP'
            ? `${comm.host || '-'}:${comm.port || '-'}`
            : `${comm.com_port || '-'} @ ${comm.baudrate || 9600}`;
        return `${comm.driver || 'Unknown'} | ${comm.comm_type || 'Unknown'} | ${endpoint}`;
    } catch (e) {
        console.error("Error in getCommLabel:", e);
        return "Lỗi hiển thị cấu hình";
    }
}

function getDefaultCommId() {
    const formCommId = document.getElementById('comm-id')?.value;
    if (!formCommId) return "";
    return settingsComms.some(c => String(c.id) === String(formCommId)) ? String(formCommId) : "";
}

function renderScanResults() {
    const scanList = document.getElementById('scan-list');
    if (!scanList) return;

    captureScanSelections();

    if (!foundInverters.length) {
        scanList.innerHTML = "";
        return;
    }

    const defaultCommId = getDefaultCommId();
    const noComms = settingsComms.length === 0;

    scanList.innerHTML = foundInverters.map((inv, idx) => {
        const key = getScanKey(inv, idx);
        const selected = scanSelections[key] || {};
        const selectedProjectId = selected.project_id || "";
        const selectedCommId = selected.comm_id || defaultCommId;

        return `
        <div class="scan-item">
            <div class="scan-item__meta">
                <b style="color:var(--primary)">${inv.serial_number}</b> <small style="opacity:0.6">(Slave: ${inv.slave_id})</small><br/>
                <span style="font-size:11px;">${inv.brand || 'Inverter'} ${inv.model || ''} | <b>${inv.capacity_kw || 0} kW</b></span>
            </div>
            <div class="scan-item__actions">
                <select id="scan-proj-${idx}" class="scan-select">
                    <option value="">Dự án...</option>
                    ${settingsProjects.map(p => `<option value="${p.id}" ${String(selectedProjectId) === String(p.id) ? 'selected' : ''}>${p.name}</option>`).join('')}
                </select>
                <select id="scan-comm-${idx}" class="scan-select">
                    <option value="">Comm...</option>
                    ${noComms ? '<option value="" disabled>Lưu comm trước</option>' : settingsComms.map(c => `<option value="${c.id}" ${String(selectedCommId) === String(c.id) ? 'selected' : ''}>${getCommLabel(c)}</option>`).join('')}
                </select>
                <button onclick="saveFoundInverter(${idx})" class="btn-success scan-save-btn" ${noComms ? 'disabled' : ''}>LƯU</button>
            </div>
        </div>
        `;
    }).join('');
}

// === METER MANAGEMENT ===
async function renderMetersByProject() {
    const filterEl = document.getElementById('meter-mgmt-project-filter');
    const tbody = document.getElementById('body-settings-meters');
    if (!filterEl || !tbody) return;
    
    const projId = filterEl.value;
    if (!projId) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; opacity:0.5;">Vui lòng chọn dự án...</td></tr>';
        return;
    }

    const data = await apiCall(`/meters/project/${projId}`);
    settingsMeters = data || [];
    
    if (settingsMeters.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; opacity:0.5;">Dự án này chưa có Meter nào.</td></tr>';
    } else {
        tbody.innerHTML = settingsMeters.map(m => `
            <tr>
                <td>${m.serial_number || 'N/A'}</td>
                <td>${m.slave_id}</td>
                <td>${m.brand} ${m.model}</td>
                <td class="action-btns">
                    <button class="action-btn edit" onclick=\'editMeter(${JSON.stringify(m)})\' title="Sửa"><i class="fas fa-edit"></i></button>
                    <button class="action-btn delete" onclick="deleteMeter(${m.id})" title="Xóa"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `).join('');
    }
}

async function saveMeter() {
    const id = document.getElementById('meter-id').value;
    const body = {
        project_id: parseInt(document.getElementById('meter-proj-select').value),
        comm_id: parseInt(document.getElementById('meter-comm-select').value),
        serial_number: document.getElementById('meter-sn').value,
        slave_id: parseInt(document.getElementById('meter-slave').value),
        brand: document.getElementById('meter-brand').value,
        model: document.getElementById('meter-model').value
    };

    if (!body.project_id || !body.comm_id || isNaN(body.slave_id)) {
        return alert("Vui lòng nhập đầy đủ thông tin!");
    }

    const m = id ? 'PATCH' : 'POST';
    const url = id ? `/meters/${id}` : '/meters/';
    
    const r = await apiCall(url, m, body);
    if (r) {
        alert("Lưu Meter thành công!");
        resetMeterForm();
        renderMetersByProject();
    }
}

function editMeter(m) {
    document.getElementById('meter-id').value = m.id;
    document.getElementById('meter-proj-select').value = m.project_id;
    document.getElementById('meter-comm-select').value = m.comm_id;
    document.getElementById('meter-sn').value = m.serial_number || "";
    document.getElementById('meter-slave').value = m.slave_id;
    document.getElementById('meter-brand').value = m.brand;
    document.getElementById('meter-model').value = m.model;
    document.getElementById('form-meter').classList.remove('hidden');
}

function resetMeterForm() {
    document.getElementById('meter-id').value = "";
    document.getElementById('meter-sn').value = "";
    document.getElementById('meter-slave').value = 1;
    document.getElementById('form-meter').classList.add('hidden');
}

async function deleteMeter(id) {
    if (confirm("Xoá meter này?")) {
        await apiCall(`/meters/${id}`, 'DELETE');
        renderMetersByProject();
    }
}

// === METER SCANNING ===
async function startMeterScan() {
    const commId = document.getElementById('meter-scan-comm-select').value;
    if (!commId) return alert("Vui lòng chọn cấu hình truyền thông!");
    
    const comm = settingsComms.find(c => String(c.id) === String(commId));
    const body = {
        comm: {
            ...comm,
            brand: "Chint", // Mặc định hoặc cho chọn
            model: "DTSU666",
            slave_id_start: 1,
            slave_id_end: 20
        }
    };

    const res = await apiCall('/scan/meters/start', 'POST', body);
    if (res && res.ok) {
        foundMeters = [];
        document.getElementById('meter-scan-results').classList.remove('hidden');
        document.getElementById('btn-scan-meter').disabled = true;
        if (meterScanPollInterval) clearInterval(meterScanPollInterval);
        meterScanPollInterval = setInterval(pollMeterScanStatus, 1000);
    }
}

async function pollMeterScanStatus() {
    const res = await apiCall('/scan/meters/status');
    if (!res) return;

    const progress = res.total > 0 ? (res.progress / res.total * 100) : 0;
    document.getElementById('meter-scan-progress-bar').style.width = `${progress}%`;
    document.getElementById('meter-scan-status-text').innerText = res.is_running ? `Đang quét Slave ID: ${res.progress}/${res.total}` : 'Quét hoàn tất';

    foundMeters = res.results || [];
    renderMeterScanResults();

    if (!res.is_running) {
        clearInterval(meterScanPollInterval);
        meterScanPollInterval = null;
        document.getElementById('btn-scan-meter').disabled = false;
    }
}

function renderMeterScanResults() {
    const scanList = document.getElementById('meter-scan-list');
    if (!scanList) return;

    if (!foundMeters.length) {
        scanList.innerHTML = "";
        return;
    }

    const projId = document.getElementById('meter-mgmt-project-filter').value;
    const commId = document.getElementById('meter-scan-comm-select').value;

    scanList.innerHTML = foundMeters.map((m, idx) => `
        <div class="scan-item">
            <div class="scan-item__meta">
                <b>SN: ${m.serial_number || 'Unknown'}</b> <small>(Slave: ${m.slave_id})</small><br/>
                <span style="font-size:11px;">${m.brand} ${m.model} | P: ${m.p_total} W</span>
            </div>
            <div class="scan-item__actions">
                <button onclick="saveFoundMeter(${idx})" class="btn-success scan-save-btn">LƯU</button>
            </div>
        </div>
    `).join('');
}

async function saveFoundMeter(idx) {
    const meter = foundMeters[idx];
    const projId = document.getElementById('meter-mgmt-project-filter').value;
    const commId = document.getElementById('meter-scan-comm-select').value;

    if (!projId) return alert("Vui lòng chọn dự án ở phía trên!");

    const body = {
        project_id: parseInt(projId),
        meters: [{
            ...meter,
            comm_id: parseInt(commId)
        }]
    };
    const r = await apiCall('/scan/meters/save', 'POST', body);
    if (r) {
        alert("Đã lưu Meter!");
        renderMetersByProject();
    }
}

async function stopMeterScan() {
    await apiCall('/scan/meters/stop', 'POST');
}

// === EVN CONFIGURATION ===
async function saveEVNConfig() {
    const body = {
        host: document.getElementById('evn-host').value,
        port: parseInt(document.getElementById('evn-port').value),
        enabled: document.getElementById('evn-enabled').checked
    };
    const r = await apiCall('/evn/settings', 'POST', body);
    if (r) {
        alert("Lưu cấu hình EVN thành công!");
    }
}