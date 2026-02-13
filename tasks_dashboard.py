#!/usr/bin/env python3
"""
Kanban Task Board Dashboard (Port 5001)
Jira-style task management with drag-and-drop, REST API, keyboard shortcuts.
Dark theme, mobile responsive.
"""
from flask import Flask, render_template_string, jsonify, request
import json
import os
from datetime import datetime

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.json')

COLUMNS = ['Backlog', 'To Do', 'In Progress', 'Blocked', 'Testing', 'Done']
PRIORITIES = ['High', 'Medium', 'Low']

TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📋 Kanban Task Board</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #fff; min-height: 100vh; }

/* Top bar */
.topbar { background: #111; border-bottom: 1px solid #222; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; position: sticky; top: 0; z-index: 100; }
.topbar h1 { color: #00ff88; font-size: 1.4em; }
.topbar .actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.btn { background: #00ff88; color: #0a0a0a; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 0.85em; transition: opacity 0.2s; }
.btn:hover { opacity: 0.85; }
.btn.secondary { background: #333; color: #ccc; }
.btn.danger { background: #ff4444; color: #fff; }
.btn .kbd { background: #0a0a0a33; padding: 1px 5px; border-radius: 3px; font-size: 0.8em; margin-left: 4px; }

/* Filters */
.filter-bar { background: #0f0f0f; border-bottom: 1px solid #1a1a1a; padding: 10px 20px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
.filter-bar select, .filter-bar input { background: #1a1a1a; color: #fff; border: 1px solid #333; border-radius: 6px; padding: 6px 10px; font-size: 0.85em; }
.filter-bar select { min-width: 130px; }
.filter-bar input { min-width: 160px; }
.filter-bar label { color: #888; font-size: 0.8em; }

/* Board */
.board { display: flex; gap: 12px; padding: 16px 20px; overflow-x: auto; min-height: calc(100vh - 120px); }
.column { flex: 0 0 280px; background: #111; border: 1px solid #1a1a1a; border-radius: 10px; display: flex; flex-direction: column; max-height: calc(100vh - 140px); }
.column.drag-over { border-color: #00ff88; background: #0a1a10; }
.col-header { padding: 12px 14px; border-bottom: 1px solid #1a1a1a; display: flex; justify-content: space-between; align-items: center; }
.col-header h3 { font-size: 0.9em; color: #ccc; }
.col-header .badge { background: #222; color: #888; font-size: 0.75em; padding: 2px 8px; border-radius: 10px; }
.col-body { flex: 1; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 8px; min-height: 60px; }

/* Task card */
.task-card { background: #1a1a1a; border: 1px solid #222; border-radius: 8px; padding: 12px; cursor: grab; transition: border-color 0.2s, transform 0.15s, opacity 0.2s; }
.task-card:hover { border-color: #00ff88; }
.task-card.dragging { opacity: 0.4; transform: scale(0.95); }
.task-card .card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }
.task-card .task-id { color: #888; font-size: 0.75em; font-family: monospace; }
.task-card .priority { font-size: 0.7em; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; }
.task-card .priority.high { background: #ff444433; color: #ff4444; }
.task-card .priority.medium { background: #ffaa4433; color: #ffaa44; }
.task-card .priority.low { background: #44aaff33; color: #44aaff; }
.task-card .title { font-size: 0.95em; font-weight: 600; margin-bottom: 4px; color: #eee; }
.task-card .desc { font-size: 0.8em; color: #888; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.task-card .meta-row { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 4px; }
.task-card .tag { background: #222; color: #aaa; font-size: 0.7em; padding: 1px 6px; border-radius: 3px; }
.task-card .blocker-badge { background: #ff444433; color: #ff4444; font-size: 0.7em; padding: 1px 6px; border-radius: 3px; }
.task-card .assignee { color: #00ff88; font-size: 0.75em; }
.task-card .due { font-size: 0.7em; color: #888; }
.task-card .due.overdue { color: #ff4444; font-weight: 600; }
.task-card .card-actions { display: flex; gap: 6px; margin-top: 8px; }
.task-card .card-actions button { background: #222; border: none; color: #888; padding: 3px 8px; border-radius: 4px; cursor: pointer; font-size: 0.75em; }
.task-card .card-actions button:hover { background: #333; color: #fff; }
.task-card .card-actions button.del:hover { background: #ff4444; }

/* Modal */
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 200; justify-content: center; align-items: center; }
.modal-overlay.active { display: flex; }
.modal { background: #111; border: 1px solid #333; border-radius: 12px; padding: 24px; width: 90%; max-width: 500px; max-height: 90vh; overflow-y: auto; }
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

/* Responsive */
@media (max-width: 768px) {
    .board { flex-direction: column; }
    .column { flex: none; width: 100%; max-height: none; }
}
</style>
</head>
<body>

<div class="topbar">
    <h1>📋 Kanban Board</h1>
    <div class="actions">
        <button class="btn" onclick="openNewTask()">➕ New Task <span class="kbd">N</span></button>
        <button class="btn secondary" onclick="loadBoard()">🔄 Refresh <span class="kbd">R</span></button>
    </div>
</div>

<div class="filter-bar">
    <div>
        <label>Priority</label>
        <select id="filterPriority" onchange="renderBoard()">
            <option value="all">All</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
        </select>
    </div>
    <div>
        <label>Assignee</label>
        <select id="filterAssignee" onchange="renderBoard()">
            <option value="all">All</option>
        </select>
    </div>
    <div>
        <label>Tag</label>
        <input id="filterTag" placeholder="Filter by tag..." oninput="renderBoard()">
    </div>
</div>

<div class="board" id="board"></div>

<!-- New/Edit Task Modal -->
<div class="modal-overlay" id="taskModal">
    <div class="modal">
        <h2 id="modalTitle">New Task</h2>
        <input type="hidden" id="editTaskId">
        <div class="form-group">
            <label>Title *</label>
            <input id="taskTitleInput" placeholder="Task title" required>
        </div>
        <div class="form-group">
            <label>Description</label>
            <textarea id="taskDescInput" placeholder="Task description"></textarea>
        </div>
        <div class="form-group">
            <label>Status</label>
            <select id="taskStatusInput">
                <option>Backlog</option><option>To Do</option><option>In Progress</option>
                <option>Blocked</option><option>Testing</option><option>Done</option>
            </select>
        </div>
        <div class="form-group">
            <label>Priority</label>
            <select id="taskPriorityInput">
                <option>Medium</option><option>High</option><option>Low</option>
            </select>
        </div>
        <div class="form-group">
            <label>Assignee</label>
            <input id="taskAssigneeInput" placeholder="Assignee name">
        </div>
        <div class="form-group">
            <label>Due Date</label>
            <input type="date" id="taskDueInput">
        </div>
        <div class="form-group">
            <label>Blockers (comma-separated)</label>
            <input id="taskBlockersInput" placeholder="blocker1, blocker2">
        </div>
        <div class="form-group">
            <label>Tags (comma-separated)</label>
            <input id="taskTagsInput" placeholder="tag1, tag2">
        </div>
        <div class="btn-row">
            <button class="btn" onclick="saveTask()">💾 Save</button>
            <button class="btn secondary" onclick="closeModal()">Cancel</button>
        </div>
    </div>
</div>

<div class="toast" id="toast"></div>

<script>
const COLUMNS = ['Backlog', 'To Do', 'In Progress', 'Blocked', 'Testing', 'Done'];
let tasks = [];
let draggedId = null;

async function loadBoard() {
    try {
        const res = await fetch('/api/tasks');
        const data = await res.json();
        tasks = data.tasks || [];
        updateFilterOptions();
        renderBoard();
        showToast('Board refreshed');
    } catch(e) {
        console.error('Load failed:', e);
    }
}

function updateFilterOptions() {
    const assignees = [...new Set(tasks.map(t => t.assignee).filter(a => a))];
    const sel = document.getElementById('filterAssignee');
    const cur = sel.value;
    sel.innerHTML = '<option value="all">All</option>';
    assignees.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a; opt.textContent = a;
        sel.appendChild(opt);
    });
    sel.value = cur;
}

function getFilteredTasks() {
    const priority = document.getElementById('filterPriority').value;
    const assignee = document.getElementById('filterAssignee').value;
    const tag = document.getElementById('filterTag').value.toLowerCase().trim();
    return tasks.filter(t => {
        if (priority !== 'all' && t.priority !== priority) return false;
        if (assignee !== 'all' && t.assignee !== assignee) return false;
        if (tag && !(t.tags || []).some(tg => tg.toLowerCase().includes(tag))) return false;
        return true;
    });
}

function renderBoard() {
    const board = document.getElementById('board');
    const filtered = getFilteredTasks();
    board.innerHTML = '';

    COLUMNS.forEach(col => {
        const colTasks = filtered.filter(t => t.status === col);
        const colEl = document.createElement('div');
        colEl.className = 'column';
        colEl.dataset.status = col;
        colEl.innerHTML = `
            <div class="col-header">
                <h3>${col}</h3>
                <span class="badge">${colTasks.length}</span>
            </div>
            <div class="col-body" ondragover="onDragOver(event)" ondrop="onDrop(event, '${col}')" ondragenter="onDragEnter(event)" ondragleave="onDragLeave(event)">
                ${colTasks.map(t => taskCardHTML(t)).join('')}
            </div>
        `;
        board.appendChild(colEl);
    });
}

function taskCardHTML(t) {
    const prioClass = (t.priority || 'Medium').toLowerCase();
    const blockers = (t.blockers || []).map(b => `<span class="blocker-badge">🚫 ${escHtml(b)}</span>`).join('');
    const tags = (t.tags || []).map(tg => `<span class="tag">${escHtml(tg)}</span>`).join('');
    const isOverdue = t.due_date && new Date(t.due_date) < new Date() && t.status !== 'Done';
    const dueStr = t.due_date ? `<span class="due ${isOverdue ? 'overdue' : ''}">📅 ${t.due_date}${isOverdue ? ' (OVERDUE)' : ''}</span>` : '';

    return `
    <div class="task-card" draggable="true" ondragstart="onDragStart(event, '${t.id}')" ondragend="onDragEnd(event)" data-id="${t.id}">
        <div class="card-top">
            <span class="task-id">${escHtml(t.id)}</span>
            <span class="priority ${prioClass}">${escHtml(t.priority || 'Medium')}</span>
        </div>
        <div class="title">${escHtml(t.title)}</div>
        ${t.description ? `<div class="desc">${escHtml(t.description)}</div>` : ''}
        <div class="meta-row">${blockers}${tags}</div>
        <div class="meta-row">
            ${t.assignee ? `<span class="assignee">👤 ${escHtml(t.assignee)}</span>` : ''}
            ${dueStr}
        </div>
        <div class="card-actions">
            <button onclick="editTask('${t.id}')">✏️ Edit</button>
            <button class="del" onclick="deleteTask('${t.id}')">🗑️ Delete</button>
        </div>
    </div>`;
}

function escHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Drag & Drop
function onDragStart(e, id) {
    draggedId = id;
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}
function onDragEnd(e) {
    e.target.classList.remove('dragging');
    document.querySelectorAll('.column').forEach(c => c.classList.remove('drag-over'));
}
function onDragOver(e) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }
function onDragEnter(e) { e.preventDefault(); e.target.closest('.column')?.classList.add('drag-over'); }
function onDragLeave(e) {
    const col = e.target.closest('.column');
    if (col && !col.contains(e.relatedTarget)) col.classList.remove('drag-over');
}
async function onDrop(e, newStatus) {
    e.preventDefault();
    document.querySelectorAll('.column').forEach(c => c.classList.remove('drag-over'));
    if (!draggedId) return;
    try {
        await fetch(`/api/tasks/${draggedId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status: newStatus})
        });
        const task = tasks.find(t => t.id === draggedId);
        if (task) task.status = newStatus;
        renderBoard();
        showToast(`Moved to ${newStatus}`);
    } catch(err) { console.error(err); }
    draggedId = null;
}

// CRUD
function openNewTask() {
    document.getElementById('modalTitle').textContent = 'New Task';
    document.getElementById('editTaskId').value = '';
    document.getElementById('taskTitleInput').value = '';
    document.getElementById('taskDescInput').value = '';
    document.getElementById('taskStatusInput').value = 'Backlog';
    document.getElementById('taskPriorityInput').value = 'Medium';
    document.getElementById('taskAssigneeInput').value = '';
    document.getElementById('taskDueInput').value = '';
    document.getElementById('taskBlockersInput').value = '';
    document.getElementById('taskTagsInput').value = '';
    document.getElementById('taskModal').classList.add('active');
    setTimeout(() => document.getElementById('taskTitleInput').focus(), 100);
}

function editTask(id) {
    const t = tasks.find(tk => tk.id === id);
    if (!t) return;
    document.getElementById('modalTitle').textContent = 'Edit Task';
    document.getElementById('editTaskId').value = t.id;
    document.getElementById('taskTitleInput').value = t.title || '';
    document.getElementById('taskDescInput').value = t.description || '';
    document.getElementById('taskStatusInput').value = t.status || 'Backlog';
    document.getElementById('taskPriorityInput').value = t.priority || 'Medium';
    document.getElementById('taskAssigneeInput').value = t.assignee || '';
    document.getElementById('taskDueInput').value = t.due_date || '';
    document.getElementById('taskBlockersInput').value = (t.blockers || []).join(', ');
    document.getElementById('taskTagsInput').value = (t.tags || []).join(', ');
    document.getElementById('taskModal').classList.add('active');
    setTimeout(() => document.getElementById('taskTitleInput').focus(), 100);
}

function closeModal() {
    document.getElementById('taskModal').classList.remove('active');
}

async function saveTask() {
    const title = document.getElementById('taskTitleInput').value.trim();
    if (!title) { alert('Title is required'); return; }

    const payload = {
        title: title,
        description: document.getElementById('taskDescInput').value.trim(),
        status: document.getElementById('taskStatusInput').value,
        priority: document.getElementById('taskPriorityInput').value,
        assignee: document.getElementById('taskAssigneeInput').value.trim(),
        due_date: document.getElementById('taskDueInput').value || null,
        blockers: document.getElementById('taskBlockersInput').value.split(',').map(s=>s.trim()).filter(Boolean),
        tags: document.getElementById('taskTagsInput').value.split(',').map(s=>s.trim()).filter(Boolean)
    };

    const editId = document.getElementById('editTaskId').value;
    try {
        if (editId) {
            await fetch(`/api/tasks/${editId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            showToast('Task updated');
        } else {
            await fetch('/api/tasks', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            showToast('Task created');
        }
        closeModal();
        await loadBoard();
    } catch(err) { console.error(err); alert('Save failed'); }
}

async function deleteTask(id) {
    if (!confirm(`Delete task ${id}?`)) return;
    try {
        await fetch(`/api/tasks/${id}`, { method: 'DELETE' });
        tasks = tasks.filter(t => t.id !== id);
        renderBoard();
        showToast('Task deleted');
    } catch(err) { console.error(err); }
}

// Toast
function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2000);
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
    if (e.key === 'n' || e.key === 'N') { e.preventDefault(); openNewTask(); }
    if (e.key === 'r' || e.key === 'R') { e.preventDefault(); loadBoard(); }
    if (e.key === 'Escape') closeModal();
});

// Init
loadBoard();
</script>
</body>
</html>'''


def load_tasks():
    """Load tasks from JSON file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            return data.get('tasks', []) if isinstance(data, dict) else data
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_tasks(tasks):
    """Save tasks to JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump({'tasks': tasks}, f, indent=2)


def next_task_id(tasks):
    """Generate next TASK-N id."""
    max_n = 0
    for t in tasks:
        tid = t.get('id', '')
        if tid.startswith('TASK-'):
            try:
                n = int(tid.split('-')[1])
                max_n = max(max_n, n)
            except (ValueError, IndexError):
                pass
    return f"TASK-{max_n + 1}"


@app.route('/')
def index():
    return render_template_string(TEMPLATE)


@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    tasks = load_tasks()
    return jsonify({'tasks': tasks})


@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json(force=True)
    tasks = load_tasks()
    task = {
        'id': next_task_id(tasks),
        'title': data.get('title', 'Untitled'),
        'description': data.get('description', ''),
        'status': data.get('status', 'Backlog'),
        'priority': data.get('priority', 'Medium'),
        'assignee': data.get('assignee', ''),
        'due_date': data.get('due_date', None),
        'blockers': data.get('blockers', []),
        'tags': data.get('tags', []),
        'created': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    tasks.append(task)
    save_tasks(tasks)
    return jsonify(task), 201


@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json(force=True)
    tasks = load_tasks()
    for t in tasks:
        if t['id'] == task_id:
            for key in ['title', 'description', 'status', 'priority', 'assignee', 'due_date', 'blockers', 'tags']:
                if key in data:
                    t[key] = data[key]
            save_tasks(tasks)
            return jsonify(t)
    return jsonify({'error': 'Task not found'}), 404


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    tasks = load_tasks()
    original_len = len(tasks)
    tasks = [t for t in tasks if t['id'] != task_id]
    if len(tasks) == original_len:
        return jsonify({'error': 'Task not found'}), 404
    save_tasks(tasks)
    return jsonify({'deleted': task_id})


if __name__ == '__main__':
    print("\n📋 Kanban Task Board starting at http://localhost:5001\n")
    app.run(debug=False, host='0.0.0.0', port=5001)
