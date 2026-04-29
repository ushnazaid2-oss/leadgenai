/* ============================================
   LeadGenAI — Dashboard Application Logic
   ============================================ */

const API = '';
let TOKEN = localStorage.getItem('leadgenai_token') || '';
let CHARTS = {};

// --- API Client ---
async function api(path, opts = {}) {
    const headers = { 'Content-Type': 'application/json', ...opts.headers };
    if (TOKEN) headers['Authorization'] = `Bearer ${TOKEN}`;
    try {
        const res = await fetch(`${API}${path}`, { ...opts, headers });
        if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
        if (res.status === 204) return null;
        if (!res.ok) {
            let msg = `Error ${res.status}`;
            try {
                const err = await res.json();
                msg = Array.isArray(err.detail) ? err.detail[0].msg : (err.detail || msg);
            } catch (e) {}
            throw new Error(msg);
        }
        if (res.headers.get('content-type')?.includes('json')) return res.json();
        return res;
    } catch (e) {
        console.error(`API Error: ${path}`, e);
        throw e;
    }
}

// --- Auth ---
function toggleAuthMode() {
    const af = document.getElementById('auth-form');
    const rf = document.getElementById('register-form');
    af.style.display = af.style.display === 'none' ? '' : 'none';
    rf.style.display = rf.style.display === 'none' ? '' : 'none';
}

function toggleTheme() {
    document.body.classList.toggle('light-mode');
    const isLight = document.body.classList.contains('light-mode');
    localStorage.setItem('leadgenai_theme', isLight ? 'light' : 'dark');
}

if (localStorage.getItem('leadgenai_theme') === 'light') {
    document.body.classList.add('light-mode');
}

async function loginUser() {
    const username = document.getElementById('auth-username').value;
    const password = document.getElementById('auth-password').value;
    if (!username || !password) return toast('Enter username and password', 'error');
    try {
        const data = await api('/api/auth/login', {
            method: 'POST', body: JSON.stringify({ username, password })
        });
        TOKEN = data.access_token;
        localStorage.setItem('leadgenai_token', TOKEN);
        localStorage.setItem('leadgenai_refresh', data.refresh_token);
        document.getElementById('auth-overlay').style.display = 'none';
        initDashboard();
        toast('Welcome back!', 'success');
    } catch (e) { toast(e.message || 'Login failed. Check credentials.', 'error'); }
}

async function registerUser() {
    const username = document.getElementById('reg-username').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    if (!username || !email || !password) return toast('Fill all fields', 'error');
    try {
        await api('/api/auth/register', {
            method: 'POST', body: JSON.stringify({ username, email, password })
        });
        toast('Registered! Please login.', 'success');
        toggleAuthMode();
    } catch (e) { toast(e.message || 'Registration failed.', 'error'); }
}

function logout() {
    TOKEN = '';
    localStorage.removeItem('leadgenai_token');
    localStorage.removeItem('leadgenai_refresh');
    document.getElementById('auth-overlay').style.display = 'flex';
}

// --- Navigation ---
function navigateTo(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');
    document.querySelector(`.nav-item[data-page="${page}"]`).classList.add('active');
    const titles = {
        dashboard: 'Dashboard', leads: 'Lead Management', campaigns: 'Campaigns',
        email: 'Email Outreach', whatsapp: 'WhatsApp', calls: 'AI Voice Calls', analytics: 'Analytics'
    };
    document.getElementById('page-title').textContent = titles[page] || page;
    // Load page data
    const loaders = { dashboard: loadDashboard, leads: loadLeads, campaigns: loadCampaigns,
        email: loadEmail, whatsapp: loadWhatsApp, calls: loadCalls, analytics: loadAnalytics };
    if (loaders[page]) loaders[page]();
}

// --- Dashboard ---
async function loadDashboard() {
    try {
        const data = await api('/api/analytics/dashboard');
        document.getElementById('dashboard-stats').innerHTML = [
            statCard('<i class="fa-solid fa-users"></i>', data.total_leads, 'Total Leads'),
            statCard('<i class="fa-solid fa-fire"></i>', data.hot_leads, 'Hot Leads'),
            statCard('<i class="fa-solid fa-bolt"></i>', data.new_leads_today, 'New Today'),
            statCard('<i class="fa-solid fa-envelope"></i>', data.emails_sent, 'Emails Sent'),
            statCard('<i class="fa-brands fa-whatsapp"></i>', data.whatsapp_sent, 'WhatsApp Sent'),
            statCard('<i class="fa-solid fa-phone"></i>', data.calls_made, 'Calls Made'),
            statCard('<i class="fa-solid fa-bullseye"></i>', data.conversion_rate + '%', 'Conversion'),
            statCard('<i class="fa-solid fa-rocket"></i>', data.active_campaigns, 'Active Campaigns'),
        ].join('');
        document.getElementById('lead-count-badge').textContent = data.total_leads;

        // Pipeline
        const pipeline = await api('/api/analytics/pipeline');
        document.getElementById('pipeline-stages').innerHTML = pipeline.stages
            .filter(s => !['lost'].includes(s.stage))
            .map(s => `<div class="pipeline-stage"><div class="stage-count">${s.count}</div>
                <div class="stage-name">${s.stage}</div>
                <div class="stage-bar"><div class="stage-bar-fill" style="width:${s.percentage}%"></div></div></div>`).join('');

        // Timeline chart
        const timeline = await api('/api/analytics/timeline?days=14');
        renderTimelineChart(timeline.data);

        // Channel chart
        const channels = await api('/api/analytics/channels');
        renderChannelChart(channels.channels);
    } catch (e) { console.error('Dashboard load error:', e); }
}

function statCard(icon, value, label) {
    return `<div class="stat-card"><div class="stat-icon">${icon}</div>
        <div class="stat-value">${value}</div><div class="stat-label">${label}</div></div>`;
}

// --- Charts ---
function renderTimelineChart(data) {
    if (CHARTS.timeline) CHARTS.timeline.destroy();
    const ctx = document.getElementById('timeline-chart');
    if (!ctx) return;
    CHARTS.timeline = new Chart(ctx, {
        type: 'line', data: {
            labels: data.map(d => d.date.slice(5)),
            datasets: [
                { label: 'Emails', data: data.map(d => d.emails_sent), borderColor: '#DC2626', tension: 0.4, fill: false },
                { label: 'WhatsApp', data: data.map(d => d.whatsapp_sent), borderColor: '#22C55E', tension: 0.4, fill: false },
                { label: 'Calls', data: data.map(d => d.calls_made), borderColor: '#3B82F6', tension: 0.4, fill: false },
            ]
        },
        options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#A3A3A3', font: { family: 'Inter', size: 11 } } } },
            scales: { x: { ticks: { color: '#6B6B6B' }, grid: { color: '#1E1E1E' } },
                      y: { ticks: { color: '#6B6B6B' }, grid: { color: '#1E1E1E' } } } }
    });
}

function renderChannelChart(channels) {
    if (CHARTS.channel) CHARTS.channel.destroy();
    const ctx = document.getElementById('channel-chart');
    if (!ctx) return;
    CHARTS.channel = new Chart(ctx, {
        type: 'doughnut', data: {
            labels: channels.map(c => c.channel.charAt(0).toUpperCase() + c.channel.slice(1)),
            datasets: [{ data: channels.map(c => c.total_sent), backgroundColor: ['#DC2626', '#22C55E', '#3B82F6'] }]
        },
        options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: '#A3A3A3', font: { family: 'Inter' }, padding: 20 } } } }
    });
}

// --- Leads ---
async function loadLeads() {
    try {
        const status = document.getElementById('lead-filter-status')?.value || '';
        const niche = document.getElementById('lead-filter-niche')?.value || '';
        let url = '/api/leads/?per_page=100';
        if (status) url += `&status=${status}`;
        if (niche) url += `&niche=${niche}`;
        const data = await api(url);
        const tbody = document.getElementById('leads-tbody');
        const empty = document.getElementById('leads-empty');
        if (!data.leads || data.leads.length === 0) {
            tbody.innerHTML = '';
            empty.style.display = '';
            return;
        }
        empty.style.display = 'none';
        tbody.innerHTML = data.leads.map(l => `<tr>
            <td><input type="checkbox" class="lead-checkbox" value="${l.id}" onchange="updateBulkActions()"></td>
            <td style="color:var(--text-muted);font-size:12px">#${l.id}</td>
            <td><strong>${esc(l.name)}</strong>${l.is_hot_lead ? ' <span class="badge badge-hot">🔥</span>' : ''}</td>
            <td>${esc(l.company || '-')}</td><td>${esc(l.email)}</td>
            <td style="font-family:var(--font-mono);font-size:12px">${esc(l.phone || '-')}</td>
            <td>${esc(l.niche || '-')}</td>
            <td><span class="badge badge-${l.status}">${l.status}</span></td>
            <td>
                <div style="display:flex; gap:5px">
                    <button class="btn btn-secondary btn-sm" onclick="showLeadDetail(${l.id})"><i class="fa-solid fa-eye"></i></button>
                    <button class="btn btn-secondary btn-sm" onclick="showEditLeadModal(${l.id})"><i class="fa-solid fa-pen"></i></button>
                    <button class="btn btn-danger btn-sm" onclick="deleteLead(${l.id})"><i class="fa-solid fa-trash"></i></button>
                </div>
            </td>
        </tr>`).join('');
        updateBulkActions();
    } catch (e) { console.error('Load leads error:', e); }
}

function showAddLeadModal() {
    openModal(`<h3>Add New Lead</h3>
        <div class="form-group"><label>Name *</label><input class="form-control" id="new-lead-name"></div>
        <div class="form-group"><label>Email *</label><input class="form-control" id="new-lead-email" type="email"></div>
        <div class="form-group"><label>Company</label><input class="form-control" id="new-lead-company"></div>
        <div class="form-group"><label>Phone</label><input class="form-control" id="new-lead-phone" placeholder="+1..."></div>
        <div class="form-group"><label>Niche</label><input class="form-control" id="new-lead-niche"></div>
        <button class="btn btn-primary" onclick="createLead()">Create Lead</button>`);
}

async function createLead() {
    const body = {
        name: document.getElementById('new-lead-name').value,
        email: document.getElementById('new-lead-email').value,
        company: document.getElementById('new-lead-company').value || null,
        phone: document.getElementById('new-lead-phone').value || null,
        niche: document.getElementById('new-lead-niche').value || null,
    };
    if (!body.name || !body.email) return toast('Name and email required', 'error');
    try {
        await api('/api/leads/', { method: 'POST', body: JSON.stringify(body) });
        closeModalDirect(); loadLeads(); toast('Lead created!', 'success');
    } catch (e) { toast('Failed to create lead', 'error'); }
}

function showImportModal() {
    openModal(`<h3>Import CSV</h3>
        <p style="color:var(--text-muted);margin-bottom:16px;font-size:13px">CSV must have columns: name, email. Optional: company, phone, niche</p>
        <div class="form-group"><label>CSV File</label><input type="file" accept=".csv" id="csv-file" class="form-control"></div>
        <button class="btn btn-primary" onclick="importCSV()">📁 Import</button>`);
}

async function importCSV() {
    const fileInput = document.getElementById('csv-file');
    if (!fileInput.files.length) return toast('Select a CSV file', 'error');
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    try {
        const res = await fetch(`${API}/api/leads/import/csv`, {
            method: 'POST', headers: { 'Authorization': `Bearer ${TOKEN}` }, body: formData
        });
        const data = await res.json();
        closeModalDirect(); loadLeads();
        toast(`Imported ${data.imported} leads (${data.duplicates} duplicates, ${data.skipped} skipped)`, 'success');
    } catch (e) { toast('CSV import failed', 'error'); }
}

// --- Campaigns ---
async function loadCampaigns() {
    try {
        const data = await api('/api/campaigns/');
        const tbody = document.getElementById('campaigns-tbody');
        const empty = document.getElementById('campaigns-empty');
        if (!data || data.length === 0) { tbody.innerHTML = ''; empty.style.display = ''; return; }
        empty.style.display = 'none';
        tbody.innerHTML = (data || []).map(c => {
            const progress = c.target_count > 0 ? Math.round((c.sent_count / c.target_count) * 100) : 0;
            return `<tr>
                <td><input type="checkbox" class="campaign-checkbox" value="${c.id}" onchange="updateCampaignBulkActions()"></td>
                <td><strong>${esc(c.name)}</strong></td>
                <td><span class="badge badge-secondary">${c.type}</span></td>
                <td>${esc(c.niche_filter || 'All')}</td>
                <td>${c.target_count}</td>
                <td>
                    <div style="font-size:11px; margin-bottom:4px">${c.sent_count} / ${c.target_count} (${progress}%)</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: ${progress}%"></div></div>
                </td>
                <td><span class="badge badge-${c.status}">${c.status}</span></td>
                <td>
                    <div style="display:flex; gap:5px">
                        ${c.status === 'draft' ? `<button class="btn btn-primary btn-sm" onclick="startCampaign(${c.id})"><i class="fa-solid fa-play"></i></button>` : ''}
                        <button class="btn btn-secondary btn-sm" onclick="showEditCampaignModal(${c.id})"><i class="fa-solid fa-pen"></i></button>
                        <button class="btn btn-danger btn-sm" onclick="deleteCampaign(${c.id})"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </td>
            </tr>`;
        }).join('');
        updateCampaignBulkActions();
    } catch (e) { console.error(e); }
}

async function showCreateCampaignModal() {
    let niches = [];
    try {
        niches = await api('/api/leads/niches');
    } catch (e) { console.error('Failed to load niches', e); }

    const nicheOptions = niches.map(n => `<option value="${esc(n)}">`).join('');

    openModal(`<h3>Create Campaign</h3>
        <div class="form-group"><label>Campaign Name</label><input class="form-control" id="camp-name" placeholder="Summer Outreach"></div>
        
        <div class="form-group">
            <label>Target Niches</label>
            <input class="form-control" id="camp-niche-input" list="niche-list" placeholder="Select a niche..." onchange="addNicheTag(this.value)">
            <datalist id="niche-list">${nicheOptions}</datalist>
            <div id="niche-tags-container" class="niche-tags-container"></div>
            <small style="color:var(--text-muted)">Select one or more niches. Click the (x) to remove.</small>
        </div>

        <div class="form-group">
            <label>Channel</label>
            <select class="form-control" id="camp-type" onchange="onCampaignTypeChange()">
                <option value="email">Email</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="call">Voice Call</option>
            </select>
        </div>

        <div class="form-group" id="camp-subject-group">
            <label>Email Subject</label>
            <input class="form-control" id="camp-subject" placeholder="Hi {name}, I have a question">
        </div>

        <div class="form-group">
            <label id="camp-body-label">Template / Script</label>
            <textarea class="form-control" id="camp-body" rows="5" placeholder="Hi {name}, ..."></textarea>
        </div>
        
        <button class="btn btn-primary" onclick="createCampaign()">Create Campaign</button>`);
    
    // Initial trigger to set correct visibility
    onCampaignTypeChange();
}

function onCampaignTypeChange() {
    const type = document.getElementById('camp-type').value;
    const subjectGroup = document.getElementById('camp-subject-group');
    const bodyLabel = document.getElementById('camp-body-label');
    const bodyText = document.getElementById('camp-body');

    if (type === 'email') {
        subjectGroup.style.display = 'block';
        bodyLabel.textContent = 'Email Body (HTML)';
        bodyText.placeholder = "Hello {name}, I noticed {company} has been...";
    } else if (type === 'whatsapp') {
        subjectGroup.style.display = 'none';
        bodyLabel.textContent = 'WhatsApp Message / Template Name';
        bodyText.placeholder = "e.g. business_intro";
    } else {
        subjectGroup.style.display = 'none';
        bodyLabel.textContent = 'AI Voice Call Script';
        bodyText.placeholder = "Hi {name}, this is Alex from {company}...";
    }
}

async function createCampaign() {
    try {
        const niches = Array.from(document.querySelectorAll('.niche-tag-text')).map(el => el.textContent);
        await api('/api/campaigns/', { method: 'POST', body: JSON.stringify({
            name: document.getElementById('camp-name').value,
            type: document.getElementById('camp-type').value,
            niche_filter: niches.join(','),
            subject: document.getElementById('camp-subject').value || null,
            body: document.getElementById('camp-body').value || null,
        })});
        closeModalDirect(); loadCampaigns(); toast('Campaign created!', 'success');
    } catch (e) { toast('Failed: ' + e.message, 'error'); }
}

function addNicheTag(val) {
    if (!val) return;
    const container = document.getElementById('niche-tags-container');
    // Check if already exists
    const existing = Array.from(container.querySelectorAll('.niche-tag-text')).map(el => el.textContent);
    if (existing.includes(val)) {
        document.getElementById('camp-niche-input').value = '';
        return;
    }

    const tag = document.createElement('div');
    tag.className = 'niche-tag';
    tag.innerHTML = `<span class="niche-tag-text">${esc(val)}</span><span class="remove-tag" onclick="this.parentElement.remove()">×</span>`;
    container.appendChild(tag);
    document.getElementById('camp-niche-input').value = '';
}

async function startCampaign(id) {
    if (!confirm('Are you sure you want to start this campaign now?')) return;
    try {
        const res = await api(`/api/campaigns/${id}/start`, { method: 'POST' });
        toast(`Campaign started! Targeting ${res.leads_targeted} leads.`, 'success');
        loadCampaigns();
    } catch (e) { toast('Failed to start: ' + e.message, 'error'); }
}

// --- Email ---
async function loadEmail() {
    try {
        const stats = await api('/api/email/stats');
        document.getElementById('email-stats').innerHTML = [
            statCard('<i class="fa-solid fa-paper-plane"></i>', stats.total_sent, 'Total Sent'),
            statCard('<i class="fa-solid fa-eye"></i>', stats.opened, 'Opened'),
            statCard('<i class="fa-solid fa-hand-pointer"></i>', stats.clicked, 'Clicked'),
            statCard('<i class="fa-solid fa-chart-simple"></i>', stats.open_rate + '%', 'Open Rate'),
        ].join('');
        loadEmailAccounts();
    } catch (e) { console.error(e); }
}

async function loadEmailAccounts() {
    try {
        const accounts = await api('/api/email/accounts');
        const list = document.getElementById('email-accounts-list');
        if (!accounts || accounts.length === 0) {
            list.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px;">No accounts connected.</p>';
            return;
        }
        list.innerHTML = accounts.map(a => `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-bottom:1px solid var(--border-color)">
                <div>
                    <div style="font-weight:600">${esc(a.name)}</div>
                    <div style="font-size:12px; color:var(--text-muted)">${esc(a.email)} (${a.provider})</div>
                </div>
                <div style="text-align:right">
                    <div style="font-size:12px">${a.sent_today} / ${a.daily_limit} today</div>
                    <span class="badge badge-${a.is_active ? 'active' : 'failed'}">${a.is_active ? 'Active' : 'Inactive'}</span>
                    <div style="margin-top:5px">
                        <button class="btn btn-secondary btn-sm" onclick="showEditAccountModal(${a.id})" title="Edit Name"><i class="fa-solid fa-pen"></i></button>
                        <button class="btn btn-danger btn-sm" onclick="deleteAccount(${a.id})" title="Delete"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) { console.error(e); }
}

function showAddAccountModal() {
    openModal(`<h3>Connect Email Account</h3>
        <div class="form-group"><label>Account Name (e.g. Sales)</label><input class="form-control" id="acc-name"></div>
        <div class="form-group"><label>Email Address</label><input class="form-control" id="acc-email" type="email"></div>
        <div class="form-group"><label>Provider</label>
            <select class="form-control" id="acc-provider" onchange="onEmailProviderChange()">
                <option value="gmail">Gmail</option>
                <option value="sendgrid">SendGrid</option>
                <option value="custom_smtp">Custom SMTP</option>
            </select>
        </div>

        <div id="acc-smtp-fields">
            <div class="form-group"><label>App Password / SMTP Password</label><input class="form-control" id="acc-pass" type="password"></div>
            <div class="form-group"><label>SMTP Host</label><input class="form-control" id="acc-host" value="smtp.gmail.com"></div>
            <div class="form-group"><label>SMTP Port</label><input class="form-control" id="acc-port" value="587" type="number"></div>
        </div>

        <div id="acc-sendgrid-fields" style="display:none">
            <div class="form-group"><label>SendGrid API Key</label><input class="form-control" id="acc-sg-key" type="password"></div>
        </div>

        <div class="form-group"><label>Daily Sending Limit</label><input class="form-control" id="acc-limit" value="500" type="number"></div>
        
        <button class="btn btn-primary" onclick="createEmailAccount()">Connect Account</button>`);
}

function onEmailProviderChange() {
    const provider = document.getElementById('acc-provider').value;
    const smtpFields = document.getElementById('acc-smtp-fields');
    const sgFields = document.getElementById('acc-sendgrid-fields');
    const host = document.getElementById('acc-host');

    if (provider === 'sendgrid') {
        smtpFields.style.display = 'none';
        sgFields.style.display = 'block';
    } else {
        smtpFields.style.display = 'block';
        sgFields.style.display = 'none';
        if (provider === 'gmail') {
            host.value = 'smtp.gmail.com';
        } else {
            host.value = '';
        }
    }
}

async function createEmailAccount() {
    try {
        const body = {
            name: document.getElementById('acc-name').value,
            email: document.getElementById('acc-email').value,
            provider: document.getElementById('acc-provider').value,
            daily_limit: parseInt(document.getElementById('acc-limit').value),
            password: document.getElementById('acc-pass').value || null,
            smtp_host: document.getElementById('acc-host').value || null,
            smtp_port: parseInt(document.getElementById('acc-port').value) || 587,
            sendgrid_api_key: document.getElementById('acc-sg-key').value || null,
        };
        await api('/api/email/accounts', { method: 'POST', body: JSON.stringify(body) });
        closeModalDirect(); loadEmail(); toast('Account connected!', 'success');
    } catch (e) { toast('Failed: ' + e.message, 'error'); }
}

async function sendSingleEmail() {
    const input = document.getElementById('email-lead-id').value.trim();
    const subject = document.getElementById('email-subject').value;
    const body = document.getElementById('email-body').value;
    
    if (!input || !subject) return toast('Recipient and subject required', 'error');

    let leadId = parseInt(input);
    
    // If input is an email address, try to find the lead ID
    if (isNaN(leadId) && input.includes('@')) {
        try {
            const data = await api(`/api/leads/?search=${encodeURIComponent(input)}`);
            if (data.leads && data.leads.length > 0) {
                leadId = data.leads[0].id;
            } else {
                return toast('Lead not found. Please add this lead first.', 'error');
            }
        } catch (e) { return toast('Error looking up lead', 'error'); }
    }

    if (!leadId) return toast('Invalid Recipient ID', 'error');

    try {
        await api('/api/email/send', { method: 'POST', body: JSON.stringify({
            lead_id: leadId, subject, body_html: body || ''
        })});
        toast('Email sent successfully!', 'success');
    } catch (e) { toast('Failed to send: ' + e.message, 'error'); }
}

// --- WhatsApp ---
async function loadWhatsApp() {
    try {
        const logs = await api('/api/whatsapp/logs?per_page=50');
        document.getElementById('whatsapp-tbody').innerHTML = (logs || []).map(l =>
            `<tr><td>${l.lead_id}</td><td>${esc(l.template_name || '-')}</td>
            <td>${l.direction}</td><td><span class="badge badge-${l.status}">${l.status}</span></td>
            <td>${l.sent_at ? new Date(l.sent_at).toLocaleString() : '-'}</td></tr>`
        ).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No messages yet</td></tr>';
    } catch (e) { console.error(e); }
}

async function sendWhatsApp() {
    const leadId = parseInt(document.getElementById('wa-lead-id').value);
    const template = document.getElementById('wa-template').value;
    if (!leadId || !template) return toast('Lead ID and template required', 'error');
    try {
        await api('/api/whatsapp/send', { method: 'POST', body: JSON.stringify({ lead_id: leadId, template_name: template })});
        toast('WhatsApp sent!', 'success'); loadWhatsApp();
    } catch (e) { toast('Failed', 'error'); }
}

// --- Calls ---
async function loadCalls() {
    try {
        const stats = await api('/api/calls/stats');
        document.getElementById('call-stats').innerHTML = [
            statCard('<i class="fa-solid fa-phone"></i>', stats.total_calls, 'Total Calls'),
            statCard('<i class="fa-solid fa-circle-check"></i>', stats.connected, 'Connected'),
            statCard('<i class="fa-solid fa-bullseye"></i>', stats.interested, 'Interested'),
            statCard('<i class="fa-solid fa-fire"></i>', stats.hot_leads, 'Hot Leads'),
        ].join('');
        const logs = await api('/api/calls/logs?per_page=50');
        document.getElementById('calls-tbody').innerHTML = (logs || []).map(l =>
            `<tr><td>${l.lead_id}</td><td style="font-family:var(--font-mono);font-size:12px">${esc(l.from_number)}</td>
            <td style="font-family:var(--font-mono);font-size:12px">${esc(l.to_number)}</td>
            <td>${l.duration_seconds}s</td>
            <td><span class="badge badge-${l.outcome || 'new'}">${l.outcome || 'pending'}</span></td>
            <td>${l.is_hot_lead ? '🔥' : '-'}</td>
            <td>${l.created_at ? new Date(l.created_at).toLocaleString() : '-'}</td></tr>`
        ).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">No calls yet</td></tr>';
    } catch (e) { console.error(e); }
}

async function initiateCall() {
    const leadId = parseInt(document.getElementById('call-lead-id').value);
    if (!leadId) return toast('Lead ID required', 'error');
    try {
        const result = await api('/api/calls/initiate', { method: 'POST', body: JSON.stringify({
            lead_id: leadId,
            from_number: document.getElementById('call-from').value || null,
            call_script: document.getElementById('call-script').value || null,
        })});
        toast(`Call initiated: ${result.call_sid}`, 'success'); loadCalls();
    } catch (e) { toast('Call failed', 'error'); }
}

async function deleteLead(id) {
    if (!confirm('Are you sure you want to delete this lead?')) return;
    try {
        await api(`/api/leads/${id}`, { method: 'DELETE' });
        loadLeads(); toast('Lead deleted', 'success');
    } catch (e) { toast('Failed to delete', 'error'); }
}

async function showEditLeadModal(id) {
    try {
        const l = await api(`/api/leads/${id}`);
        openModal(`<h3>Edit Lead</h3>
            <div class="form-group"><label>Name</label><input class="form-control" id="edit-lead-name" value="${esc(l.name)}"></div>
            <div class="form-group"><label>Email</label><input class="form-control" id="edit-lead-email" value="${esc(l.email)}"></div>
            <div class="form-group"><label>Company</label><input class="form-control" id="edit-lead-company" value="${esc(l.company || '')}"></div>
            <div class="form-group"><label>Phone</label><input class="form-control" id="edit-lead-phone" value="${esc(l.phone || '')}"></div>
            <div class="form-group"><label>Niche</label><input class="form-control" id="edit-lead-niche" value="${esc(l.niche || '')}"></div>
            <button class="btn btn-primary" onclick="updateLead(${l.id})">Save Changes</button>`);
    } catch (e) { toast('Failed to load lead data', 'error'); }
}

async function updateLead(id) {
    try {
        await api(`/api/leads/${id}`, { method: 'PUT', body: JSON.stringify({
            name: document.getElementById('edit-lead-name').value,
            email: document.getElementById('edit-lead-email').value,
            company: document.getElementById('edit-lead-company').value,
            phone: document.getElementById('edit-lead-phone').value,
            niche: document.getElementById('edit-lead-niche').value,
        })});
        closeModalDirect(); loadLeads(); toast('Lead updated', 'success');
    } catch (e) { toast('Update failed: ' + e.message, 'error'); }
}

function toggleSelectAll(source) {
    const checkboxes = document.querySelectorAll('.lead-checkbox');
    checkboxes.forEach(c => c.checked = source.checked);
    updateBulkActions();
}

function updateBulkActions() {
    const selectedCount = document.querySelectorAll('.lead-checkbox:checked').length;
    const bar = document.getElementById('bulk-actions');
    const btn = document.getElementById('btn-delete-selected');
    if (selectedCount > 0) {
        bar.style.display = 'block';
        btn.innerHTML = `<i class="fa-solid fa-trash"></i> Delete ${selectedCount} Selected`;
    } else {
        bar.style.display = 'none';
    }
}

async function deleteSelectedLeads() {
    const selected = Array.from(document.querySelectorAll('.lead-checkbox:checked')).map(c => parseInt(c.value));
    if (selected.length === 0) return;
    if (!confirm(`Delete ${selected.length} leads?`)) return;

    let successCount = 0;
    for (const id of selected) {
        try {
            await api(`/api/leads/${id}`, { method: 'DELETE' });
            successCount++;
        } catch (e) { console.error(`Failed to delete lead ${id}`, e); }
    }
    loadLeads();
    toast(`Successfully deleted ${successCount} leads`, 'success');
}
async function deleteCampaign(id) {
    if (!confirm('Are you sure you want to delete this campaign?')) return;
    try {
        await api(`/api/campaigns/${id}`, { method: 'DELETE' });
        loadCampaigns(); toast('Campaign deleted', 'success');
    } catch (e) { toast('Failed to delete', 'error'); }
}

async function showEditCampaignModal(id) {
    try {
        const c = await api(`/api/campaigns/${id}`);
        openModal(`<h3>Edit Campaign</h3>
            <div class="form-group"><label>Campaign Name</label><input class="form-control" id="edit-camp-name" value="${esc(c.name)}"></div>
            <div class="form-group"><label>Subject</label><input class="form-control" id="edit-camp-subject" value="${esc(c.subject || '')}"></div>
            <div class="form-group"><label>Template / Script</label><textarea class="form-control" id="edit-camp-body" rows="5">${esc(c.body || '')}</textarea></div>
            <button class="btn btn-primary" onclick="updateCampaign(${c.id})">Save Changes</button>`);
    } catch (e) { toast('Failed to load campaign', 'error'); }
}

async function updateCampaign(id) {
    try {
        await api(`/api/campaigns/${id}`, { method: 'PUT', body: JSON.stringify({
            name: document.getElementById('edit-camp-name').value,
            subject: document.getElementById('edit-camp-subject').value,
            body: document.getElementById('edit-camp-body').value,
        })});
        closeModalDirect(); loadCampaigns(); toast('Campaign updated', 'success');
    } catch (e) { toast('Update failed', 'error'); }
}

function toggleSelectAllCampaigns(source) {
    const checkboxes = document.querySelectorAll('.campaign-checkbox');
    checkboxes.forEach(c => c.checked = source.checked);
    updateCampaignBulkActions();
}

function updateCampaignBulkActions() {
    const selectedCount = document.querySelectorAll('.campaign-checkbox:checked').length;
    const bar = document.getElementById('campaign-bulk-actions');
    if (selectedCount > 0) {
        bar.style.display = 'block';
    } else {
        bar.style.display = 'none';
    }
}

async function deleteSelectedCampaigns() {
    const selected = Array.from(document.querySelectorAll('.campaign-checkbox:checked')).map(c => parseInt(c.value));
    if (selected.length === 0) return;
    if (!confirm(`Delete ${selected.length} campaigns?`)) return;

    for (const id of selected) {
        try { await api(`/api/campaigns/${id}`, { method: 'DELETE' }); } catch (e) {}
    }
    loadCampaigns();
    toast('Campaigns deleted', 'success');
}

async function loadAnalytics() {
    try {
        const pipeline = await api('/api/analytics/pipeline');
        renderFunnelChart(pipeline.stages);
        const timeline = await api('/api/analytics/timeline?days=30');
        renderTrendChart(timeline.data);
    } catch (e) { console.error(e); }
}

function renderFunnelChart(stages) {
    if (CHARTS.funnel) CHARTS.funnel.destroy();
    const ctx = document.getElementById('funnel-chart');
    if (!ctx) return;
    const filtered = stages.filter(s => !['lost'].includes(s.stage));
    CHARTS.funnel = new Chart(ctx, {
        type: 'bar', data: {
            labels: filtered.map(s => s.stage.charAt(0).toUpperCase() + s.stage.slice(1)),
            datasets: [{ data: filtered.map(s => s.count),
                backgroundColor: ['#3B82F6','#6366F1','#8B5CF6','#A855F7','#DC2626','#EF4444','#22C55E'],
                borderRadius: 6 }]
        },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { ticks: { color: '#6B6B6B' }, grid: { color: '#1E1E1E' } },
                      y: { ticks: { color: '#A3A3A3', font: { family: 'Inter' } }, grid: { display: false } } } }
    });
}

function renderTrendChart(data) {
    if (CHARTS.trend) CHARTS.trend.destroy();
    const ctx = document.getElementById('trend-chart');
    if (!ctx) return;
    CHARTS.trend = new Chart(ctx, {
        type: 'bar', data: {
            labels: data.map(d => d.date.slice(5)),
            datasets: [
                { label: 'Emails', data: data.map(d => d.emails_sent), backgroundColor: '#DC262680' },
                { label: 'WhatsApp', data: data.map(d => d.whatsapp_sent), backgroundColor: '#22C55E80' },
                { label: 'Calls', data: data.map(d => d.calls_made), backgroundColor: '#3B82F680' },
            ]
        },
        options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#A3A3A3' } } },
            scales: { x: { stacked: true, ticks: { color: '#6B6B6B' }, grid: { color: '#1E1E1E' } },
                      y: { stacked: true, ticks: { color: '#6B6B6B' }, grid: { color: '#1E1E1E' } } } }
    });
}

// --- Exports ---
function exportReport(format) {
    const url = format === 'pdf' ? '/api/analytics/export/pdf' : '/api/analytics/export/excel';
    window.open(url, '_blank');
}

// --- Utils ---
function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

function handleGlobalSearch(e) {
    if (e.key === 'Enter') { navigateTo('leads'); /* Search handled in loadLeads */ }
}

function showLeadDetail(id) {
    toast(`Lead #${id} detail view — coming soon!`, 'info');
}

// --- Modal ---
function openModal(html) {
    document.getElementById('modal-content').innerHTML = html;
    document.getElementById('modal-overlay').classList.add('active');
}
function closeModal(e) { if (e.target.id === 'modal-overlay') closeModalDirect(); }
function closeModalDirect() { document.getElementById('modal-overlay').classList.remove('active'); }

// --- Toast ---
function toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<span>${msg}</span>`;
    container.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 4000);
}

function toggleUserMenu() { logout(); }

// --- Init ---
function initDashboard() {
    loadDashboard();
}

// Check auth on load
if (TOKEN) {
    document.getElementById('auth-overlay').style.display = 'none';
    initDashboard();
}
async function deleteAccount(id) {
    if (!confirm('Are you sure you want to delete this email account?')) return;
    try {
        await api(`/api/email/accounts/${id}`, { method: 'DELETE' });
        loadEmailAccounts(); toast('Account deleted', 'success');
    } catch (e) { toast('Delete failed', 'error'); }
}

async function showEditAccountModal(id) {
    try {
        const accounts = await api('/api/email/accounts');
        const acc = accounts.find(a => a.id === id);
        openModal(`<h3>Edit Account Name</h3>
            <div class="form-group">
                <label>Sender Name (How you appear in inboxes)</label>
                <input class="form-control" id="edit-acc-name" value="${esc(acc.name)}">
            </div>
            <button class="btn btn-primary" onclick="updateEmailAccount(${id})">Save Name</button>`);
    } catch (e) { toast('Failed to load account', 'error'); }
}

async function updateEmailAccount(id) {
    try {
        const name = document.getElementById('edit-acc-name').value;
        await api(`/api/email/accounts/${id}`, { method: 'PUT', body: JSON.stringify({ name }) });
        closeModalDirect(); loadEmailAccounts(); toast('Name updated!', 'success');
    } catch (e) { toast('Update failed', 'error'); }
}
