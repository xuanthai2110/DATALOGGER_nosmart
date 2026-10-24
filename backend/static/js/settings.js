function getNowFormattedUTC7() {
    const now = new Date();
    // Chuyển đổi chính xác sang mốc thời gian UTC+7 bất kể múi giờ máy khách
    const utc7 = new Date(now.getTime() + (now.getTimezoneOffset() + 420) * 60000);
    const pad = (n) => String(n).padStart(2, '0');
    return `${utc7.getFullYear()}-${pad(utc7.getMonth() + 1)}-${pad(utc7.getDate())} ${pad(utc7.getHours())}:${pad(utc7.getMinutes())}:${pad(utc7.getSeconds())}`;
}

function getLocalModelSpecs(brand, model, cap) {
    const b = (brand || "").toLowerCase().trim();
    const m = (model || "").toUpperCase().trim();
    const c = parseFloat(cap) || 0;
    let specs = {
        mppt_count: null,
        strings_per_mppt: null,
        string_count: null,
        rate_ac_kw: c > 0 ? c : null,
        rate_dc_kwp: c > 0 ? (c * 1.2).toFixed(1) : null,
        phase_count: 3,
        firmware_version: "V1.0"
    };

    if (b.includes("sungrow")) {
        if (m.includes("110")) {
            specs = { mppt_count: 9, strings_per_mppt: 2, string_count: 18, rate_ac_kw: 110.0, rate_dc_kwp: 143.0, phase_count: 3, firmware_version: "V1.0" };
        } else if (m.includes("50")) {
            specs = { mppt_count: 5, strings_per_mppt: 2, string_count: 10, rate_ac_kw: 50.0, rate_dc_kwp: 65.0, phase_count: 3, firmware_version: "V1.0" };
        } else if (m.includes("33")) {
            specs = { mppt_count: 3, strings_per_mppt: 2, string_count: 6, rate_ac_kw: 33.0, rate_dc_kwp: 42.9, phase_count: 3, firmware_version: "V1.0" };
        }
    } else if (b.includes("huawei")) {
        if (m.includes("110")) {
            specs = { mppt_count: 10, strings_per_mppt: 2, string_count: 20, rate_ac_kw: 110.0, rate_dc_kwp: 132.0, phase_count: 3, firmware_version: "V1.0" };
        } else if (m.includes("60")) {
            specs = { mppt_count: 6, strings_per_mppt: 2, string_count: 12, rate_ac_kw: 60.0, rate_dc_kwp: 72.0, phase_count: 3, firmware_version: "V1.0" };
        }
    } else if (b.includes("solis")) {
        specs = { mppt_count: 10, strings_per_mppt: 2, string_count: 20, rate_ac_kw: c || 100.0, rate_dc_kwp: c || 100.0, phase_count: 3, firmware_version: "V1.0" };
    }
    return specs;
}

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



        console.log("DEBUG: Data fetched:", { pData, cData, iData });



        settingsProjects = (pData && pData.projects) || [];

        settingsComms = cData || [];

        settingsInverters = iData || [];

        

        // --- 1. ĐIỀN DROPDOWN DỰ ÁN (ƯU TIÊN LÀM TRƯỚC) ---

        const projOptions = ['<option value="">-- Chọn dự án --</option>', ...settingsProjects.map(p => `<option value="${p.id}">${p.name}</option>`)].join('');

        const projectDropdownIds = ['inv-mgmt-project-filter', 'meter-mgmt-project-filter', 'inv-proj-select', 'meter-proj-select', 'sync-project-select'];

        

        projectDropdownIds.forEach(id => {

            const el = document.getElementById(id);

            if (el) {

                el.innerHTML = projOptions;

                console.log(`DEBUG: Populated #${id} with ${settingsProjects.length} projects`);

            }

        });



        // --- 2. ĐIỀN DROPDOWN TRUYỀN THÔNG ---

        const commOptions = ['<option value="">-- Chọn truyền thông --</option>', ...settingsComms.map(c => `<option value="${c.id}">${getCommLabel(c)}</option>`)].join('');

        const commDropdownIds = ['inv-comm-select', 'meter-comm-select', 'inv-scan-comm-select'];



        commDropdownIds.forEach(id => {

            const el = document.getElementById(id);

            if (el) {

                el.innerHTML = commOptions;

                console.log(`DEBUG: Populated #${id} with ${settingsComms.length} configs`);

            }

        });



        // --- 3. CÁC CẤU HÌNH KHÁC ---

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



        // Render bảng Dự án

        const projectBody = document.getElementById('body-settings-projects');

        if (projectBody) {

            projectBody.innerHTML = settingsProjects.map(p => `<tr><td>${p.name}</td><td class="action-btns"><button class="action-btn edit" onclick='editProject(${JSON.stringify(p)})'><i class="fas fa-edit"></i></button><button class="action-btn delete" onclick="deleteProject(${p.id})"><i class="fas fa-trash"></i></button></td></tr>`).join('');

        }



        renderInvertersByProject();

        renderMetersByProject();

        renderScanResults();

        renderMeterScanResults();

        loadAvailablePorts();

        loadCommSettings(); // Load dữ liệu truyền thông RS-485 / TCP cố định



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

        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; opacity:0.5;">Vui lòng chọn dự án...</td></tr>';

        return;

    }



    const filtered = settingsInverters.filter(inv => String(inv.project_id) === String(projId));

    console.log("Filtered inverters:", filtered);

    

    if (filtered.length === 0) {

        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; opacity:0.5;">Dự án này chưa có Inverter nào.</td></tr>';

    } else {

        tbody.innerHTML = filtered.map(inv => {

            const isActive = inv.is_active === true || inv.is_active === 1 || inv.is_active === "true";

            const statusBadge = isActive 

                ? '<span style="color:var(--success); font-weight:600;"><i class="fas fa-check-circle"></i> Hoạt động</span>' 

                : '<span style="color:var(--danger); font-weight:600;"><i class="fas fa-times-circle"></i> Ngưng hoạt động</span>';

            return `

            <tr>

                <td><strong style="color:var(--primary); font-size:12px;">#${inv.id}</strong></td>

                <td>${inv.serial_number}</td>

                <td>${inv.slave_id}</td>

                <td>${statusBadge}</td>

                <td class="action-btns">

                    <button class="action-btn edit" onclick="editInverter(${inv.id})" title="Sửa"><i class="fas fa-edit"></i></button>

                    <button class="action-btn delete" onclick="deleteInverter(${inv.id})" title="Xóa"><i class="fas fa-trash"></i></button>

                </td>

            </tr>

            `;

        }).join('');

    }

}



async function saveInverter() {

    const id = document.getElementById('inv-id').value;

    const invIndexVal = document.getElementById('inv-index').value;

    const rateDcVal = document.getElementById('inv-dc').value;

    const rateAcVal = document.getElementById('inv-rate-ac').value;

    const mpptCountVal = document.getElementById('inv-mppt-count').value;

    const stringCountVal = document.getElementById('inv-string-count').value;

    const stringsPerMpptVal = document.getElementById('inv-strings-per-mppt').value;

    const replacedByVal = document.getElementById('inv-replaced-by').value;

    

    const isActiveVal = document.getElementById('inv-is-active').value === "true";

    let usageEndVal = document.getElementById('inv-usage-end').value || null;

    

    // Nếu chuyển sang ngưng hoạt động hoặc có Inverter thay thế mà chưa nhập usage_end_at, tự động lấy thời gian hiện tại theo UTC+7
    if ((!isActiveVal || replacedByVal) && !usageEndVal) {
        usageEndVal = getNowFormattedUTC7();
        document.getElementById('inv-usage-end').value = usageEndVal;
    }



    const body = {

        project_id: parseInt(document.getElementById('inv-proj-select').value),

        comm_id: parseInt(document.getElementById('inv-comm-select').value),

        serial_number: document.getElementById('inv-sn').value,

        slave_id: parseInt(document.getElementById('inv-slave').value),

        brand: document.getElementById('inv-brand').value,

        model: document.getElementById('inv-model').value,

        capacity_kw: parseFloat(document.getElementById('inv-cap').value) || 0,

        rate_ac_kw: rateAcVal ? parseFloat(rateAcVal) : null,

        rate_dc_kwp: rateDcVal ? parseFloat(rateDcVal) : null,

        mppt_count: mpptCountVal ? parseInt(mpptCountVal) : null,

        string_count: stringCountVal ? parseInt(stringCountVal) : null,

        strings_per_mppt: stringsPerMpptVal ? parseInt(stringsPerMpptVal) : null,

        phase_count: parseInt(document.getElementById('inv-phase').value) || 3,

        firmware_version: document.getElementById('inv-firmware').value || null,

        is_active: isActiveVal,

        replaced_by_id: replacedByVal ? parseInt(replacedByVal) : null,

        usage_start_at: document.getElementById('inv-usage-start').value || null,

        usage_end_at: usageEndVal,

        inverter_index: invIndexVal ? parseInt(invIndexVal) : null

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



function formatDateTimeStr(dtStr) {

    if (!dtStr) return "";

    let s = String(dtStr).trim().replace("Z", "").replace("T", " ");

    if (s.includes(".")) {

        s = s.split(".")[0];

    }

    return s;

}



function editInverter(invOrId) {
    let inv = invOrId;
    if (typeof invOrId === 'number' || typeof invOrId === 'string') {
        inv = settingsInverters.find(i => String(i.id) === String(invOrId)) || invOrId;
    }
    if (!inv || typeof inv !== 'object') {
        console.warn("Invalid inverter data in editInverter:", invOrId);
        return;
    }

    const currentId = (inv.id !== undefined && inv.id !== null) ? inv.id : (inv.inverter_id || "");
    document.getElementById('inv-id').value = currentId;
    
    const invIdDisplay = document.getElementById('inv-id-display');
    if (invIdDisplay) {
        invIdDisplay.value = currentId !== "" ? currentId : "";
    }

    document.getElementById('inv-proj-select').value = inv.project_id || "";
    document.getElementById('inv-comm-select').value = inv.comm_id || "";
    document.getElementById('inv-sn').value = inv.serial_number || "";
    document.getElementById('inv-slave').value = (inv.slave_id !== undefined && inv.slave_id !== null) ? inv.slave_id : 1;
    document.getElementById('inv-brand').value = inv.brand || "";
    document.getElementById('inv-model').value = inv.model || "";
    document.getElementById('inv-cap').value = inv.capacity_kw || 0;

    // Lấy thông số chuẩn dự phòng theo Brand/Model
    const localSpecs = getLocalModelSpecs(inv.brand, inv.model, inv.capacity_kw);

    const getVal = (field, fallback) => {
        const v = inv[field];
        if (v !== undefined && v !== null && v !== "" && v !== 0 && v !== 0.0) return v;
        return (fallback !== undefined && fallback !== null) ? fallback : "";
    };

    document.getElementById('inv-dc').value = getVal('rate_dc_kwp', localSpecs.rate_dc_kwp);
    document.getElementById('inv-rate-ac').value = getVal('rate_ac_kw', localSpecs.rate_ac_kw);
    document.getElementById('inv-mppt-count').value = getVal('mppt_count', localSpecs.mppt_count);
    document.getElementById('inv-string-count').value = getVal('string_count', localSpecs.string_count);
    document.getElementById('inv-strings-per-mppt').value = getVal('strings_per_mppt', localSpecs.strings_per_mppt);
    document.getElementById('inv-phase').value = getVal('phase_count', localSpecs.phase_count || 3);
    document.getElementById('inv-firmware').value = getVal('firmware_version', localSpecs.firmware_version || "V1.0");

    const isActive = inv.is_active === true || inv.is_active === 1 || inv.is_active === "true";
    document.getElementById('inv-is-active').value = isActive ? "true" : "false";
    document.getElementById('inv-replaced-by').value = (inv.replaced_by_id !== undefined && inv.replaced_by_id !== null) ? inv.replaced_by_id : "";
    
    let usageStart = formatDateTimeStr(inv.usage_start_at);
    if (!usageStart) {
        usageStart = getNowFormattedUTC7();
    }
    document.getElementById('inv-usage-start').value = usageStart;
    document.getElementById('inv-usage-end').value = formatDateTimeStr(inv.usage_end_at);
    document.getElementById('inv-index').value = (inv.inverter_index !== undefined && inv.inverter_index !== null) ? inv.inverter_index : "";
    
    // Read-only server fields
    document.getElementById('inv-server-id').value = inv.server_id || "";
    document.getElementById('inv-server-request-id').value = inv.server_request_id || "";
    document.getElementById('inv-sync-status').value = inv.sync_status || "pending";
    
    // Kiểm tra thêm từ backend API
    autoFillInverterSpecs(false);

    document.getElementById('form-inverter').classList.remove('hidden');
    document.getElementById('inv-sn').focus();
}



async function autoFillInverterSpecs(force = true) {
    const brand = document.getElementById('inv-brand').value;
    const model = document.getElementById('inv-model').value;
    const cap = parseFloat(document.getElementById('inv-cap').value) || 0;
    
    if (!brand && !model) return;

    // 1. Điền nhanh từ local specs
    const local = getLocalModelSpecs(brand, model, cap);
    const setIfEmptyOrForced = (elemId, val) => {
        const el = document.getElementById(elemId);
        if (el && (force || !el.value || el.value === "0" || el.value === "")) {
            if (val !== undefined && val !== null) el.value = val;
        }
    };
    if (local) {
        setIfEmptyOrForced('inv-rate-ac', local.rate_ac_kw);
        setIfEmptyOrForced('inv-dc', local.rate_dc_kwp);
        setIfEmptyOrForced('inv-mppt-count', local.mppt_count);
        setIfEmptyOrForced('inv-string-count', local.string_count);
        setIfEmptyOrForced('inv-strings-per-mppt', local.strings_per_mppt);
        setIfEmptyOrForced('inv-phase', local.phase_count || 3);
        setIfEmptyOrForced('inv-firmware', local.firmware_version || "V1.0");
    }
    
    // 2. Tra cứu thêm từ backend API
    try {
        const res = await apiCall(`/inverters/specs?brand=${encodeURIComponent(brand)}&model=${encodeURIComponent(model)}&capacity_kw=${cap}`);
        if (res && res.specs) {
            const s = res.specs;
            setIfEmptyOrForced('inv-rate-ac', s.rate_ac_kw || (cap > 0 ? cap : null));
            setIfEmptyOrForced('inv-dc', s.rate_dc_kwp || (cap > 0 ? (cap * 1.2).toFixed(1) : null));
            setIfEmptyOrForced('inv-mppt-count', s.mppt_count);
            setIfEmptyOrForced('inv-string-count', s.string_count);
            setIfEmptyOrForced('inv-strings-per-mppt', s.strings_per_mppt);
            setIfEmptyOrForced('inv-phase', s.phase_count || 3);
            setIfEmptyOrForced('inv-firmware', s.firmware_version || "V1.0");
        }
    } catch (e) {
        console.warn("autoFillInverterSpecs error:", e);
    }
}



function resetInverterForm() {

    document.getElementById('inv-id').value = "";

    const invIdDisplay = document.getElementById('inv-id-display');

    if (invIdDisplay) invIdDisplay.value = "";

    document.getElementById('inv-sn').value = "";

    document.getElementById('inv-slave').value = 1;

    document.getElementById('inv-brand').value = "";

    document.getElementById('inv-model').value = "";

    document.getElementById('inv-firmware').value = "";

    document.getElementById('inv-cap').value = 0;

    document.getElementById('inv-dc').value = "";

    document.getElementById('inv-rate-ac').value = "";

    document.getElementById('inv-mppt-count').value = "";

    document.getElementById('inv-string-count').value = "";

    document.getElementById('inv-strings-per-mppt').value = "";

    document.getElementById('inv-phase').value = 3;

    document.getElementById('inv-is-active').value = "true";

    document.getElementById('inv-replaced-by').value = "";

    document.getElementById('inv-usage-start').value = "";

    document.getElementById('inv-usage-end').value = "";

    document.getElementById('inv-index').value = "";

    document.getElementById('inv-server-id').value = "";

    document.getElementById('inv-server-request-id').value = "";

    document.getElementById('inv-sync-status').value = "pending";

    document.getElementById('form-inverter').classList.add('hidden');

}



async function deleteInverter(id) {

    showConfirmModal("Xác nhận xóa", "Bạn có chắc chắn muốn xóa inverter này?", async () => {

        await apiCall(`/inverters/${id}`, 'DELETE');

        loadSettings();

    });

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

    

    const container = document.getElementById('project-form-container');

    if (container) {

        container.classList.remove('hidden');

        container.scrollIntoView({ behavior: 'smooth' });

    }

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

    

    const container = document.getElementById('project-form-container');

    if (container) {

        container.classList.add('hidden');

    }

}



async function deleteProject(id) {

    showConfirmModal("Xác nhận xóa", "Bạn có chắc chắn muốn xóa dự án này?", async () => {

        await apiCall(`/projects/${id}`, 'DELETE');

        loadSettings();

    });

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

        multi_master: (typeof commConfig !== 'undefined' && commConfig) ? commConfig.multi_master : (document.getElementById('comm-multimaster-1')?.value === "1"),

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

    showConfirmModal("Dừng quét", "Bạn có chắc chắn muốn dừng quá trình quét?", async () => {

        await apiCall('/scan/stop', 'POST');

    });

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

    showConfirmModal("Xác nhận xóa", "Bạn có chắc chắn muốn xóa cấu hình truyền thông này?", async () => {

        await apiCall(`/comm/${id}`, 'DELETE');

        loadSettings();

    });

}



// === NEW RS-485 & TCP SETTINGS ===

function loadCommSettings() {

    for (let i = 1; i <= 5; i++) {

        const c = settingsComms.find(x => x.id === i);

        if (!c) continue;

        

        if (i <= 4) {

            // RS485 (USB0 -> USB3)

            const baudEl = document.getElementById(`comm-baud-${i}`);

            const dataEl = document.getElementById(`comm-data-${i}`);

            const parityEl = document.getElementById(`comm-parity-${i}`);

            const stopEl = document.getElementById(`comm-stop-${i}`);

            const timeoutEl = document.getElementById(`comm-timeout-${i}`);

            const startEl = document.getElementById(`comm-start-${i}`);

            const endEl = document.getElementById(`comm-end-${i}`);

            const mmEl = document.getElementById(`comm-multimaster-${i}`);

            const roleEl = document.getElementById(`comm-role-${i}`);



            if (baudEl) baudEl.value = c.baudrate || 9600;

            if (dataEl) dataEl.value = c.databits || 8;

            if (parityEl) parityEl.value = c.parity || 'N';

            if (stopEl) stopEl.value = c.stopbits || 1;

            if (timeoutEl) timeoutEl.value = c.timeout || 1.0;

            if (startEl) startEl.value = c.slave_id_start || 1;

            if (endEl) endEl.value = c.slave_id_end || 30;

            if (mmEl) mmEl.value = c.multi_master ? "1" : "0";

            if (roleEl) roleEl.value = c.is_master !== false ? "1" : "0";

        } else {

            // TCP

            const hostEl = document.getElementById(`comm-host-5`);

            const portEl = document.getElementById(`comm-port-5`);

            const timeoutEl = document.getElementById(`comm-timeout-5`);

            const startEl = document.getElementById(`comm-start-5`);

            const endEl = document.getElementById(`comm-end-5`);

            const mmEl = document.getElementById(`comm-multimaster-5`);

            const roleEl = document.getElementById(`comm-role-5`);



            if (hostEl) hostEl.value = c.host || '192.168.1.10';

            if (portEl) portEl.value = c.port || 502;

            if (timeoutEl) timeoutEl.value = c.timeout || 1.0;

            if (startEl) startEl.value = c.slave_id_start || 1;

            if (endEl) endEl.value = c.slave_id_end || 30;

            if (mmEl) mmEl.value = c.multi_master ? "1" : "0";

            if (roleEl) roleEl.value = c.is_master !== false ? "1" : "0";

        }

    }

}



async function saveCommSettings() {

    showToast('Lưu Cấu Hình', 'Đang cập nhật các cấu hình truyền thông...');

    try {

        const promises = [];

        

        // RS-485 (ID 1 -> 4)

        for (let i = 1; i <= 4; i++) {

            const body = {

                baudrate: parseInt(document.getElementById(`comm-baud-${i}`).value),

                databits: parseInt(document.getElementById(`comm-data-${i}`).value),

                parity: document.getElementById(`comm-parity-${i}`).value,

                stopbits: parseInt(document.getElementById(`comm-stop-${i}`).value),

                timeout: parseFloat(document.getElementById(`comm-timeout-${i}`).value),

                slave_id_start: parseInt(document.getElementById(`comm-start-${i}`).value),

                slave_id_end: parseInt(document.getElementById(`comm-end-${i}`).value),

                multi_master: document.getElementById(`comm-multimaster-${i}`).value === "1",

                is_master: document.getElementById(`comm-role-${i}`).value === "1"

            };

            promises.push(apiCall(`/comm/${i}`, 'PATCH', body));

        }

        

        // TCP (ID 5)

        const tcpBody = {

            host: document.getElementById(`comm-host-5`).value.trim(),

            port: parseInt(document.getElementById(`comm-port-5`).value),

            timeout: parseFloat(document.getElementById(`comm-timeout-5`).value),

            slave_id_start: parseInt(document.getElementById(`comm-start-5`).value),

            slave_id_end: parseInt(document.getElementById(`comm-end-5`).value),

            multi_master: document.getElementById(`comm-multimaster-5`).value === "1",

            is_master: document.getElementById(`comm-role-5`).value === "1"

        };

        promises.push(apiCall(`/comm/5`, 'PATCH', tcpBody));

        

        const results = await Promise.all(promises);

        if (results.every(r => r && !r.error)) {

            alert("Lưu cấu hình truyền thông RS-485 và TCP thành công!");

            loadSettings();

        } else {

            alert("Có lỗi xảy ra khi lưu một số cấu hình.");

        }

    } catch (e) {

        console.error("saveCommSettings error:", e);

        alert("Lỗi: " + e.message);

    }

}



// === AUTOMATIC INVERTER SCANNING ===

let inverterScanPollInterval = null;

let foundInvertersList = [];

let inverterScanSelections = {};



async function startInverterScan() {

    const btn = document.getElementById('btn-scan-inverter');

    const selectedCommId = document.getElementById('inv-scan-comm-select').value;

    const selectedDriverTemplate = document.getElementById('inv-scan-driver-select').value;

    const slaveStart = parseInt(document.getElementById('inv-scan-start').value) || 1;

    const slaveEnd = parseInt(document.getElementById('inv-scan-end').value) || 30;

    

    if (!selectedCommId) return alert("Vui lòng chọn truyền thông!");

    if (!selectedDriverTemplate) return alert("Vui lòng chọn driver inverter!");

    if (slaveStart > slaveEnd) return alert("Slave Start không thể lớn hơn Slave End!");

    

    const commConfig = settingsComms.find(c => String(c.id) === String(selectedCommId));

    if (!commConfig) return alert("Không tìm thấy cấu hình truyền thông!");

    

    // Ánh xạ driver template

    let brand = "", model = "", driverName = "";

    if (selectedDriverTemplate === "huawei_sun2000_110ktl") {

        brand = "Huawei"; model = "SUN2000-110KTL"; driverName = "Huawei";

    } else if (selectedDriverTemplate === "huawei_sun2000_60ktl") {

        brand = "Huawei"; model = "SUN2000-60KTL"; driverName = "Huawei";

    } else if (selectedDriverTemplate === "sungrow_sg33cx") {

        brand = "Sungrow"; model = "SG33CX"; driverName = "Sungrow";

    } else if (selectedDriverTemplate === "sungrow_sg50cx") {

        brand = "Sungrow"; model = "SG50CX"; driverName = "Sungrow";

    } else if (selectedDriverTemplate === "sungrow_sg110cx") {

        brand = "Sungrow"; model = "SG110CX"; driverName = "Sungrow";

    } else if (selectedDriverTemplate === "solis_110k") {

        brand = "Solis"; model = "110K"; driverName = "Solis";

    } else if (selectedDriverTemplate === "canadian_csi110KTL1400GL02E") {

        brand = "Canadian"; model = "csi110KTL1400GL02E"; driverName = "Canadian";

    } else if (selectedDriverTemplate === "goodwe_gw80kmt") {

        brand = "GoodWe"; model = "GW80KMT"; driverName = "GoodWe";

    } else if (selectedDriverTemplate === "goodwe_gw100k_gt") {

        brand = "GoodWe"; model = "GW100K-GT"; driverName = "GoodWe";

    } else if (selectedDriverTemplate === "goodwe_gw150k_gt_g10") {

        brand = "GoodWe"; model = "GW150K-GT-G10"; driverName = "GoodWe";

    }

    const comm = {

        id: commConfig.id,

        brand,

        model,

        driver: driverName,

        comm_type: commConfig.comm_type,

        host: commConfig.host,

        port: commConfig.port,

        com_port: commConfig.com_port,

        baudrate: commConfig.baudrate,

        databits: commConfig.databits,

        parity: commConfig.parity,

        stopbits: commConfig.stopbits,

        timeout: commConfig.timeout,

        multi_master: commConfig.multi_master,

        slave_id_start: slaveStart,

        slave_id_end: slaveEnd

    };

    

    const res = await apiCall('/scan/start', 'POST', { comm });

    if (res && res.ok) {

        inverterScanSelections = {};

        foundInvertersList = [];

        btn.disabled = true;

        document.getElementById('inverter-scan-results').classList.remove('hidden');

        document.getElementById('inverter-scan-list').innerHTML = "";

        document.getElementById('inverter-scan-progress-bar').style.width = "0%";

        document.getElementById('btn-stop-scan-inverter').classList.remove('hidden');

        

        if (inverterScanPollInterval) clearInterval(inverterScanPollInterval);

        inverterScanPollInterval = setInterval(pollInverterScanStatus, 1000);

    } else {

        alert("Lỗi: " + (res ? res.error : "Không thể bắt đầu quét"));

    }

}



async function pollInverterScanStatus() {

    const res = await apiCall('/scan/status');

    if (!res) return;

    

    if (settingsProjects.length === 0) {

        const pData = await apiCall('/projects');

        settingsProjects = (pData && pData.projects) || [];

    }

    

    const progress = res.total > 0 ? (res.progress / res.total * 100) : 0;

    const progressEl = document.getElementById('inverter-scan-progress-bar');

    const statusTextEl = document.getElementById('inverter-scan-status-text');

    const btnScanEl = document.getElementById('btn-scan-inverter');

    const btnStopEl = document.getElementById('btn-stop-scan-inverter');

    

    if (progressEl) progressEl.style.width = `${progress}%`;

    if (statusTextEl) statusTextEl.innerText = res.is_running ? `Đang quét Slave ID: ${res.progress}/${res.total}` : 'Quét hoàn tất';

    

    foundInvertersList = res.inverters || [];

    renderInverterScanResults();

    

    if (!res.is_running) {

        clearInterval(inverterScanPollInterval);

        inverterScanPollInterval = null;

        if (btnScanEl) btnScanEl.disabled = false;

        if (btnStopEl) btnStopEl.classList.add('hidden');

        

        const scanListEl = document.getElementById('inverter-scan-list');

        if (foundInvertersList.length === 0 && !res.stop_requested) {

            if (scanListEl) scanListEl.innerHTML = '<p style="text-align:center; padding:10px; opacity:0.6">Không tìm thấy thiết bị nào.</p>';

        } else if (res.stop_requested) {

            if (statusTextEl) statusTextEl.innerText = 'Đã dừng quét';

        }

    }

}



function stopInverterScan() {

    showConfirmModal("Dừng quét", "Bạn có chắc chắn muốn dừng quá trình quét inverter?", async () => {

        await apiCall('/scan/stop', 'POST');

    });

}



function renderInverterScanResults() {

    const scanList = document.getElementById('inverter-scan-list');

    if (!scanList) return;

    

    if (!foundInvertersList.length) {

        scanList.innerHTML = "";

        return;

    }

    

    const defaultCommId = document.getElementById('inv-scan-comm-select')?.value || "";

    const noComms = settingsComms.length === 0;



    scanList.innerHTML = foundInvertersList.map((inv, idx) => {

        const key = `${inv.serial_number}-${inv.slave_id}`;

        const currentSel = inverterScanSelections[key] || {};

        const selectedProjId = currentSel.project_id || "";

        const selectedCommId = currentSel.comm_id || defaultCommId;

        

        return `

        <div class="scan-item" style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.05); padding:10px 15px; border-radius:8px; border:1px solid var(--border);">

            <div>

                <b style="color:var(--primary)">SN: ${inv.serial_number}</b> <small style="opacity:0.6">(Slave: ${inv.slave_id})</small><br/>

                <span style="font-size:12px;">${inv.brand || 'Inverter'} ${inv.model || ''} | Công suất: <b>${inv.capacity_kw || 0} kW</b></span>

            </div>

            <div style="display:flex; gap:10px; align-items:center;">

                <select id="inv-scan-proj-${idx}" class="scan-select" style="padding:6px; border-radius:6px; background:var(--bg-dark); border:1px solid var(--border); color:var(--text);" onchange="captureInvScanSelections()">

                    <option value="">Chọn dự án...</option>

                    ${settingsProjects.map(p => `<option value="${p.id}" ${String(selectedProjId) === String(p.id) ? 'selected' : ''}>${p.name}</option>`).join('')}

                </select>

                <select id="inv-scan-comm-${idx}" class="scan-select" style="padding:6px; border-radius:6px; background:var(--bg-dark); border:1px solid var(--border); color:var(--text);" onchange="captureInvScanSelections()">

                    <option value="">Truyền thông...</option>

                    ${noComms ? '<option value="" disabled>Lưu comm trước</option>' : settingsComms.map(c => `<option value="${c.id}" ${String(selectedCommId) === String(c.id) ? 'selected' : ''}>${getCommLabel(c)}</option>`).join('')}

                </select>

                <button onclick="saveFoundInverterDevice(${idx})" class="btn btn-success" style="padding:6px 12px; font-size:12px;" ${noComms ? 'disabled' : ''}>LƯU</button>

            </div>

        </div>

        `;

    }).join('');

}



function captureInvScanSelections() {

    foundInvertersList.forEach((inv, idx) => {

        const key = `${inv.serial_number}-${inv.slave_id}`;

        const projEl = document.getElementById(`inv-scan-proj-${idx}`);

        const commEl = document.getElementById(`inv-scan-comm-${idx}`);

        const current = inverterScanSelections[key] || {};

        inverterScanSelections[key] = {

            project_id: projEl ? projEl.value : current.project_id || "",

            comm_id: commEl ? commEl.value : current.comm_id || ""

        };

    });

}



async function saveFoundInverterDevice(idx) {

    const inv = foundInvertersList[idx];

    captureInvScanSelections();

    

    const key = `${inv.serial_number}-${inv.slave_id}`;

    const projId = inverterScanSelections[key]?.project_id;

    const commId = inverterScanSelections[key]?.comm_id;

    

    if (!projId) return alert("Vui lòng chọn dự án!");

    if (!commId) return alert("Vui lòng chọn cổng truyền thông!");

    

    const body = {

        inverters: [{

            ...inv,

            project_id: parseInt(projId),

            comm_id: parseInt(commId)

        }]

    };

    

    const r = await apiCall('/scan/save', 'POST', body);

    if (r && r.ok) {

        alert(`Đã lưu Inverter SN ${inv.serial_number} thành công!`);

        loadSettings();

    } else {

        alert("Lỗi: " + (r ? r.error : "Không thể lưu inverter"));

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

        if (comm.id === 1) return "RS485_0";

        if (comm.id === 2) return "RS485_1";

        if (comm.id === 3) return "RS485_2";

        if (comm.id === 4) return "RS485_3";

        if (comm.id === 5) return "TCP";

        return comm.driver || 'Unknown';

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

        document.getElementById('form-meter').classList.add('hidden');

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

    

    // Tự động gán dự án đang chọn cho form-meter và hiển thị form

    document.getElementById('meter-proj-select').value = projId;

    document.getElementById('form-meter').classList.remove('hidden');

    resetMeterForm();

}



function handleMeterDriverChange() {

    const selectedDriver = document.getElementById('meter-driver-select').value;

    let brand = "Chint", model = "DTSU666";

    if (selectedDriver === "chint_dtsu666") {

        brand = "Chint"; model = "DTSU666";

    } else if (selectedDriver === "chint_dssu666") {

        brand = "Chint"; model = "DSSU666";

    } else if (selectedDriver === "acrel_dtsd1352-c") {

        brand = "Acrel"; model = "DTSD1352-C";

    } else if (selectedDriver === "eastron_sdm630mct") {

        brand = "Eastron"; model = "SDM630MCT";

    } else if (selectedDriver === "huawei_dtsu666-h") {

        brand = "Huawei"; model = "DTSU666-H";

    } else if (selectedDriver === "schneider_pm5350") {

        brand = "Schneider"; model = "PM5350";

    } else if (selectedDriver === "janitza_b23") {

        brand = "Janitza"; model = "B23";

    } else if (selectedDriver === "janitza_umg96rm-e") {

        brand = "Janitza"; model = "UMG96RM-E";

    }

    document.getElementById('meter-brand').value = brand;

    document.getElementById('meter-model').value = model;

}



async function saveMeter() {

    const id = document.getElementById('meter-id').value;

    

    // Đồng bộ driver trước khi lấy giá trị

    handleMeterDriverChange();

    

    let sn = document.getElementById('meter-sn').value.trim();

    const slaveId = parseInt(document.getElementById('meter-slave').value);

    

    if (!sn) {

        // Tự động sinh Serial Number nếu để trống

        sn = "MTR_" + slaveId + "_" + Date.now().toString().slice(-6);

    }



    const body = {

        project_id: parseInt(document.getElementById('meter-mgmt-project-filter').value),

        comm_id: parseInt(document.getElementById('meter-comm-select').value),

        serial_number: sn,

        slave_id: slaveId,

        brand: document.getElementById('meter-brand').value,

        model: document.getElementById('meter-model').value

    };



    console.log("DEBUG saveMeter body:", JSON.stringify(body));



    if (!body.project_id || !body.comm_id || isNaN(body.slave_id)) {

        return alert("Vui lòng nhập đầy đủ thông tin (Dự án, Truyền thông, Slave ID)!");

    }



    const method = id ? 'PATCH' : 'POST';

    const url = id ? `/meters/${id}` : '/meters/';

    

    console.log("DEBUG saveMeter URL:", url, "Method:", method);

    

    try {

        const h = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

        const resp = await fetch(`${API_URL}${url}`, { method: method, headers: h, body: JSON.stringify(body) });

        console.log("DEBUG saveMeter response status:", resp.status);

        

        if (resp.ok) {

            const r = await resp.json();

            console.log("DEBUG saveMeter response:", r);

            alert("Lưu Meter thành công!");

            resetMeterForm();

            renderMetersByProject();

        } else {

            const errText = await resp.text();

            console.error("DEBUG saveMeter error:", resp.status, errText);

            alert("Lỗi lưu Meter: " + resp.status + " - " + errText);

        }

    } catch(e) {

        console.error("DEBUG saveMeter exception:", e);

        alert("Lỗi kết nối: " + e.message);

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

    

    // Tìm driver phù hợp để gán cho dropdown

    const brandLower = (m.brand || '').toLowerCase();

    const modelLower = (m.model || '').toLowerCase();

    let driverVal = "chint_dtsu666";

    if (brandLower.includes("chint") && modelLower.includes("dtsu666")) {

        driverVal = "chint_dtsu666";

    } else if (brandLower.includes("chint") && modelLower.includes("dssu666")) {

        driverVal = "chint_dssu666";

    } else if (brandLower.includes("acrel") && modelLower.includes("dtsd1352")) {

        driverVal = "acrel_dtsd1352-c";

    } else if (brandLower.includes("eastron") && modelLower.includes("sdm630")) {

        driverVal = "eastron_sdm630mct";

    } else if (brandLower.includes("huawei") && modelLower.includes("dtsu666")) {

        driverVal = "huawei_dtsu666-h";

    } else if (brandLower.includes("schneider") && modelLower.includes("pm5350")) {

        driverVal = "schneider_pm5350";

    } else if (brandLower.includes("janitza") && modelLower.includes("b23")) {

        driverVal = "janitza_b23";

    } else if (brandLower.includes("janitza") && modelLower.includes("umg96")) {

        driverVal = "janitza_umg96rm-e";

    }

    document.getElementById('meter-driver-select').value = driverVal;

    

    document.getElementById('form-meter-title').innerText = "Chỉnh sửa Meter";

    document.getElementById('form-meter').classList.remove('hidden');

}



function resetMeterForm() {

    document.getElementById('meter-id').value = "";

    document.getElementById('meter-sn').value = "";

    document.getElementById('meter-slave').value = 1;

    document.getElementById('meter-driver-select').value = "chint_dtsu666";

    handleMeterDriverChange();

    document.getElementById('form-meter-title').innerText = "Thêm Meter Mới";

    

    const filterEl = document.getElementById('meter-mgmt-project-filter');

    if (filterEl && filterEl.value) {

        document.getElementById('meter-proj-select').value = filterEl.value;

    }

}



async function deleteMeter(id) {

    showConfirmModal("Xác nhận xóa", "Bạn có chắc chắn muốn xóa meter này?", async () => {

        await apiCall(`/meters/${id}`, 'DELETE');

        renderMetersByProject();

    });

}



// === METER SCANNING ===

async function loadAvailablePorts() {

    const datalist = document.getElementById('available-ports');

    if (!datalist) return;

    

    try {

        const ports = await apiCall('/comm/available-ports');

        if (ports) {

            datalist.innerHTML = ports.map(p => `<option value="${p.device}">${p.description}</option>`).join('');

            console.log("DEBUG: Loaded available ports:", ports);

        }

    } catch (e) {

        console.error("Error loading available ports:", e);

    }

}



async function startMeterScan() {

    const commId = document.getElementById('meter-scan-comm-select').value;

    if (!commId) return alert("Vui lòng chọn cấu hình truyền thông!");

    

    const selectedDriverTemplate = document.getElementById('meter-scan-driver-select').value;

    const slaveStart = parseInt(document.getElementById('meter-scan-start').value) || 1;

    const slaveEnd = parseInt(document.getElementById('meter-scan-end').value) || 20;



    let brand = "", model = "";

    if (selectedDriverTemplate === "chint_dtsu666") {

        brand = "Chint"; model = "DTSU666";

    } else if (selectedDriverTemplate === "chint_dssu666") {

        brand = "Chint"; model = "DSSU666";

    } else if (selectedDriverTemplate === "acrel_dtsd1352-c") {

        brand = "Acrel"; model = "DTSD1352-C";

    } else if (selectedDriverTemplate === "eastron_sdm630mct") {

        brand = "Eastron"; model = "SDM630MCT";

    } else if (selectedDriverTemplate === "huawei_dtsu666-h") {

        brand = "Huawei"; model = "DTSU666-H";

    } else if (selectedDriverTemplate === "schneider_pm5350") {

        brand = "Schneider"; model = "PM5350";

    } else if (selectedDriverTemplate === "janitza_b23") {

        brand = "Janitza"; model = "B23";

    } else if (selectedDriverTemplate === "janitza_umg96rm-e") {

        brand = "Janitza"; model = "UMG96RM-E";

    }



    const comm = settingsComms.find(c => String(c.id) === String(commId));

    const body = {

        comm: {

            ...comm,

            brand: brand,

            model: model,

            slave_id_start: slaveStart,

            slave_id_end: slaveEnd

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

        showToast("Success", "Lưu cấu hình EVN thành công!");

    }

}



// === TOAST NOTIFICATION ===

function showToast(title, desc) {

    const toast = document.getElementById('toast-success');

    if (!toast) return;

    document.getElementById('toast-title').innerText = title;

    document.getElementById('toast-desc').innerText = desc;

    toast.classList.add('show');

    setTimeout(() => { toast.classList.remove('show'); }, 3000);

}



function triggerRestart() {

    showConfirmModal("Khởi động lại", "Bạn có muốn khởi động lại dịch vụ không?", () => {

        showToast('System Restarting', 'Hệ thống đang khởi động lại...');

    });

}



// === MULTI-PLANT SETTINGS ===

function renderPlantList() {

    const tbody = document.getElementById('plant-list-body');

    if (!tbody) return;

    if (settingsProjects.length === 0) {

        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-dim);">Chưa có plant nào. Nhấn "Thêm Plant Mới" để bắt đầu.</td></tr>';

        return;

    }

    tbody.innerHTML = settingsProjects.map(p => `

        <tr>

            <td><span style="background:rgba(14,165,233,0.15);color:var(--primary);padding:3px 8px;border-radius:6px;font-size:12px;">#${p.id}</span></td>

            <td style="font-weight:600;">${p.name || '--'}</td>

            <td style="color:var(--text-dim);font-size:13px;">${p.location || '--'}</td>

            <td>${p.capacity_kwp || 0} kWp</td>

            <td>${p.ac_capacity_kw || 0} kW</td>

            <td style="font-size:12px;">${p.elec_meter_no || '--'}</td>

            <td style="display:flex;gap:8px;">

                <button class="action-btn edit" title="Sửa" onclick="editPlant(${p.id})"><i class="fas fa-edit"></i></button>

                <button class="action-btn delete" title="Xóa" onclick="deletePlant(${p.id}, '${(p.name||'').replace(/'/g,"\\'")}')"><i class="fas fa-trash"></i></button>

            </td>

        </tr>

    `).join('');



    // Cập nhật dropdown mode-plant-select

    const modePlantSelect = document.getElementById('mode-plant-select');

    if (modePlantSelect) {

        const currentSelected = modePlantSelect.value;

        modePlantSelect.innerHTML = '<option value="" disabled selected>-- Chọn Plant --</option>' + 

            settingsProjects.map(p => `<option value="${p.id}">${p.name}</option>`).join('');

        if (currentSelected && settingsProjects.some(p => String(p.id) === String(currentSelected))) {

            modePlantSelect.value = currentSelected;

        }

    }

}



function onPlantModeChange() {

    const plantId = document.getElementById('mode-plant-select').value;

    if (!plantId) return;

    const plant = settingsProjects.find(p => String(p.id) === String(plantId));

    if (plant) {

        document.getElementById('mode-telemetry-select').value = plant.telemetry_mode || "Realtime";

    }

}



async function savePlantMode() {

    const plantId = document.getElementById('mode-plant-select').value;

    if (!plantId) return alert("Vui lòng chọn Plant!");

    const mode = document.getElementById('mode-telemetry-select').value;



    showToast("Đang lưu", "Đang cập nhật chế độ hoạt động cho Plant...");

    const r = await apiCall(`/projects/${plantId}`, 'PATCH', { telemetry_mode: mode });

    if (r && r.ok !== false) {

        showToast("Thành công", "Đã cập nhật chế độ gửi dữ liệu thành công!");

        // Cập nhật telemetry_mode trong settingsProjects cục bộ

        const idx = settingsProjects.findIndex(p => String(p.id) === String(plantId));

        if (idx !== -1) {

            settingsProjects[idx].telemetry_mode = mode;

        }

    } else {

        showToast("Lỗi", "Không thể lưu chế độ hoạt động. Vui lòng thử lại.");

    }

}



async function loadPlantSettings() {

    console.log("Loading plant settings...");

    if (settingsProjects.length === 0) {

        await loadSettings();

    }

    // Điền tài khoản cloud vào dropdown

    const plantAccSelect = document.getElementById('plant-account-id');

    const projAccSelect = document.getElementById('proj-account-id');

    if (plantAccSelect && projAccSelect) {

        plantAccSelect.innerHTML = projAccSelect.innerHTML;

    }

    // Render danh sách plant

    renderPlantList();

    // Khởi tạo form trống khi chưa có gì chọn

    if (!document.getElementById('plant-id').value) {

        clearPlantForm();

    }

}



function newPlantForm() {

    clearPlantForm();

    document.getElementById('plant-form-title').textContent = 'Thêm Plant Mới';

    const card = document.getElementById('plant-form-card');

    if (card) card.classList.remove('hidden');

    document.getElementById('plant-form-card').scrollIntoView({ behavior: 'smooth' });

}



function clearPlantForm() {

    document.getElementById('plant-id').value = '';

    document.getElementById('plant-name').value = '';

    document.getElementById('plant-meter').value = '';

    document.getElementById('plant-price').value = 1783;

    document.getElementById('plant-loc').value = '';

    document.getElementById('plant-lat').value = 0;

    document.getElementById('plant-lon').value = 0;

    document.getElementById('plant-dc').value = 0;

    document.getElementById('plant-ac').value = 0;

    document.getElementById('plant-inv-count').value = 0;

    document.getElementById('plant-form-title').textContent = 'Thêm Plant Mới';

    

    const card = document.getElementById('plant-form-card');

    if (card) card.classList.add('hidden');

}



function cancelPlantForm() {

    clearPlantForm();

}



function editPlant(id) {

    const p = settingsProjects.find(x => x.id === id);

    if (!p) return;

    document.getElementById('plant-id').value = p.id;

    document.getElementById('plant-account-id').value = p.server_account_id || 1;

    document.getElementById('plant-name').value = p.name || '';

    document.getElementById('plant-meter').value = p.elec_meter_no || '';

    document.getElementById('plant-price').value = p.elec_price_per_kwh || 1783;

    document.getElementById('plant-loc').value = p.location || '';

    document.getElementById('plant-lat').value = p.lat || 0;

    document.getElementById('plant-lon').value = p.lon || 0;

    document.getElementById('plant-dc').value = p.capacity_kwp || 0;

    document.getElementById('plant-ac').value = p.ac_capacity_kw || 0;

    document.getElementById('plant-inv-count').value = p.inverter_count || 0;

    document.getElementById('plant-form-title').textContent = `Chỉnh sửa Plant: ${p.name}`;

    

    const card = document.getElementById('plant-form-card');

    if (card) card.classList.remove('hidden');

    document.getElementById('plant-form-card').scrollIntoView({ behavior: 'smooth' });

}



async function deletePlant(id, name) {

    showConfirmModal(

        "Xác nhận xóa Plant", 

        `Bạn có chắc muốn xóa plant "${name}" (ID: ${id})?\nHành động này sẽ xóa toàn bộ inverter thuộc plant này!`, 

        async () => {

            const r = await apiCall(`/projects/${id}`, 'DELETE');

            if (r && r.ok !== false) {

                showToast('Đã xóa', `Plant "${name}" đã được xóa thành công.`);

                await loadSettings();

                loadPlantSettings();

            } else {

                showToast('Lỗi', 'Không thể xóa plant. Vui lòng thử lại.');

            }

        }

    );

}



async function savePlantSettings() {

    const id = document.getElementById('plant-id').value;

    const body = {

        server_account_id: parseInt(document.getElementById('plant-account-id').value) || 1,

        name: document.getElementById('plant-name').value.trim(),

        elec_meter_no: document.getElementById('plant-meter').value.trim(),

        elec_price_per_kwh: parseFloat(document.getElementById('plant-price').value),

        location: document.getElementById('plant-loc').value.trim(),

        lat: parseFloat(document.getElementById('plant-lat').value) || 0,

        lon: parseFloat(document.getElementById('plant-lon').value) || 0,

        capacity_kwp: parseFloat(document.getElementById('plant-dc').value) || 0,

        ac_capacity_kw: parseFloat(document.getElementById('plant-ac').value) || 0,

        inverter_count: parseInt(document.getElementById('plant-inv-count').value) || 0

    };



    if (!body.name || !body.location || body.capacity_kwp <= 0 || body.ac_capacity_kw <= 0) {

        return alert("Vui lòng nhập đầy đủ: Tên dự án, Địa điểm, Công suất DC và AC!");

    }



    const r = id 

        ? await apiCall(`/projects/${id}`, 'PATCH', body)

        : await apiCall('/projects', 'POST', body);



    if (r && r.ok !== false) {

        showToast("Thành công", id ? "Đã cập nhật Plant thành công!" : "Đã thêm Plant mới thành công!");

        clearPlantForm();

        await loadSettings();

        loadPlantSettings();

    } else {

        showToast("Lỗi", "Không thể lưu Plant. Vui lòng kiểm tra lại.");

    }

}





// === ACCORDION IP SETTINGS (LAN/WLAN) ===

async function loadIPSettings() {

    console.log("Loading network settings...");

    try {

        const netData = await apiCall('/network/settings');

        if (netData) {

            // LAN Settings

            const lanTypeVal = netData.lan_type || "static";

            const lanRadios = document.getElementsByName('lan-type');

            lanRadios.forEach(r => { if (r.value === lanTypeVal) r.checked = true; });

            

            document.getElementById('lan-ip').value = netData.lan_ip || "192.168.1.100";

            document.getElementById('lan-gateway').value = netData.lan_gateway || "192.168.1.1";

            document.getElementById('lan-mask').value = netData.lan_mask || "255.255.255.0";

            document.getElementById('lan-dns1').value = netData.lan_dns1 || "192.168.1.1";

            document.getElementById('lan-dns2').value = netData.lan_dns2 || "8.8.8.8";

            document.getElementById('lan-default').checked = netData.lan_default !== false;



            // WLAN Settings

            const wlanTypeVal = netData.wlan_type || "dynamic";

            const wlanRadios = document.getElementsByName('wlan-type');

            wlanRadios.forEach(r => { if (r.value === wlanTypeVal) r.checked = true; });



            document.getElementById('wlan-ip').value = netData.wlan_ip || "192.168.43.100";

            document.getElementById('wlan-gateway').value = netData.wlan_gateway || "192.168.43.1";

            document.getElementById('wlan-mask').value = netData.wlan_mask || "255.255.255.0";

            document.getElementById('wlan-dns1').value = netData.wlan_dns1 || "192.168.43.1";

            document.getElementById('wlan-dns2').value = netData.wlan_dns2 || "8.8.8.8";

            

            const ssidSelect = document.getElementById('wlan-ssid-select');

            const savedSSID = netData.wlan_ssid || "";

            if (savedSSID) {

                // Thêm SSID đã lưu vào dropdown nếu chưa có

                let exists = false;

                for (let i = 0; i < ssidSelect.options.length; i++) {

                    if (ssidSelect.options[i].value === savedSSID) { exists = true; break; }

                }

                if (!exists) {

                    const opt = document.createElement('option');

                    opt.value = savedSSID;

                    opt.innerText = savedSSID;

                    ssidSelect.appendChild(opt);

                }

                ssidSelect.value = savedSSID;

            }

            

            document.getElementById('wlan-pass').value = netData.wlan_pass || "";

            document.getElementById('wlan-manual').checked = netData.wlan_manual === true;

            document.getElementById('wlan-manual-ssid').value = netData.wlan_manual_ssid || "";

            document.getElementById('wlan-default').checked = netData.wlan_default === true;

            

            toggleLANInputs();

            toggleWLANInputs();

            toggleManualSSID();

        }

    } catch (e) {

        console.error("loadIPSettings error:", e);

    }

}



async function readLiveIPSettings() {

    console.log("Reading live IP settings from Raspberry Pi...");

    showToast("Đang đọc", "Đang đọc thông số IP thực tế từ Raspberry Pi...");

    try {

        const netData = await apiCall('/network/live-status');

        if (netData) {

            // LAN Settings

            if (netData.lan) {

                document.getElementById('lan-ip').value = netData.lan.ip || "";

                document.getElementById('lan-gateway').value = netData.lan.gateway || "";

                document.getElementById('lan-mask').value = netData.lan.netmask || "";

                document.getElementById('lan-dns1').value = netData.lan.dns1 || "";

                document.getElementById('lan-dns2').value = netData.lan.dns2 || "";

                

                // Cập nhật radio button type

                const lanTypeVal = netData.lan.type || "static";

                const lanRadios = document.getElementsByName('lan-type');

                lanRadios.forEach(r => { if (r.value === lanTypeVal) r.checked = true; });

            }



            // WLAN Settings

            if (netData.wlan) {

                document.getElementById('wlan-ip').value = netData.wlan.ip || "";

                document.getElementById('wlan-gateway').value = netData.wlan.gateway || "";

                document.getElementById('wlan-mask').value = netData.wlan.netmask || "";

                document.getElementById('wlan-dns1').value = netData.wlan.dns1 || "";

                document.getElementById('wlan-dns2').value = netData.wlan.dns2 || "";

                

                // Cập nhật radio button type

                const wlanTypeVal = netData.wlan.type || "dynamic";

                const wlanRadios = document.getElementsByName('wlan-type');

                wlanRadios.forEach(r => { if (r.value === wlanTypeVal) r.checked = true; });

            }

            

            toggleLANInputs();

            toggleWLANInputs();

            

            showToast("Thành công", "Đã đọc và hiển thị thông số IP thực tế từ Raspberry Pi!");

        } else {

            showToast("Lỗi", "Không thể đọc dữ liệu IP từ Pi.");

        }

    } catch (e) {

        console.error("readLiveIPSettings error:", e);

        showToast("Lỗi", "Gặp lỗi khi kết nối tới hệ thống để đọc IP.");

    }

}



async function applyIPSettings() {

    const lanType = document.querySelector('input[name="lan-type"]:checked').value;

    const wlanType = document.querySelector('input[name="wlan-type"]:checked').value;

    

    const body = {

        lan_type: lanType,

        lan_ip: document.getElementById('lan-ip').value,

        lan_gateway: document.getElementById('lan-gateway').value,

        lan_mask: document.getElementById('lan-mask').value,

        lan_dns1: document.getElementById('lan-dns1').value,

        lan_dns2: document.getElementById('lan-dns2').value,

        lan_default: document.getElementById('lan-default').checked,

        

        wlan_type: wlanType,

        wlan_ip: document.getElementById('wlan-ip').value,

        wlan_gateway: document.getElementById('wlan-gateway').value,

        wlan_mask: document.getElementById('wlan-mask').value,

        wlan_dns1: document.getElementById('wlan-dns1').value,

        wlan_dns2: document.getElementById('wlan-dns2').value,

        wlan_ssid: document.getElementById('wlan-ssid-select').value,

        wlan_pass: document.getElementById('wlan-pass').value,

        wlan_manual: document.getElementById('wlan-manual').checked,

        wlan_manual_ssid: document.getElementById('wlan-manual-ssid').value,

        wlan_default: document.getElementById('wlan-default').checked

    };



    const r = await apiCall('/network/apply', 'POST', body);

    if (r) {

        showToast("IP Applied", "Cài đặt mạng đã lưu. Hệ thống đang chạy script áp dụng ngầm...");

    }

}



async function scanWifi() {

    const btn = document.getElementById('btn-wifi-scan');

    const icon = document.getElementById('scan-icon');

    const select = document.getElementById('wlan-ssid-select');

    if (!btn || !select) return;

    

    btn.disabled = true;

    if (icon) icon.classList.add('fa-spin');

    btn.innerHTML = `<i class="fas fa-sync fa-spin"></i> Đang quét...`;

    

    try {

        const res = await apiCall('/network/wifi-scan');

        if (res && res.wifi) {

            select.innerHTML = '<option value="" disabled selected>-- Chọn Wifi --</option>';

            res.wifi.forEach(w => {

                const opt = document.createElement('option');

                opt.value = w.ssid;

                opt.innerText = `${w.ssid} (${w.signal})`;

                select.appendChild(opt);

            });

            showToast("Wifi Scanned", `Đã tìm thấy ${res.wifi.length} mạng Wifi xung quanh.`);

        }

    } catch (e) {

        console.error("scanWifi error:", e);

    } finally {

        btn.disabled = false;

        if (icon) icon.classList.remove('fa-spin');

        btn.innerHTML = `<i class="fas fa-sync" id="scan-icon"></i> Quét Wifi`;

    }

}



function toggleLANInputs() {

    const isStatic = document.querySelector('input[name="lan-type"]:checked').value === 'static';

    const ids = ['lan-ip', 'lan-gateway', 'lan-mask', 'lan-dns1', 'lan-dns2'];

    ids.forEach(id => {

        const el = document.getElementById(id);

        if (el) {

            el.disabled = !isStatic;

            if (!isStatic) el.classList.add('time-box-disabled');

            else el.classList.remove('time-box-disabled');

        }

    });

}



function toggleWLANInputs() {

    const isStatic = document.querySelector('input[name="wlan-type"]:checked').value === 'static';

    const ids = ['wlan-ip', 'wlan-gateway', 'wlan-mask', 'wlan-dns1', 'wlan-dns2'];

    ids.forEach(id => {

        const el = document.getElementById(id);

        if (el) {

            el.disabled = !isStatic;

            if (!isStatic) el.classList.add('time-box-disabled');

            else el.classList.remove('time-box-disabled');

        }

    });

}



function toggleManualSSID() {

    const isManual = document.getElementById('wlan-manual').checked;

    const group = document.getElementById('manual-ssid-group');

    const select = document.getElementById('wlan-ssid-select');

    

    if (isManual) {

        group.style.display = 'flex';

        select.disabled = true;

    } else {

        group.style.display = 'none';

        select.disabled = false;

    }

}



// === ACCORDION EVN & VPN IPSEC ===

async function loadEVNVPN() {

    console.log("Loading EVN and VPN configurations...");

    try {

        const [evnData, vpnData] = await Promise.all([

            apiCall('/evn/settings'),

            apiCall('/evn/vpn')

        ]);

        

        if (evnData) {

            const hostEl = document.getElementById('evn-host');

            const portEl = document.getElementById('evn-port');

            const enabledEl = document.getElementById('evn-enabled');

            if (hostEl) hostEl.value = evnData.host || '0.0.0.0';

            if (portEl) portEl.value = evnData.port || 502;

            if (enabledEl) enabledEl.checked = evnData.enabled || false;

        }

        

        if (vpnData) {

            document.getElementById('vpn-enabled').checked = vpnData.vpn_enabled === true;

            document.getElementById('vpn-gateway').value = vpnData.vpn_gateway || "";

            document.getElementById('vpn-psk').value = vpnData.vpn_psk || "";

            document.getElementById('vpn-local-id').value = vpnData.vpn_local_id || "";

            document.getElementById('vpn-remote-id').value = vpnData.vpn_remote_id || "";

            document.getElementById('vpn-local-subnet').value = vpnData.vpn_local_subnet || "";

            document.getElementById('vpn-remote-subnet').value = vpnData.vpn_remote_subnet || "";

            document.getElementById('vpn-key-exchange').value = vpnData.vpn_key_exchange || "IKEv2";

            document.getElementById('vpn-auth-mode').value = vpnData.vpn_auth_mode || "main";

            

            document.getElementById('vpn-p1-life').value = vpnData.vpn_p1_life || 28800;

            document.getElementById('vpn-p1-margin').value = vpnData.vpn_p1_margin || 360;

            document.getElementById('vpn-p1-dh').value = vpnData.vpn_p1_dh || "14";

            document.getElementById('vpn-p1-enc').value = vpnData.vpn_p1_enc || "aes256";

            document.getElementById('vpn-p1-auth').value = vpnData.vpn_p1_auth || "sha256";

            

            document.getElementById('vpn-p2-dh').value = vpnData.vpn_p2_dh || "14";

            document.getElementById('vpn-p2-life').value = vpnData.vpn_p2_life || 21600;

            document.getElementById('vpn-p2-enc').value = vpnData.vpn_p2_enc || "aes256";

            document.getElementById('vpn-p2-auth').value = vpnData.vpn_p2_auth || "sha256";

            

            toggleVPNInputs();

        }

    } catch (e) {

        console.error("loadEVNVPN error:", e);

    }

}



async function saveVPNConfig() {

    const body = {

        vpn_enabled: document.getElementById('vpn-enabled').checked,

        vpn_gateway: document.getElementById('vpn-gateway').value,

        vpn_psk: document.getElementById('vpn-psk').value,

        vpn_local_id: document.getElementById('vpn-local-id').value,

        vpn_remote_id: document.getElementById('vpn-remote-id').value,

        vpn_local_subnet: document.getElementById('vpn-local-subnet').value,

        vpn_remote_subnet: document.getElementById('vpn-remote-subnet').value,

        vpn_key_exchange: document.getElementById('vpn-key-exchange').value,

        vpn_auth_mode: document.getElementById('vpn-auth-mode').value,

        vpn_p1_life: parseInt(document.getElementById('vpn-p1-life').value),

        vpn_p1_margin: parseInt(document.getElementById('vpn-p1-margin').value),

        vpn_p1_dh: document.getElementById('vpn-p1-dh').value,

        vpn_p1_enc: document.getElementById('vpn-p1-enc').value,

        vpn_p1_auth: document.getElementById('vpn-p1-auth').value,

        vpn_p2_dh: document.getElementById('vpn-p2-dh').value,

        vpn_p2_life: parseInt(document.getElementById('vpn-p2-life').value),

        vpn_p2_enc: document.getElementById('vpn-p2-enc').value,

        vpn_p2_auth: document.getElementById('vpn-p2-auth').value

    };

    

    const r = await apiCall('/evn/vpn', 'POST', body);

    if (r) {

        showToast("Success", "Đã lưu cấu hình VPN IPsec.");

    }

}



async function applyVPNConfig() {

    const body = {

        vpn_enabled: document.getElementById('vpn-enabled').checked,

        vpn_gateway: document.getElementById('vpn-gateway').value,

        vpn_psk: document.getElementById('vpn-psk').value,

        vpn_local_id: document.getElementById('vpn-local-id').value,

        vpn_remote_id: document.getElementById('vpn-remote-id').value,

        vpn_local_subnet: document.getElementById('vpn-local-subnet').value,

        vpn_remote_subnet: document.getElementById('vpn-remote-subnet').value,

        vpn_key_exchange: document.getElementById('vpn-key-exchange').value,

        vpn_auth_mode: document.getElementById('vpn-auth-mode').value,

        vpn_p1_life: parseInt(document.getElementById('vpn-p1-life').value),

        vpn_p1_margin: parseInt(document.getElementById('vpn-p1-margin').value),

        vpn_p1_dh: document.getElementById('vpn-p1-dh').value,

        vpn_p1_enc: document.getElementById('vpn-p1-enc').value,

        vpn_p1_auth: document.getElementById('vpn-p1-auth').value,

        vpn_p2_dh: document.getElementById('vpn-p2-dh').value,

        vpn_p2_life: parseInt(document.getElementById('vpn-p2-life').value),

        vpn_p2_enc: document.getElementById('vpn-p2-enc').value,

        vpn_p2_auth: document.getElementById('vpn-p2-auth').value

    };

    

    const r = await apiCall('/evn/vpn/apply', 'POST', body);

    if (r) {

        showToast("VPN Applied", r.message);

    }

}



function toggleVPNInputs() {

    const isEnabled = document.getElementById('vpn-enabled').checked;

    const elements = [

        'vpn-gateway', 'vpn-psk', 'vpn-local-id', 'vpn-remote-id',

        'vpn-local-subnet', 'vpn-remote-subnet', 'vpn-key-exchange', 'vpn-auth-mode',

        'vpn-p1-life', 'vpn-p1-margin', 'vpn-p1-dh', 'vpn-p1-enc', 'vpn-p1-auth',

        'vpn-p2-dh', 'vpn-p2-life', 'vpn-p2-enc', 'vpn-p2-auth'

    ];

    elements.forEach(id => {

        const el = document.getElementById(id);

        if (el) {

            el.disabled = !isEnabled;

            if (!isEnabled) el.classList.add('time-box-disabled');

            else el.classList.remove('time-box-disabled');

        }

    });

}



// === ACCORDION DI_BOARD & DIGITAL SENSOR & STATUS ===

async function loadDIBoardSettings() {

    console.log("Loading DI Board settings...");

    // Cài đặt DI Board load từ SQLite

    try {

        const slave = await apiCall('/config/current'); // Lấy config legacy

        if (slave && slave.di_board_slave_id) {

            document.getElementById('di-slave').value = slave.di_board_slave_id;

        }

    } catch (e) {

        console.error(e);

    }

}



async function saveDIBoardSettings() {

    const slaveId = parseInt(document.getElementById('di-slave').value) || 1;

    // Cập nhật qua config legacy

    const body = {

        di_board_slave_id: slaveId

    };

    const r = await apiCall('/config/update', 'POST', body);

    if (r) {

        showToast("Success", "Đã lưu cài đặt DI Board.");

    }

}



function loadDigitalSensorSettings() {

    console.log("Loading digital sensors...");

    // Hiển thị danh sách cảm biến số tĩnh theo thiết kế

}



function loadStatusSettings() {

    console.log("Loading status details...");

    // Tải thông số system status

}



// === MODAL ADD DEVICE ===

function openAddDeviceModal() {

    const modal = document.getElementById('add-device-modal');

    if (modal) modal.style.display = 'flex';

}



function closeAddDeviceModal() {

    const modal = document.getElementById('add-device-modal');

    if (modal) modal.style.display = 'none';

}



function submitAddDevice() {

    // Add device logic

    closeAddDeviceModal();

    showToast("Device Added", "Đã thêm thiết bị thành công.");

}



// =========================================================

// ZERO EXPORT FUNCTIONALITY

// =========================================================

let zeStatusInterval = null;



function initZeroExportTab() {

    console.log("Initializing Zero Export Tab...");

    

    // Đổ danh sách dự án vào dropdown ze-project-select

    const projSelect = document.getElementById('ze-project-select');

    if (projSelect) {

        const projOptions = ['<option value="">-- Chọn dự án --</option>', ...settingsProjects.map(p => `<option value="${p.id}">${p.name}</option>`)].join('');

        projSelect.innerHTML = projOptions;

    }

    

    // Ẩn form cấu hình ban đầu

    const form = document.getElementById('ze-config-form');

    if (form) form.classList.add('hidden');

    

    if (zeStatusInterval) {

        clearInterval(zeStatusInterval);

        zeStatusInterval = null;

    }

}



async function loadZeroExportConfig() {

    const projectId = document.getElementById('ze-project-select').value;

    const form = document.getElementById('ze-config-form');

    

    if (zeStatusInterval) {

        clearInterval(zeStatusInterval);

        zeStatusInterval = null;

    }



    if (!projectId) {

        if (form) form.classList.add('hidden');

        return;

    }



    try {

        // Gọi API lấy cấu hình và trạng thái của Zero Export

        const res = await apiCall(`/zero-export/${projectId}`);

        if (!res) return;



        const cfg = res.config;

        const status = res.status;



        // Hiển thị form

        if (form) form.classList.remove('hidden');



        // Điền các Meter của dự án vào select

        const meterSelect = document.getElementById('ze-meter-select');

        if (meterSelect) {

            // Lấy tất cả meter của dự án hiện tại

            const projectMeters = settingsMeters.filter(m => String(m.project_id) === String(projectId)) || [];

            

            // Nếu settingsMeters chưa load đầy đủ, gọi API

            let meters = projectMeters;

            if (meters.length === 0) {

                const apiMeters = await apiCall(`/meters/project/${projectId}`);

                meters = apiMeters || [];

            }

            

            meterSelect.innerHTML = [

                '<option value="">-- Chọn Meter --</option>',

                ...meters.map(m => `<option value="${m.id}">${m.brand} ${m.model || ''} (ID: ${m.slave_id}, SN: ${m.serial_number || 'N/A'})</option>`)

            ].join('');

            

            // Đặt giá trị đã lưu

            meterSelect.value = cfg.meter_id || "";

        }



        // Điền cấu hình khác

        document.getElementById('ze-meter-direction').value = cfg.meter_direction || "GRID_SIDE";

        document.getElementById('ze-export-limit-w').value = cfg.export_limit_w !== undefined ? cfg.export_limit_w : 0;

        document.getElementById('ze-deadband-w').value = cfg.deadband_w !== undefined ? cfg.deadband_w : 200;

        document.getElementById('ze-gain').value = cfg.gain !== undefined ? cfg.gain : 1.0;

        document.getElementById('ze-ramp-kw').value = cfg.ramp_kw_per_step !== undefined ? cfg.ramp_kw_per_step : 50;

        document.getElementById('ze-fail-threshold').value = cfg.meter_fail_threshold !== undefined ? cfg.meter_fail_threshold : 10;



        // Cập nhật giao diện trạng thái hoạt động

        const badge = document.getElementById('ze-status-badge');

        const btnEnable = document.getElementById('ze-btn-enable');

        const btnDisable = document.getElementById('ze-btn-disable');



        if (cfg.enabled) {

            badge.innerText = "BẬT";

            badge.style.background = "#10b981"; // green

            btnEnable.style.display = "none";

            btnDisable.style.display = "inline-block";

        } else {

            badge.innerText = "TẮT";

            badge.style.background = "#6b7280"; // gray

            btnEnable.style.display = "inline-block";

            btnDisable.style.display = "none";

        }



        // Cập nhật Realtime monitors

        updateZeroExportMonitorUI(status);



        // Đăng ký lặp cập nhật trạng thái mỗi 5s

        zeStatusInterval = setInterval(async () => {

            const freshRes = await apiCall(`/zero-export/${projectId}`);

            if (freshRes && freshRes.status) {

                updateZeroExportMonitorUI(freshRes.status);

            }

        }, 5000);



    } catch (e) {

        console.error("loadZeroExportConfig error:", e);

        showToast("Lỗi", "Không thể tải cấu hình Zero Export.");

    }

}



function updateZeroExportMonitorUI(status) {

    if (!status) return;



    // P_grid (W)

    const pGridEl = document.getElementById('ze-monitor-pgrid');

    if (pGridEl) {

        if (status.p_grid_w !== null && status.p_grid_w !== undefined) {

            pGridEl.innerText = `${status.p_grid_w.toLocaleString('vi-VN')} W`;

            pGridEl.style.color = status.p_grid_w < 0 ? "#ef4444" : "#10b981"; // đỏ nếu export (P_grid < 0)

        } else {

            pGridEl.innerText = "-- W";

            pGridEl.style.color = "var(--text)";

        }

    }



    // P_inv (W)

    const pInvEl = document.getElementById('ze-monitor-pinv');

    if (pInvEl) {

        pInvEl.innerText = status.p_inv_total_w !== null ? `${status.p_inv_total_w.toLocaleString('vi-VN')} W` : "-- W";

    }



    // Setpoint limit (kW)

    const setpointEl = document.getElementById('ze-monitor-setpoint');

    if (setpointEl) {

        setpointEl.innerText = status.p_inv_setpoint_w !== null ? `${(status.p_inv_setpoint_w / 1000).toFixed(2)} kW` : "-- kW";

    }



    // Hành động cuối

    const actionEl = document.getElementById('ze-monitor-action');

    if (actionEl) {

        actionEl.innerText = status.last_action || "--";

        if (status.last_action === "DECREASE") {

            actionEl.style.color = "#ef4444"; // đỏ

        } else if (status.last_action === "INCREASE") {

            actionEl.style.color = "#10b981"; // xanh

        } else if (status.last_action === "METER_FAULT") {

            actionEl.style.color = "#f59e0b"; // cam

        } else {

            actionEl.style.color = "var(--text)";

        }

    }



    // Fail count

    const failEl = document.getElementById('ze-monitor-failcount');

    if (failEl) {

        failEl.innerText = status.meter_fail_count !== undefined ? status.meter_fail_count : 0;

        failEl.style.color = status.meter_fail_count > 0 ? "#f59e0b" : "var(--text)";

    }



    // Trạng thái tạm khóa (suspended_by)

    const suspEl = document.getElementById('ze-monitor-suspended');

    if (suspEl) {

        if (status.suspended_by) {

            suspEl.innerText = `BỊ KHÓA BỞI ${status.suspended_by.toUpperCase()}`;

            suspEl.style.color = "#f59e0b";

        } else {

            suspEl.innerText = "KHÔNG";

            suspEl.style.color = "#10b981";

        }

    }

}



async function saveZeroExportConfigSilent() {

    const projectId = document.getElementById('ze-project-select').value;

    if (!projectId) return false;



    const meterSelectVal = document.getElementById('ze-meter-select').value;

    const body = {

        meter_id: meterSelectVal ? parseInt(meterSelectVal) : null,

        meter_direction: document.getElementById('ze-meter-direction').value,

        export_limit_w: parseFloat(document.getElementById('ze-export-limit-w').value),

        deadband_w: parseFloat(document.getElementById('ze-deadband-w').value),

        gain: parseFloat(document.getElementById('ze-gain').value),

        ramp_kw_per_step: parseFloat(document.getElementById('ze-ramp-kw').value),

        meter_fail_threshold: parseInt(document.getElementById('ze-fail-threshold').value),

    };



    if (!body.meter_id) {

        alert("Vui lòng chọn Meter PCC đo lưới trước!");

        return false;

    }



    try {

        const res = await apiCall(`/zero-export/${projectId}/config`, 'PUT', body);

        return res && res.success;

    } catch (e) {

        console.error(e);

        alert("Lỗi khi lưu cấu hình: " + e.message);

        return false;

    }

}



async function saveZeroExportConfig() {

    const success = await saveZeroExportConfigSilent();

    if (success) {

        alert("Lưu cấu hình Zero Export thành công!");

        loadZeroExportConfig();

    } else {

        alert("Lưu cấu hình thất bại.");

    }

}



async function toggleZeroExport(enable) {

    const projectId = document.getElementById('ze-project-select').value;

    if (!projectId) return;



    if (enable) {

        // Tự động lưu cấu hình trước khi BẬT để đảm bảo meter_id được lưu vào DB

        const saved = await saveZeroExportConfigSilent();

        if (!saved) return; // Dừng lại nếu lưu cấu hình thất bại

    }



    const action = enable ? "enable" : "disable";

    try {

        const res = await apiCall(`/zero-export/${projectId}/${action}`, 'POST');

        if (res && res.success) {

            showToast("Zero Export", enable ? "Đã bật Zero Export" : "Đã tắt Zero Export");

            loadZeroExportConfig();

        } else {

            // Hiển thị chi tiết lỗi từ backend nếu có (ví dụ: detail lỗi từ HTTPException)

            const errorMsg = res && res.detail ? res.detail : "Không thể thực hiện thao tác";

            alert("Thao tác thất bại: " + errorMsg);

        }

    } catch (e) {

        console.error(e);

        alert("Lỗi thao tác: " + e.message);

    }

}