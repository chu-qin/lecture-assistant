import Store from '../store.js';
import { get, del, sseUploadWithProgress } from '../api.js';
import { showToast } from '../components/toast.js';

// Per-workflow state
const workflows = {
  asr:    { files: [], accept: '.m4a,.mp3,.wav,.flac,.ogg', label: '语音转写', icon: '🎙️' },
  parser: { files: [], accept: '.pdf,.ppt,.pptx',          label: '课件解析', icon: '📄' },
  epub:   { files: [], accept: '.epub',                    label: '电子书导入', icon: '📖' },
};

export function renderMaterialsPage() {
  const course = Store.get('currentCourse');
  if (!course) {
    document.getElementById('main-content').innerHTML =
      '<div class="empty-state"><p>请先在首页选择课程</p></div>';
    return;
  }

  const main = document.getElementById('main-content');
  main.innerHTML = `
    <div class="materials-layout">
      <div class="materials-sidebar" id="materialsSidebar"></div>
      <div class="materials-main" id="materialsMain"></div>
    </div>
  `;

  renderWorkflows(document.getElementById('materialsMain'));
  loadSidebar();
}

function renderWorkflows(container) {
  // Reset state
  Object.values(workflows).forEach(w => w.files = []);

  container.innerHTML = Object.entries(workflows).map(([key, w]) => `
    <div class="workflow-card" data-workflow="${key}">
      <div class="workflow-header">
        <span class="workflow-icon">${w.icon}</span>
        <span class="workflow-label">${w.label}</span>
        <span class="workflow-hint">支持 ${w.accept}</span>
        <button class="workflow-toggle">−</button>
      </div>
      <div class="workflow-body">
        <div class="drop-zone" id="${key}DropZone"></div>
        <div class="file-list" id="${key}FileList"></div>
        <button class="btn btn-primary" id="${key}StartBtn" disabled>开始${w.label.substring(0, 2)}</button>
        <div class="workflow-progress" id="${key}Progress"></div>
      </div>
    </div>
  `).join('');

  // Wire up each workflow
  Object.keys(workflows).forEach(key => {
    const w = workflows[key];
    const card = container.querySelector(`[data-workflow="${key}"]`);

    // Collapse toggle
    card.querySelector('.workflow-toggle').onclick = () => {
      const body = card.querySelector('.workflow-body');
      const btn = card.querySelector('.workflow-toggle');
      const collapsed = body.style.display === 'none';
      body.style.display = collapsed ? '' : 'none';
      btn.textContent = collapsed ? '−' : '+';
    };

    // Drop zone
    buildDropZone(key + 'DropZone', w.accept, files => {
      w.files = [...w.files, ...files];
      renderFileList(key + 'FileList', w.files, () => {
        document.getElementById(key + 'StartBtn').disabled = w.files.length === 0;
      });
      document.getElementById(key + 'StartBtn').disabled = w.files.length === 0;
    });

    // Start button
    document.getElementById(key + 'StartBtn').onclick = () => {
      switch (key) {
        case 'asr':    startAsr(); break;
        case 'parser': startParse(); break;
        case 'epub':   startEpub(); break;
      }
    };
  });
}

// ============================================================
// ASR
// ============================================================
async function startAsr() {
  await runWorkflow('asr', 'transcribe', (evt, progressEl) => {
    if (evt.type === 'result') {
      const card = document.createElement('div');
      card.className = 'result-card';
      card.innerHTML = `
        <div class="result-card-header">
          <span>${escapeHtml(evt.file)}</span>
          <span class="result-stats">${evt.segments} 段 | ${formatDuration(evt.duration_sec)}</span>
        </div>
        <div class="result-card-body">${escapeHtml(evt.text)}</div>
      `;
      progressEl.appendChild(card);
    } else if (evt.type === 'summary') {
      const card = document.createElement('div');
      card.className = 'result-card';
      card.innerHTML = `
        <div class="result-card-header">AI 摘要</div>
        <div class="result-card-body">${escapeHtml(evt.text)}</div>
      `;
      progressEl.appendChild(card);
    } else if (evt.type === 'correction') {
      renderCorrection(evt, progressEl);
    }
  });
}

function renderCorrection(evt, progressEl) {
  const course = Store.get('currentCourse');
  const panel = document.createElement('div');
  panel.className = 'correction-panel';
  panel.innerHTML = `
    <div><h4>原始转录</h4><div class="panel-content">${escapeHtml(evt.original)}</div></div>
    <div><h4>AI 修正</h4><div class="panel-content">${escapeHtml(evt.corrected)}</div></div>
  `;
  progressEl.appendChild(panel);

  const actions = document.createElement('div');
  actions.style.cssText = 'display:flex;gap:8px;margin-top:8px;';
  actions.innerHTML = `
    <button class="btn btn-primary confirm-correction">确认修正</button>
    <button class="btn discard-correction">放弃修正</button>
  `;
  progressEl.appendChild(actions);

  actions.querySelector('.confirm-correction').onclick = async () => {
    await fetch(`/api/courses/${encodeURIComponent(course)}/transcripts/confirm-correction`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'confirm', stem: evt.stem }),
    });
    showToast('修正已确认', 'success');
    actions.remove();
    loadSidebar();
  };
  actions.querySelector('.discard-correction').onclick = async () => {
    await fetch(`/api/courses/${encodeURIComponent(course)}/transcripts/confirm-correction`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'discard', stem: evt.stem }),
    });
    showToast('修正已放弃', 'info');
    actions.remove();
    loadSidebar();
  };
}

// ============================================================
// Parser
// ============================================================
async function startParse() {
  const course = Store.get('currentCourse');
  const progressEl = document.getElementById('parserProgress');
  const formData = new FormData();
  workflows.parser.files.forEach(f => formData.append('files', f));
  formData.append('options', JSON.stringify({ enable_formula: true, enable_table: true }));

  await runWorkflow('parser', 'parse', (evt, progressEl) => {
    if (evt.type === 'result') {
      const card = document.createElement('div');
      card.className = 'result-card';
      card.innerHTML = `
        <div class="result-card-header">
          <span>${escapeHtml(evt.file)}</span>
          <span class="result-stats">公式: ${evt.formulas || 0} | 表格: ${evt.tables || 0} | 图片: ${evt.images || 0}</span>
        </div>
        <div class="result-card-body">${escapeHtml((evt.markdown || '').substring(0, 2000))}</div>
      `;
      progressEl.appendChild(card);
    }
  }, formData);
}

// ============================================================
// EPUB
// ============================================================
async function startEpub() {
  await runWorkflow('epub', 'import-epub', (evt, progressEl) => {
    if (evt.type === 'result') {
      const meta = evt.metadata || {};
      const card = document.createElement('div');
      card.className = 'result-card';
      card.innerHTML = `
        <div class="result-card-header">
          <span>${escapeHtml(evt.file)}</span>
          <span class="result-stats">${meta.title || ''} ${meta.author ? '— ' + meta.author : ''} ${meta.chapters ? meta.chapters + ' 章' : ''}</span>
        </div>
        <div class="result-card-body">${escapeHtml((evt.markdown || '').substring(0, 2000))}</div>
      `;
      progressEl.appendChild(card);
    }
  });
}

// ============================================================
// Shared workflow runner
// ============================================================
async function runWorkflow(key, endpoint, onEvent, extraFormData) {
  const course = Store.get('currentCourse');
  const w = workflows[key];
  const btn = document.getElementById(key + 'StartBtn');
  const progressEl = document.getElementById(key + 'Progress');

  btn.disabled = true;
  btn.classList.add('btn-loading');
  progressEl.innerHTML = '<div class="progress-status">正在上传文件...</div>';

  // Build form data: use provided form or create one with just files
  const fd = extraFormData || new FormData();
  if (!extraFormData) {
    w.files.forEach(f => fd.append('files', f));
  }

  try {
    await sseUploadWithProgress(
      `/courses/${encodeURIComponent(course)}/${endpoint}`,
      fd,
      (evt) => {
        if (evt.type === 'status') {
          progressEl.innerHTML = `<div class="progress-status">${escapeHtml(evt.message)}</div>`;
        } else if (evt.type === 'done') {
          showToast('操作完成', 'success');
          loadSidebar();
        } else if (evt.type === 'error') {
          showToast(`操作失败: ${evt.message}`, 'error');
        } else {
          onEvent(evt, progressEl);
        }
      },
      (pct) => {
        progressEl.innerHTML = `<div class="progress-status">正在上传... ${pct}%</div>`;
      }
    );
  } catch (e) {
    showToast(`请求失败: ${e.message}`, 'error');
  }

  btn.disabled = false;
  btn.classList.remove('btn-loading');
  w.files = [];
  document.getElementById(key + 'FileList').innerHTML = '';
}

// ============================================================
// Sidebar — existing files
// ============================================================
async function loadSidebar() {
  const course = Store.get('currentCourse');
  if (!course) return;
  const sidebar = document.getElementById('materialsSidebar');
  if (!sidebar) return;

  sidebar.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:12px;">加载中...</div>';

  try {
    const [txData, docData] = await Promise.all([
      get(`/courses/${encodeURIComponent(course)}/transcripts`),
      get(`/courses/${encodeURIComponent(course)}/documents`),
    ]);

    sidebar.innerHTML = '';

    const sections = [
      { title: '转录文件', type: 'transcripts', icon: '🎙️', items: txData.transcripts || [] },
      { title: '解析文档', type: 'documents', icon: '📄', items: docData.documents || [] },
    ];

    sections.forEach(sec => {
      const section = document.createElement('div');
      section.className = 'sidebar-section';

      const header = document.createElement('div');
      header.className = 'sidebar-section-header';
      header.innerHTML = `<span>${sec.icon}</span> <span>${sec.title}</span> <span class="sidebar-count">${sec.items.length}</span>`;
      section.appendChild(header);

      if (sec.items.length > 0) {
        sec.items.forEach(item => {
          const row = document.createElement('div');
          row.className = 'sidebar-file';
          row.innerHTML = `
            <span class="sidebar-file-name">${escapeHtml(item.name)}</span>
            <span class="sidebar-file-actions">
              <button class="act-btn" title="下载">↓</button>
              <button class="act-btn danger" title="删除">×</button>
            </span>
          `;
          row.querySelector('.act-btn').onclick = (e) => {
            e.stopPropagation();
            downloadFile(course, sec.type, item.name);
          };
          row.querySelector('.act-btn.danger').onclick = (e) => {
            e.stopPropagation();
            deleteFile(course, sec.type, item.name);
          };
          section.appendChild(row);
        });
      } else {
        const empty = document.createElement('div');
        empty.className = 'sidebar-empty';
        empty.textContent = '暂无';
        section.appendChild(empty);
      }

      sidebar.appendChild(section);
    });
  } catch (e) {
    sidebar.innerHTML = `<div style="color:var(--danger);font-size:12px;padding:12px;">加载失败: ${e.message}</div>`;
  }
}

async function downloadFile(course, type, name) {
  window.open(`/api/courses/${encodeURIComponent(course)}/${type}/${encodeURIComponent(name)}/download`, '_blank');
}

async function deleteFile(course, type, name) {
  if (!confirm(`确定要删除 "${name}" 吗？`)) return;
  try {
    await del(`/courses/${encodeURIComponent(course)}/${type}/${encodeURIComponent(name)}`);
    showToast(`"${name}" 已删除`, 'success');
    loadSidebar();
  } catch (e) {
    showToast(`删除失败: ${e.message}`, 'error');
  }
}

// ============================================================
// Drop zone utility
// ============================================================
function buildDropZone(id, accept, onFiles) {
  const zone = document.getElementById(id);
  if (!zone) return;
  zone.className = 'drop-zone';
  zone.innerHTML = `<p>拖拽文件到此处或点击上传</p><p class="hint">支持 ${accept}</p>`;

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    onFiles(Array.from(e.dataTransfer.files));
  });
  zone.addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.multiple = true;
    input.onchange = () => onFiles(Array.from(input.files));
    input.click();
  });
}

function renderFileList(id, files, onChange) {
  const container = document.getElementById(id);
  if (!container) return;
  container.innerHTML = files.map((f, i) => `
    <div class="file-item">
      <span class="file-name">${escapeHtml(f.name)}</span>
      <span class="file-size">${formatSize(f.size)}</span>
      <button class="file-remove" data-idx="${i}">×</button>
    </div>
  `).join('');

  container.querySelectorAll('.file-remove').forEach(btn => {
    btn.onclick = () => {
      files.splice(parseInt(btn.dataset.idx), 1);
      renderFileList(id, files, onChange);
      if (onChange) onChange();
    };
  });
}

// ============================================================
// Utils
// ============================================================
function escapeHtml(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function formatSize(bytes) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDuration(sec) {
  if (!sec) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
