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
    console.log("Switching to view:", v);
    const debug = document.getElementById('ui-debug');
    if (debug) debug.innerText = "View: " + v;
    document.querySelectorAll('.view-section').forEach(s => s.classList.add('hidden'));
    const section = document.getElementById(`view-${v}`);
    if (section) {
        section.classList.remove('hidden');
    } else {
        console.error("View section not found for:", v);
    }
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    
    // Find the nav-item that has the onclick for this view
    const navItem = document.querySelector(`.nav-item[onclick*="showView('${v}')"]`);
    if (navItem) navItem.classList.add('active');

    if(v === 'overview') { 
        loadDashboard(); 
    }
    if(v === 'sync') { 
        console.log("Loading sync view data...");
        if (typeof loadSync === 'function') {
             loadSync().catch(e => {
                 console.error("loadSync error:", e);
                 if (debug) debug.innerText += " ERR: " + e.message;
             });
        } else console.error("loadSync function not defined!");
    }
    if(v === 'settings') { 
        loadSettings(); 
    }
    if(v === 'accounts') {
        loadAccounts();
    }
}

function toggleCommFields() {
    const t = document.getElementById('comm-type-select').value;
    document.getElementById('fields-tcp').classList.toggle('hidden', t!=='TCP');
    document.getElementById('fields-rtu').classList.toggle('hidden', t!=='RTU');
}
