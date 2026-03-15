const API_URL = '/api';
let token = localStorage.getItem('token');
let currentProject = null;

async function handleLogin() {
    const formData = new FormData();
    formData.append('username', document.getElementById('username').value);
    formData.append('password', document.getElementById('password').value);
    const r = await fetch(`${API_URL}/auth/token`, { method: 'POST', body: formData });
    if (r.ok) { 
        token = (await r.json()).access_token; 
        localStorage.setItem('token', token); 
        initApp(); 
    }
    else alert("Login failed!");
}

function handleLogout() { 
    localStorage.removeItem('token'); 
    location.reload(); 
}

async function apiCall(e, m='GET', b=null) {
    const h = { 'Authorization': `Bearer ${token}` };
    if(b) { h['Content-Type'] = 'application/json'; b = JSON.stringify(b); }
    const r = await fetch(`${API_URL}${e}`, { method: m, headers: h, body: b });
    if(r.status === 401) handleLogout();
    return r.ok ? await r.json() : null;
}
