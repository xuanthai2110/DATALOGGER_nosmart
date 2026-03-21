function initApp() {
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('app-view').classList.remove('hidden');
    showView('overview');
    setInterval(() => { 
        document.getElementById('server-time').innerHTML = `<i class="fas fa-clock"></i> ${new Date().toLocaleTimeString('vi-VN')}`; 
    }, 1000);
    setInterval(() => { 
        if(document.getElementById('view-overview').classList.contains('hidden') === false) loadDashboard(); 
    }, 15000);
}

function showView(v) {
    document.querySelectorAll('.view-section').forEach(s => s.classList.add('hidden'));
    document.getElementById(`view-${v}`).classList.remove('hidden');
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    
    if(v === 'overview') { 
        document.querySelector('.nav-item:nth-child(1)').classList.add('active'); 
        loadDashboard(); 
    }
    if(v === 'sync') { 
        document.querySelector('.nav-item:nth-child(2)').classList.add('active'); 
        if (typeof loadSync === 'function') loadSync(); 
    }
    if(v === 'settings') { 
        document.querySelector('.nav-item:nth-child(3)').classList.add('active'); 
        loadSettings(); 
    }
}

function toggleCommFields() {
    const t = document.getElementById('comm-type-select').value;
    document.getElementById('fields-tcp').classList.toggle('hidden', t!=='TCP');
    document.getElementById('fields-rtu').classList.toggle('hidden', t!=='RTU');
}
