/**
 * accounts.js - Quản lý Server Accounts trên UI
 */

async function loadAccounts() {
    const accounts = await apiCall('/server-accounts');
    if (!accounts) return;
    
    const tbody = document.getElementById('accounts-body');
    tbody.innerHTML = '';
    
    accounts.forEach(acc => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${acc.id}</td>
            <td><strong>${acc.name}</strong></td>
            <td>${acc.username}</td>
            <td><span class="badge ${acc.token ? 'badge-success' : 'badge-dim'}">${acc.token ? 'Đã có Token' : 'Chưa đăng nhập'}</span></td>
            <td>
                <button class="action-btn edit" onclick="editAccount(${acc.id})" title="Sửa"><i class="fas fa-edit"></i></button>
                <button class="action-btn delete" onclick="deleteAccount(${acc.id})" title="Xóa"><i class="fas fa-trash"></i></button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Cập nhật dropdown trong Form Project (Settings)
    updateProjectAccountDropdown(accounts);
}

function updateProjectAccountDropdown(accounts) {
    const select = document.getElementById('proj-account-id');
    if (!select) return;
    
    select.innerHTML = '';
    accounts.forEach(acc => {
        const opt = document.createElement('option');
        opt.value = acc.id;
        opt.textContent = `${acc.name} (${acc.username})`;
        select.appendChild(opt);
    });
}

function showAccountForm() {
    document.getElementById('form-account').classList.remove('hidden');
    document.getElementById('account-id').value = '';
    document.getElementById('acc-name').value = '';
    document.getElementById('acc-user').value = '';
    document.getElementById('acc-pass').value = '';
    document.getElementById('account-form-title').innerText = 'Thêm tài khoản mới';
}

function hideAccountForm() {
    document.getElementById('form-account').classList.add('hidden');
}

async function editAccount(id) {
    const acc = await apiCall(`/server-accounts/${id}`);
    if (!acc) return;
    
    showAccountForm();
    document.getElementById('account-id').value = acc.id;
    document.getElementById('acc-name').value = acc.name;
    document.getElementById('acc-user').value = acc.username;
    document.getElementById('acc-pass').value = ''; // Không hiện password cũ
    document.getElementById('account-form-title').innerText = 'Sửa tài khoản #' + id;
}

async function saveAccount() {
    const id = document.getElementById('account-id').value;
    const data = {
        name: document.getElementById('acc-name').value,
        username: document.getElementById('acc-user').value,
        password: document.getElementById('acc-pass').value
    };
    
    if (!data.name || !data.username) {
        alert("Vui lòng điền đầy đủ Tên và Username!");
        return;
    }

    let res;
    if (id) {
        // Nếu edit, password có thể trống nếu không muốn đổi
        if (!data.password) delete data.password;
        res = await apiCall(`/server-accounts/${id}`, 'PATCH', data);
    } else {
        if (!data.password) {
            alert("Vui lòng nhập mật khẩu cho tài khoản mới!");
            return;
        }
        res = await apiCall('/server-accounts', 'POST', data);
    }
    
    if (res) {
        hideAccountForm();
        loadAccounts();
    } else {
        alert("Lỗi khi lưu tài khoản!");
    }
}

async function deleteAccount(id) {
    if (!confirm("Bạn có chắc chắn muốn xóa tài khoản này? (Chỉ xóa được nếu không có dự án nào đang liên kết)")) return;
    
    const res = await apiCall(`/server-accounts/${id}`, 'DELETE');
    if (res && res.ok) {
        loadAccounts();
    } else {
        alert(res?.error || "Không thể xóa tài khoản. Vui lòng kiểm tra lại (có thể đang có dự án sử dụng).");
    }
}

// Hook vào initApp hoặc showView
// Chúng ta sẽ gọi loadAccounts() khi showView('accounts')
