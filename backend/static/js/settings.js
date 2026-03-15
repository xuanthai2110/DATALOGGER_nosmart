async function loadSettings() {
    const pData = await apiCall('/projects');
    const cData = await apiCall('/comm');
    document.getElementById('body-settings-projects').innerHTML = (pData.projects || []).map(p => `<tr><td>${p.name}</td><td class="action-btns"><button class="action-btn edit" onclick='editProject(${JSON.stringify(p)})'><i class="fas fa-edit"></i></button><button class="action-btn delete" onclick="deleteProject(${p.id})"><i class="fas fa-trash"></i></button></td></tr>`).join('');
    document.getElementById('body-settings-comm').innerHTML = (cData || []).map(c => `<tr><td>${c.driver}</td><td>${c.comm_type}</td><td class="action-btns"><button class="action-btn edit" onclick='editComm(${JSON.stringify(c)})'><i class="fas fa-edit"></i></button><button class="action-btn delete" onclick="deleteComm(${c.id})"><i class="fas fa-trash"></i></button></td></tr>`).join('');
}

async function saveProject() {
    const id = document.getElementById('proj-id').value;
    const body = { 
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
    
    if(!body.name || !body.location || !body.elec_meter_no || isNaN(body.elec_price_per_kwh) || body.capacity_kwp <= 0 || body.ac_capacity_kw <= 0) {
        return alert("Vui lòng nhập đầy đủ các trường bắt buộc (*): Tên, Địa điểm, Meter No, Giá điện, Công suất DC/AC!");
    }
    
    const r = id ? await apiCall(`/projects/${id}`, 'PATCH', body) : await apiCall('/projects', 'POST', body);
    if(r) { alert("Lưu dự án thành công!"); resetProjectForm(); loadSettings(); }
}

function editProject(p) { 
    document.getElementById('proj-id').value = p.id; 
    document.getElementById('proj-name').value = p.name; 
    document.getElementById('proj-meter').value = p.elec_meter_no||""; 
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
    document.getElementById('proj-id').value=""; 
    document.getElementById('proj-name').value=""; 
    document.getElementById('proj-meter').value=""; 
    document.getElementById('proj-price').value=1783; 
    document.getElementById('proj-loc').value="";
    document.getElementById('proj-lat').value=0;
    document.getElementById('proj-lon').value=0;
    document.getElementById('proj-dc').value=0;
    document.getElementById('proj-ac').value=0;
    document.getElementById('proj-inv-count').value=0;
}

async function deleteProject(id) { 
    if(confirm("Xoá?")) { 
        await apiCall(`/projects/${id}`, 'DELETE'); 
        loadSettings(); 
    } 
}

async function saveComm() {
    const id = document.getElementById('comm-id').value;
    const body = {
        driver: document.getElementById('comm-driver').value, comm_type: document.getElementById('comm-type-select').value,
        host: document.getElementById('comm-host').value, port: parseInt(document.getElementById('comm-port').value),
        com_port: document.getElementById('comm-com').value, baudrate: parseInt(document.getElementById('comm-baud').value),
        databits: parseInt(document.getElementById('comm-data').value) || 8,
        parity: document.getElementById('comm-parity').value || 'N',
        stopbits: parseInt(document.getElementById('comm-stop').value) || 1,
        timeout: 1.0, slave_id_start: parseInt(document.getElementById('comm-start').value), slave_id_end: parseInt(document.getElementById('comm-end').value)
    };
    const r = id ? await apiCall(`/comm/${id}`, 'PATCH', body) : await apiCall('/comm', 'POST', body);
    if(r) { alert("Lưu cấu hình thành công!"); resetCommForm(); loadSettings(); }
}

function editComm(c) {
    document.getElementById('comm-id').value = c.id||""; 
    document.getElementById('comm-driver').value = c.driver; 
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
}

let foundInverters = [];
let scanPollInterval = null;

async function startScan() {
    const btn = document.getElementById('btn-scan');
    const comm = {
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
    if(res && res.ok) {
        btn.disabled = true;
        document.getElementById('scan-results').classList.remove('hidden');
        document.getElementById('scan-list').innerHTML = "";
        document.getElementById('scan-progress-bar').style.width = "0%";
        document.getElementById('btn-stop-scan').classList.remove('hidden');
        
        if(scanPollInterval) clearInterval(scanPollInterval);
        scanPollInterval = setInterval(pollScanStatus, 1000);
    } else {
        alert("Lỗi: " + (res ? res.error : "Không thể bắt đầu quét"));
    }
}

async function pollScanStatus() {
    const res = await apiCall('/scan/status');
    if(!res) return;

    const progress = res.total > 0 ? (res.progress / res.total * 100) : 0;
    document.getElementById('scan-progress-bar').style.width = `${progress}%`;
    document.getElementById('scan-status-text').innerText = res.is_running ? `Đang quét Slave ID: ${res.progress}/${res.total}` : 'Quét hoàn tất';
    
    foundInverters = res.inverters;
    const pData = await apiCall('/projects');
    const projs = pData.projects || [];
    
    document.getElementById('scan-list').innerHTML = foundInverters.map((inv, idx) => `
        <div style="padding:10px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center;">
            <div>
                <b style="color:var(--primary)">${inv.serial_number}</b> <small style="opacity:0.6">(Slave: ${inv.slave_id})</small><br/>
                <span style="font-size:11px;">${inv.brand || 'Inverter'} ${inv.model || ''} | <b>${inv.capacity_kw || 0} kW</b></span>
            </div>
            <div style="display:flex; gap:8px;">
                <select id="scan-proj-${idx}" style="padding:4px; font-size:12px; border-radius:4px; background:rgba(0,0,0,0.2); color:white; border:1px solid var(--border);">
                    <option value="">Dự án...</option>
                    ${projs.map(p => `<option value="${p.id}">${p.name}</option>`).join('')}
                </select>
                <button onclick="saveFoundInverter(${idx})" class="btn-success" style="padding:4px 8px; font-size:11px; border-radius:4px; border:none; cursor:pointer;">LƯU</button>
            </div>
        </div>
    `).join('');

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
    if(confirm("Dừng quá trình quét?")) {
        await apiCall('/scan/stop', 'POST');
    }
}

async function saveFoundInverter(idx) {
    const inv = foundInverters[idx];
    const projId = document.getElementById(`scan-proj-${idx}`).value;
    if(!projId) return alert("Chọn dự án!");
    const body = { inverters: [{ ...inv, project_id: parseInt(projId) }] };
    const r = await apiCall('/scan/save', 'POST', body);
    if(r && r.ok) { alert("Đã lưu!"); loadDashboard(); }
}

function resetCommForm() { 
    document.getElementById('comm-id').value=""; 
    document.getElementById('comm-driver').value="Huawei"; 
    document.getElementById('comm-type-select').value="TCP"; 
    document.getElementById('comm-data').value=8; 
    document.getElementById('comm-parity').value='N'; 
    document.getElementById('comm-stop').value=1;
    document.getElementById('scan-results').classList.add('hidden');
    if(scanPollInterval) clearInterval(scanPollInterval);
    toggleCommFields(); 
}

async function deleteComm(id) { 
    if(confirm("Xoá cấu hình?")) { 
        await apiCall(`/comm/${id}`, 'DELETE'); 
        loadSettings(); 
    } 
}
