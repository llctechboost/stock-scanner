#!/usr/bin/env python3
"""
Activity Log / Retrospective Journal Dashboard (Port 5002)
Timeline view with lessons learned, stats, search/filter, REST API.
Dark theme, mobile responsive.
"""
from flask import Flask, render_template_string, jsonify, request
import json
import os
from datetime import datetime

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'activities.json')

TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📝 Activity Log - Retrospective Journal</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #fff; min-height: 100vh; }

/* Top bar */
.topbar { background: #111; border-bottom: 1px solid #222; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; position: sticky; top: 0; z-index: 100; }
.topbar h1 { color: #00ff88; font-size: 1.4em; }
.topbar .actions { display: flex; gap: 8px; }
.btn { background: #00ff88; color: #0a0a0a; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 0.85em; transition: opacity 0.2s; }
.btn:hover { opacity: 0.85; }
.btn.secondary { background: #333; color: #ccc; }
.btn.danger { background: #ff4444; color: #fff; }

/* Stats bar */
.stats-bar { background: #111; border-bottom: 1px solid #1a1a1a; padding: 16px 20px; display: flex; gap: 20px; flex-wrap: wrap; }
.stat-card { background: #1a1a1a; border-radius: 8px; padding: 14px 20px; text-align: center; min-width: 150px; flex: 1; }
.stat-card .stat-val { font-size: 1.8em; font-weight: 700; color: #00ff88; }
.stat-card .stat-label { font-size: 0.8em; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }

/* Search/Filter */
.filter-bar { padding: 12px 20px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; background: #0f0f0f; border-bottom: 1px solid #1a1a1a; }
.filter-bar input, .filter-bar select { background: #1a1a1a; color: #fff; border: 1px solid #333; border-radius: 6px; padding: 8px 12px; font-size: 0.85em; }
.filter-bar input { min-width: 200px; flex: 1; max-width: 400px; }
.filter-bar select { min-width: 140px; }
.filter-bar label { color: #888; font-size: 0.8em; }

/* Timeline */
.timeline { padding: 20px; max-width: 900px; margin: 0 auto; position: relative; }
.timeline::before { content: ''; position: absolute; left: 24px; top: 0; bottom: 0; width: 2px; background: #222; }

/* Activity card */
.activity-card { position: relative; margin-left: 50px; margin-bottom: 20px; background: #1a1a1a; border: 1px solid #222; border-radius: 10px; padding: 16px 18px; transition: border-color 0.2s; }
.activity-card:hover { border-color: #00ff88; }
.activity-card::before { content: ''; position: absolute; left: -34px; top: 18px; width: 12px; height: 12px; background: #00ff88; border-radius: 50%; border: 2px solid #0a0a0a; z-index: 1; }
.activity-card.blocked::before { background: #ff4444; }

.activity-card .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; flex-wrap: wrap; gap: 6px; }
.activity-card .act-id { color: #00ff88; font-family: monospace; font-size: 0.8em; font-weight: 700; }
.activity-card .timestamp { color: #666; font-size: 0.75em; }
.activity-card .status-badge { font-size: 0.7em; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; }
.activity-card .status-badge.completed { background: #00ff8822; color: #00ff88; }
.activity-card .status-badge.blocked { background: #ff444422; color: #ff4444; }

.activity-card .title { font-size: 1.1em; font-weight: 600; margin-bottom: 6px; color: #eee; }
.activity-card .description { font-size: 0.9em; color: #aaa; margin-bottom: 10px; line-height: 1.5; }
.activity-card .duration { color: #888; font-size: 0.85em; margin-bottom: 10px; }
.activity-card .duration strong { color: #00ff88; }

/* Retro sections */
.retro-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-bottom: 10px; }
.retro-box { background: #111; border-radius: 6px; padding: 10px; }
.retro-box .retro-label { font-size: 0.7em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; font-weight: 600; }
.retro-box .retro-label.good { color: #00ff88; }
.retro-box .retro-label.bad { color: #ff4444; }
.retro-box .retro-label.improve { color: #ffaa44; }
.retro-box .retro-text { font-size: 0.8em; color: #ccc; line-height: 1.4; }

.activity-card .blockers-list { margin-bottom: 8px; }
.activity-card .blocker-item { background: #ff444422; color: #ff4444; font-size: 0.8em; padding: 2px 8px; border-radius: 4px; display: inline-block; margin: 2px; }

.activity-card .tags-row { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.activity-card .tag { background: #222; color: #aaa; font-size: 0.7em; padding: 2px 8px; border-radius: 3px; }

.activity-card .card-actions { display: flex; gap: 6px; }
.activity-card .card-actions button { background: #222; border: none; color: #888; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.75em; }
.activity-card .card-actions button:hover { background: #333; color: #fff; }
.activity-card .card-actions button.del:hover { background: #ff4444; }

/* Empty state */
.empty { text-align: center; padding: 60px 20px; color: #555; }
.empty .icon { font-size: 3em; margin-bottom: 12px; }
.empty .hint { font-size: 0.9em; margin-top: 8px; }

/* Modal */
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 200; justify-content: center; align-items: center; }
.modal-overlay.active { display: flex; }
.modal { background: #111; border: 1px solid #333; border-radius: 12px; padding: 24px; width: 92%; max-width: 600px; max-height: 90vh; overflow-y: auto; }
.modal h2 { color: #00ff88; margin-bottom: 16px; font-size: 1.2em; }
.modal .form-group { margin-bottom: 12px; }
.modal label { display: block; color: #888; font-size: 0.8em; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
.modal input, .modal textarea, .modal select { width: 100%; background: #1a1a1a; color: #fff; border: 1px solid #333; border-radius: 6px; padding: 8px 10px; font-size: 0.9em; font-family: inherit; }
.modal textarea { resize: vertical; min-height: 60px; }
.modal input:focus, .modal textarea:focus, .modal select:focus { outline: none; border-color: #00ff88; }
.modal .btn-row { display: flex; gap: 8px; margin-top: 16px; }

/* Toast */
.toast { position: fixed; bottom: 20px; right: 20px; background: #00ff88; color: #0a0a0a; padding: 10px 20px; border-radius: 8px; font-weight: 600; z-index: 300; opacity: 0; transform: translateY(20px); transition: all 0.3s; }
.toast.show { opacity: 1; transform: translateY(0); }

/* Footer */
.footer { text-align: center; color: #444; font-size: 0.75em; padding: 20px; border-top: 1px solid #1a1a1a; margin-top: 20px; }

/* Responsive */
@media (max-width: 768px) {
    .stats-bar { flex-direction: column; }
    .stat-card { min-width: auto; }
    .timeline { padding: 12px; }
    .timeline::before { left: 16px; }
    .activity-card { margin-left: 36px; }
    .activity-card::before { left: -26px; }
    .retro-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<div class="topbar">
    <h1>📝 Activity Log</h1>
    <div class="actions">
        <button class="btn" onclick="openNewActivity()">➕ Log Activity</button>
        <button class="btn secondary" onclick="loadActivities()">🔄 Refresh</button>
    </div>
</div>

<div class="stats-bar" id="statsBar">
    <div class="stat-card">
        <div class="stat-val" id="statTotal">0</div>
        <div class="stat-label">Activities</div>
    </div>
    <div class="stat-card">
        <div class="stat-val" id="statTime">0h</div>
        <div class="stat-label">Total Time</div>
    </div>
    <div class="stat-card">
        <div class="stat-val" id="statBlockers">0</div>
        <div class="stat-label">Blockers</div>
    </div>
    <div class="stat-card">
        <div class="stat-val" id="statCompleted">0</div>
        <div class="stat-label">Completed</div>
    </div>
</div>

<div class="filter-bar">
    <input id="searchInput" placeholder="🔍 Search activities..." oninput="renderTimeline()">
    <div>
        <label>Tag</label>
        <select id="filterTag" onchange="renderTimeline()">
            <option value="all">All Tags</option>
        </select>
    </div>
    <div>
        <label>Status</label>
        <select id="filterStatus" onchange="renderTimeline()">
            <option value="all">All</option>
            <option value="Completed">Completed</option>
            <option value="Blocked">Blocked</option>
        </select>
    </div>
</div>

<div class="timeline" id="timeline"></div>

<div class="footer">
    Activity Log Dashboard &bull; Retrospective Journal &bull; Continuous Improvement
</div>

<!-- Modal -->
<div class="modal-overlay" id="actModal">
    <div class="modal">
        <h2 id="modalTitle">Log Activity</h2>
        <input type="hidden" id="editActId">
        <div class="form-group">
            <label>Title *</label>
            <input id="actTitle" placeholder="What did you do?">
        </div>
        <div class="form-group">
            <label>Description *</label>
            <textarea id="actDesc" placeholder="Detailed explanation of the work"></textarea>
        </div>
        <div class="form-group">
            <label>Duration</label>
            <input id="actDuration" placeholder="e.g., 30 min, 2 hours">
        </div>
        <div class="form-group">
            <label>Status</label>
            <select id="actStatus">
                <option>Completed</option>
                <option>Blocked</option>
            </select>
        </div>
        <div class="form-group">
            <label>Blockers (comma-separated)</label>
            <input id="actBlockers" placeholder="blocker1, blocker2">
        </div>
        <div class="form-group">
            <label>✅ What Worked</label>
            <textarea id="actWorked" placeholder="Successful approaches"></textarea>
        </div>
        <div class="form-group">
            <label>❌ What Didn't Work</label>
            <textarea id="actDidnt" placeholder="Problems encountered"></textarea>
        </div>
        <div class="form-group">
            <label>💡 Improvements</label>
            <textarea id="actImprove" placeholder="How to do it better next time"></textarea>
        </div>
        <div class="form-group">
            <label>Tags (comma-separated)</label>
            <input id="actTags" placeholder="scanner, web, troubleshooting">
        </div>
        <div class="btn-row">
            <button class="btn" onclick="saveActivity()">💾 Save</button>
            <button class="btn secondary" onclick="closeModal()">Cancel</button>
        </div>
    </div>
</div>

<div class="toast" id="toast"></div>

<script>
let activities = [];

async function loadActivities() {
    try {
        const res = await fetch('/api/activities');
        const data = await res.json();
        activities = data.activities || [];
        updateStats();
        updateTagFilter();
        renderTimeline();
        showToast('Activities loaded');
    } catch(e) { console.error(e); }
}

function updateStats() {
    document.getElementById('statTotal').textContent = activities.length;
    // Parse durations
    let totalMin = 0;
    let blockerCount = 0;
    let completedCount = 0;
    activities.forEach(a => {
        const dur = parseDuration(a.duration);
        totalMin += dur;
        blockerCount += (a.blockers || []).length;
        if (a.status === 'Completed') completedCount++;
    });
    const hours = Math.floor(totalMin / 60);
    const mins = totalMin % 60;
    document.getElementById('statTime').textContent = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
    document.getElementById('statBlockers').textContent = blockerCount;
    document.getElementById('statCompleted').textContent = completedCount;
}

function parseDuration(d) {
    if (!d) return 0;
    let mins = 0;
    const hourMatch = d.match(/(\d+\.?\d*)\s*h/i);
    const minMatch = d.match(/(\d+)\s*m/i);
    if (hourMatch) mins += parseFloat(hourMatch[1]) * 60;
    if (minMatch) mins += parseInt(minMatch[1]);
    if (!hourMatch && !minMatch) {
        const numMatch = d.match(/(\d+)/);
        if (numMatch) mins = parseInt(numMatch[1]);
    }
    return Math.round(mins);
}

function updateTagFilter() {
    const allTags = new Set();
    activities.forEach(a => (a.tags || []).forEach(t => allTags.add(t)));
    const sel = document.getElementById('filterTag');
    const cur = sel.value;
    sel.innerHTML = '<option value="all">All Tags</option>';
    [...allTags].sort().forEach(t => {
        const opt = document.createElement('option');
        opt.value = t; opt.textContent = t;
        sel.appendChild(opt);
    });
    sel.value = cur;
}

function getFiltered() {
    const search = document.getElementById('searchInput').value.toLowerCase().trim();
    const tag = document.getElementById('filterTag').value;
    const status = document.getElementById('filterStatus').value;

    return activities.filter(a => {
        if (tag !== 'all' && !(a.tags || []).includes(tag)) return false;
        if (status !== 'all' && a.status !== status) return false;
        if (search) {
            const text = [a.title, a.description, a.what_worked, a.what_didnt, a.improvements, ...(a.tags||[]), ...(a.blockers||[])].join(' ').toLowerCase();
            if (!text.includes(search)) return false;
        }
        return true;
    });
}

function renderTimeline() {
    const filtered = getFiltered();
    const tl = document.getElementById('timeline');

    if (filtered.length === 0) {
        tl.innerHTML = `<div class="empty"><div class="icon">📝</div><div>No activities logged yet</div><div class="hint">Click "Log Activity" to start tracking your work</div></div>`;
        return;
    }

    // Sort newest first
    const sorted = [...filtered].sort((a, b) => {
        return (b.timestamp || '').localeCompare(a.timestamp || '');
    });

    tl.innerHTML = sorted.map(a => activityCardHTML(a)).join('');
}

function activityCardHTML(a) {
    const statusClass = (a.status || 'Completed').toLowerCase();
    const blockers = (a.blockers || []).filter(Boolean).map(b => `<span class="blocker-item">🚫 ${escHtml(b)}</span>`).join('');
    const tags = (a.tags || []).map(t => `<span class="tag">${escHtml(t)}</span>`).join('');

    let retroHTML = '';
    if (a.what_worked || a.what_didnt || a.improvements) {
        retroHTML = '<div class="retro-grid">';
        if (a.what_worked) retroHTML += `<div class="retro-box"><div class="retro-label good">✅ What Worked</div><div class="retro-text">${escHtml(a.what_worked)}</div></div>`;
        if (a.what_didnt) retroHTML += `<div class="retro-box"><div class="retro-label bad">❌ What Didn't</div><div class="retro-text">${escHtml(a.what_didnt)}</div></div>`;
        if (a.improvements) retroHTML += `<div class="retro-box"><div class="retro-label improve">💡 Improvements</div><div class="retro-text">${escHtml(a.improvements)}</div></div>`;
        retroHTML += '</div>';
    }

    return `
    <div class="activity-card ${statusClass}" data-id="${a.id}">
        <div class="card-header">
            <div>
                <span class="act-id">${escHtml(a.id)}</span>
                <span class="timestamp">${escHtml(a.timestamp || '')}</span>
            </div>
            <span class="status-badge ${statusClass}">${escHtml(a.status || 'Completed')}</span>
        </div>
        <div class="title">${escHtml(a.title)}</div>
        ${a.description ? `<div class="description">${escHtml(a.description)}</div>` : ''}
        ${a.duration ? `<div class="duration">⏱️ Duration: <strong>${escHtml(a.duration)}</strong></div>` : ''}
        ${blockers ? `<div class="blockers-list">${blockers}</div>` : ''}
        ${retroHTML}
        ${tags ? `<div class="tags-row">${tags}</div>` : ''}
        <div class="card-actions">
            <button onclick="editActivity('${a.id}')">✏️ Edit</button>
            <button class="del" onclick="deleteActivity('${a.id}')">🗑️ Delete</button>
        </div>
    </div>`;
}

function escHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// CRUD
function openNewActivity() {
    document.getElementById('modalTitle').textContent = 'Log Activity';
    document.getElementById('editActId').value = '';
    ['actTitle','actDesc','actDuration','actBlockers','actWorked','actDidnt','actImprove','actTags'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('actStatus').value = 'Completed';
    document.getElementById('actModal').classList.add('active');
    setTimeout(() => document.getElementById('actTitle').focus(), 100);
}

function editActivity(id) {
    const a = activities.find(x => x.id === id);
    if (!a) return;
    document.getElementById('modalTitle').textContent = 'Edit Activity';
    document.getElementById('editActId').value = a.id;
    document.getElementById('actTitle').value = a.title || '';
    document.getElementById('actDesc').value = a.description || '';
    document.getElementById('actDuration').value = a.duration || '';
    document.getElementById('actStatus').value = a.status || 'Completed';
    document.getElementById('actBlockers').value = (a.blockers || []).join(', ');
    document.getElementById('actWorked').value = a.what_worked || '';
    document.getElementById('actDidnt').value = a.what_didnt || '';
    document.getElementById('actImprove').value = a.improvements || '';
    document.getElementById('actTags').value = (a.tags || []).join(', ');
    document.getElementById('actModal').classList.add('active');
    setTimeout(() => document.getElementById('actTitle').focus(), 100);
}

function closeModal() {
    document.getElementById('actModal').classList.remove('active');
}

async function saveActivity() {
    const title = document.getElementById('actTitle').value.trim();
    if (!title) { alert('Title is required'); return; }

    const payload = {
        title,
        description: document.getElementById('actDesc').value.trim(),
        duration: document.getElementById('actDuration').value.trim(),
        status: document.getElementById('actStatus').value,
        blockers: document.getElementById('actBlockers').value.split(',').map(s => s.trim()).filter(Boolean),
        what_worked: document.getElementById('actWorked').value.trim(),
        what_didnt: document.getElementById('actDidnt').value.trim(),
        improvements: document.getElementById('actImprove').value.trim(),
        tags: document.getElementById('actTags').value.split(',').map(s => s.trim()).filter(Boolean)
    };

    const editId = document.getElementById('editActId').value;
    try {
        if (editId) {
            await fetch(`/api/activities/${editId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            showToast('Activity updated');
        } else {
            await fetch('/api/activities', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            showToast('Activity logged');
        }
        closeModal();
        await loadActivities();
    } catch(e) { console.error(e); alert('Save failed'); }
}

async function deleteActivity(id) {
    if (!confirm(`Delete activity ${id}?`)) return;
    try {
        await fetch(`/api/activities/${id}`, { method: 'DELETE' });
        activities = activities.filter(a => a.id !== id);
        updateStats();
        renderTimeline();
        showToast('Activity deleted');
    } catch(e) { console.error(e); }
}

function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2000);
}

// Keyboard
document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
    if (e.key === 'Escape') closeModal();
});

// Init
loadActivities();
</script>
</body>
</html>'''


def load_activities():
    """Load activities from JSON file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            return data.get('activities', []) if isinstance(data, dict) else data
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_activities(activities):
    """Save activities to JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump({'activities': activities}, f, indent=2)


def next_activity_id(activities):
    """Generate next ACT-N id."""
    max_n = 0
    for a in activities:
        aid = a.get('id', '')
        if aid.startswith('ACT-'):
            try:
                n = int(aid.split('-')[1])
                max_n = max(max_n, n)
            except (ValueError, IndexError):
                pass
    return f"ACT-{max_n + 1}"


@app.route('/')
def index():
    return render_template_string(TEMPLATE)


@app.route('/api/activities', methods=['GET'])
def get_activities():
    activities = load_activities()
    return jsonify({'activities': activities})


@app.route('/api/activities', methods=['POST'])
def create_activity():
    data = request.get_json(force=True)
    activities = load_activities()
    activity = {
        'id': next_activity_id(activities),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'title': data.get('title', 'Untitled'),
        'description': data.get('description', ''),
        'duration': data.get('duration', ''),
        'status': data.get('status', 'Completed'),
        'blockers': data.get('blockers', []),
        'what_worked': data.get('what_worked', ''),
        'what_didnt': data.get('what_didnt', ''),
        'improvements': data.get('improvements', ''),
        'tags': data.get('tags', [])
    }
    activities.append(activity)
    save_activities(activities)
    return jsonify(activity), 201


@app.route('/api/activities/<act_id>', methods=['PUT'])
def update_activity(act_id):
    data = request.get_json(force=True)
    activities = load_activities()
    for a in activities:
        if a['id'] == act_id:
            for key in ['title', 'description', 'duration', 'status', 'blockers', 'what_worked', 'what_didnt', 'improvements', 'tags']:
                if key in data:
                    a[key] = data[key]
            save_activities(activities)
            return jsonify(a)
    return jsonify({'error': 'Activity not found'}), 404


@app.route('/api/activities/<act_id>', methods=['DELETE'])
def delete_activity(act_id):
    activities = load_activities()
    original_len = len(activities)
    activities = [a for a in activities if a['id'] != act_id]
    if len(activities) == original_len:
        return jsonify({'error': 'Activity not found'}), 404
    save_activities(activities)
    return jsonify({'deleted': act_id})


if __name__ == '__main__':
    print("\n📝 Activity Log Dashboard starting at http://localhost:5002\n")
    app.run(debug=False, host='0.0.0.0', port=5002)
