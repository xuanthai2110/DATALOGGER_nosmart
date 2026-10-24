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
            <td><span class="badge ${acc.token ? 'badge-success' : 'badge-dim'}">${acc.token ? 'Đang đăng nhập' : 'Chưa đăng nhập'}</span></td>
            <td>
                <button class="action-btn edit" onclick="editAccount(${acc.id})" title="Chỉnh sửa"><i class="fas fa-edit"></i></button>
                <button class="action-btn login" id="btn-login-acc-${acc.id}" onclick="loginServerAccount(${acc.id}, '${acc.username}')" title="Đăng nhập Server để lấy Token"><i class="fas fa-sign-in-alt"></i></button>
                <button class="action-btn delete" onclick="deleteAccount(${acc.id})" title="Xóa"><i class="fas fa-trash"></i></button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Cập nhật dropdown trong Form Project (Settings)
    updateProjectAccountDropdown(accounts);
}

async function loginServerAccount(id, username) {
    const btn = document.getElementById(`btn-login-acc-${id}`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i>`;
    }

    try {
        const res = await apiCall(`/server-accounts/${id}/login`, 'POST');
        if (res && res.ok) {
            alert(res.message || `Đăng nhập tài khoản '${username}' thành công! Đã lấy và lưu Token.`);
            await loadAccounts();
        } else {
            const detailMsg = res?.detail || res?.message || "Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin tài khoản hoặc kết nối server.";
            alert(`Lỗi đăng nhập: ${detailMsg}`);
        }
    } catch (e) {
        console.error(e);
        alert(`Lỗi khi thực hiện đăng nhập: ${e.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fas fa-sign-in-alt"></i>`;
        }
    }
}

async function loginFromForm() {
    const id = document.getElementById('account-id').value;
    const username = document.getElementById('acc-user').value;
    if (!id) {
        alert("Vui lòng lưu tài khoản trước khi đăng nhập!");
        return;
    }

    const btn = document.getElementById('btn-account-login-form');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ĐANG ĐĂNG NHẬP...`;
    }

    try {
        // Tự động lưu mật khẩu mới hoặc tên nếu người dùng vừa sửa đổi
        const pass = document.getElementById('acc-pass').value;
        const name = document.getElementById('acc-name').value;
        const patchData = { name, username };
        if (pass) patchData.password = pass;
        await apiCall(`/server-accounts/${id}`, 'PATCH', patchData);

        // Gọi login lên server
        const res = await apiCall(`/server-accounts/${id}/login`, 'POST');
        if (res && res.ok) {
            alert(res.message || `Đăng nhập tài khoản '${username}' thành công! Đã lấy và lưu Token.`);
            hideAccountForm();
            await loadAccounts();
        } else {
            const detailMsg = res?.detail || res?.message || "Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin tài khoản hoặc kết nối server.";
            alert(`Lỗi đăng nhập: ${detailMsg}`);
        }
    } catch (e) {
        console.error(e);
        alert(`Lỗi khi thực hiện đăng nhập: ${e.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fas fa-sign-in-alt"></i> ĐĂNG NHẬP`;
        }
    }
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

    const btnLogin = document.getElementById('btn-account-login-form');
    if (btnLogin) btnLogin.classList.add('hidden');
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

    const btnLogin = document.getElementById('btn-account-login-form');
    if (btnLogin) btnLogin.classList.remove('hidden');
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
    showConfirmModal(
        "Xác nhận xóa tài khoản",
        "Bạn có chắc chắn muốn xóa tài khoản này? (Chỉ xóa được nếu không có dự án nào đang liên kết)",
        async () => {
            const res = await apiCall(`/server-accounts/${id}`, 'DELETE');
            if (res && res.ok) {
                loadAccounts();
            } else {
                alert(res?.error || "Không thể xóa tài khoản. Vui lòng kiểm tra lại (có thể đang có dự án sử dụng).");
            }
        }
    );
}

// Hook vào initApp hoặc showView
// Chúng ta sẽ gọi loadAccounts() khi showView('accounts')
