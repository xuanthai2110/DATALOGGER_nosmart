async function loadDashboard() {
    const d = await apiCall('/monitoring/dashboard/summary');
    if(!d) return;
    document.getElementById('total-p-ac').innerText = d.total_p_ac.toFixed(2);
    document.getElementById('total-e-daily').innerText = d.total_e_daily.toFixed(1);
    document.getElementById('total-revenue').innerText = d.total_revenue.toLocaleString();
    document.getElementById('projects-body').innerHTML = d.projects.map((p, i) => `
        <tr class="clickable" onclick="loadProjectDetail(${p.id})">
            <td>${i+1}</td><td>${p.name}</td><td>${p.inverter_count} Div</td>
            <td>${p.capacity_kwp} / ${p.ac_capacity_kw}</td><td>${p.elec_meter_no || '--'}</td>
            <td class="text-primary">${p.p_ac.toFixed(2)}</td><td class="text-warning">${p.revenue.toLocaleString()}</td>
            <td><span class="status-badge ${p.status==='online'?'badge-online':'badge-offline'}">${p.status}</span></td>
        </tr>
    `).join('');
}

async function loadProjectDetail(id) {
    const d = await apiCall('/monitoring/dashboard/summary');
    const p = d.projects.find(x => x.id === id);
    currentProject = p;
    document.getElementById('detail-project-name').innerText = p.name;
    document.getElementById('bp-project-name').innerText = p.name;
    document.getElementById('project-stats').innerHTML = `
        <div class="stat-card glass"><div>P_ac</div><div class="value text-primary">${p.p_ac.toFixed(2)} kW</div></div>
        <div class="stat-card glass"><div>E_daily</div><div class="value text-success">${p.e_daily.toFixed(1)} kWh</div></div>
        <div class="stat-card glass"><div>Revenue</div><div class="value text-warning">${p.revenue.toLocaleString()} VNĐ</div></div>
    `;
    const invs = await apiCall('/inverters');
    const filtered = invs.filter(x => x.project_id === id);
    document.getElementById('inverter-grid').innerHTML = filtered.map(inv => `
        <div class="detail-card glass clickable" onclick="loadInverterDetail(${inv.id}, '${inv.serial_number}')">
            <h4 style="margin-bottom:8px">${inv.serial_number}</h4>
            <p style="color:var(--text-dim);font-size:12px">${inv.model} / ID:${inv.slave_id}</p>
        </div>
    `).join('');
    showView('project-detail');
}

async function loadInverterDetail(id, sn) {
    const d = await apiCall(`/monitoring/inverter/${id}/detail`);
    if(!d) return;
    document.getElementById('bp-p-back').innerText = currentProject.name;
    document.getElementById('bp-p-back').onclick = () => loadProjectDetail(currentProject.id);
    document.getElementById('bp-inv-sn').innerText = sn;
    document.getElementById('detail-inv-sn').innerHTML = `Biến tần: ${sn} <span style="font-size: 14px; font-weight: 300; opacity: 0.7; margin-left: 10px;">(Cập nhật: ${d.ac && d.ac.created_at ? new Date(d.ac.created_at).toLocaleString('vi-VN') : '--'})</span>`;
    document.getElementById('back-to-project-btn').onclick = () => loadProjectDetail(currentProject.id);

    const ac = d.ac;
    document.getElementById('inv-det-p-ac').innerText = ac ? `${(ac.P_ac || 0).toFixed(2)} kW` : '--';
    document.getElementById('inv-det-q-ac').innerText = ac ? `${(ac.Q_ac || 0).toFixed(2)} kVar` : '--';
    document.getElementById('inv-det-pf').innerText = ac ? `${(ac.PF || 0).toFixed(2)}` : '--';
    document.getElementById('inv-det-h').innerText = ac ? `${(ac.H || 0).toFixed(1)} Hz` : '--';
    document.getElementById('inv-det-e-daily').innerText = ac ? `${(ac.E_daily || 0).toFixed(2)} kWh` : '--';
    document.getElementById('inv-det-e-monthly').innerText = ac ? `${(ac.E_monthly || 0).toFixed(2)} kWh` : '--';
    document.getElementById('inv-det-e-total').innerText = ac ? `${(ac.E_total || 0).toFixed(2)} kWh` : '--';
    document.getElementById('inv-det-created-at').innerText = ac && ac.created_at ? new Date(ac.created_at).toLocaleString('vi-VN') : '--';

    document.getElementById('inv-det-ua').innerText = ac ? `${ac.V_a}V` : '--';
    document.getElementById('inv-det-ia').innerText = ac ? `${(ac.I_a || 0).toFixed(1)}A` : '--';
    document.getElementById('inv-det-ub').innerText = ac ? `${ac.V_b}V` : '--';
    document.getElementById('inv-det-ib').innerText = ac ? `${(ac.I_b || 0).toFixed(1)}A` : '--';
    document.getElementById('inv-det-uc').innerText = ac ? `${ac.V_c}V` : '--';
    document.getElementById('inv-det-ic').innerText = ac ? `${(ac.I_c || 0).toFixed(1)}A` : '--';

    document.getElementById('inv-det-mppt').innerHTML = (d.mppts || []).map(m => `<div class="list-item"><p><b>MPPT ${m.mppt_index}</b></p><p>${m.V_mppt}V / ${m.I_mppt}A / ${m.P_mppt.toFixed(2)}kW</p></div>`).join('') || 'Trống';
    document.getElementById('inv-det-string').innerHTML = (d.strings || []).map(s => `<div class="list-item">String ${s.string_id}: ${s.I_string}A</div>`).join('') || 'Trống';
    const actualErrors = (d.errors || []).filter(e => e.fault_code != 0 && e.severity !== "STABLE" && e.fault_code !== "0");
    document.getElementById('inv-det-errors').innerHTML = actualErrors.length ? actualErrors.map(e => `<div class="list-item text-danger">Lỗi ${e.fault_code}: ${e.fault_description}</div>`).join('') : '<p class="text-success">Hoạt động tốt</p>';

    
    showView('inverter-detail');
}
