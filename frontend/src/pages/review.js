import Store from '../store.js';
import { get, post, del, sseStream } from '../api.js';
import { renderMarkdown, renderMathAndMermaid, renderInline } from '../utils/markdown.js';
import { showToast } from '../components/toast.js';
import { escapeHtml } from '../utils/dom.js';


let currentTab = '';
let tabMaterials = {};
let scrollPositions = {};
let chatHistory = [];
let materialList = [];
let kbReady = false;
let isGenerating = false;

const TYPE_MAP = {
  '复习提纲': { key: 'outline', short: '提纲', icon: '📋' },
  '详细笔记': { key: 'notes', short: '笔记', icon: '📝' },
  '知识结构图': { key: 'graph', short: '结构图', icon: '🔗' },
  '自测题库': { key: 'quiz', short: '题库', icon: '❓' },
};

function getTabKey(material) {
  for (const typeName in TYPE_MAP) {
    if (material.material_type.indexOf(typeName) !== -1 || material.display_name.indexOf(typeName) !== -1) {
      return TYPE_MAP[typeName].key;
    }
  }
  return material.material_type.substring(0, 8);
}

function getTypeNameFromKey(key) {
  for (const typeName in TYPE_MAP) {
    if (TYPE_MAP[typeName].key === key) return typeName;
  }
  return key;
}

export async function renderReviewPage() {
  const course = Store.get('currentCourse');
  if (!course) {
    document.getElementById('main-content').innerHTML =
      '<div class="empty-state"><p>请先在首页选择课程</p></div>';
    return;
  }

  const main = document.getElementById('main-content');
  main.innerHTML = `
    <div class="review-layout">
      <nav class="review-sidebar" id="reviewSidebar"></nav>
      <section class="review-content" id="reviewContent">
        <div class="review-body content-body" id="reviewBody">
          <div class="empty-state"><p>加载中...</p></div>
        </div>
      </section>
      <aside class="review-chat" id="reviewChat">
        <div class="chat-header" id="chatHeader">
          <span class="kb-badge off">知识库未构建</span>
          <span style="margin-left:auto;display:flex;gap:4px;">
            <button class="nav-btn" id="clearChatBtn" title="清空对话" style="font-size:11px;">清空</button>
            <button class="nav-btn" id="exportChatBtn" title="导出对话" style="font-size:11px;">导出</button>
          </span>
        </div>
        <div class="chat-messages" id="chatMessages">
          <div class="empty-state" style="padding:30px 10px;">
            <p>在此输入问题，AI 基于课件和录音回答</p>
          </div>
        </div>
        <div class="chat-status" id="chatStatus"></div>
        <div class="chat-input-area">
          <textarea class="chat-textarea" id="chatInput" placeholder="输入问题..." rows="1"></textarea>
          <button class="btn-send" id="sendBtn" title="发送">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="19" x2="12" y2="5"></line>
              <polyline points="5 12 12 5 19 12"></polyline>
            </svg>
          </button>
        </div>
      </aside>
    </div>
    ${buildGenerateModal()}
  `;

  // Chat input setup
  const chatInput = document.getElementById('chatInput');
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  });
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  document.getElementById('sendBtn').onclick = sendMessage;

  // Chat actions
  document.getElementById('clearChatBtn').onclick = clearChat;
  document.getElementById('exportChatBtn').onclick = exportChat;

  // Modal
  document.getElementById('genCancelBtn').onclick = closeGenerateModal;
  document.getElementById('genStartBtn').onclick = startGenerate;

  await loadReviewData();
}

function buildGenerateModal() {
  return `
    <div class="modal-overlay" id="genModal">
      <div class="modal">
        <h3>生成复习资料</h3>
        <p style="font-size:13px;color:var(--text-secondary);">
          源材料：<span id="genSourceInfo">加载中...</span>
        </p>
        <label>资料类型</label>
        <div class="check-group" id="genTypes"></div>
        <label>附加要求（可选）</label>
        <textarea id="genExtra" placeholder="例如：重点讲解第三章、与公式对比分析"></textarea>
        <div id="genProgress" style="margin-top:8px;font-size:13px;color:var(--text-secondary);"></div>
        <div class="modal-buttons">
          <button class="btn" id="genCancelBtn">取消</button>
          <button class="btn btn-primary" id="genStartBtn">开始生成</button>
        </div>
      </div>
    </div>
  `;
}

// ============================================================
// Load
// ============================================================
async function loadReviewData() {
  const course = Store.get('currentCourse');

  try {
    const [matData, kbData] = await Promise.all([
      get(`/courses/${encodeURIComponent(course)}/materials`),
      get(`/courses/${encodeURIComponent(course)}/kb-status`).catch(() => ({ ready: false })),
    ]);

    materialList = matData.materials || [];
    kbReady = kbData.ready || false;

    restoreChatHistory(course);
    renderChatHistory();
    updateKBIndicator();
    renderSidebar();

    if (materialList.length > 0) {
      // Find first material by type order
      const order = ['outline', 'notes', 'graph', 'quiz'];
      let firstKey = null;
      for (const key of order) {
        if (materialList.some(m => getTabKey(m) === key)) {
          firstKey = key;
          break;
        }
      }
      if (!firstKey) firstKey = getTabKey(materialList[0]);
      switchMaterialTab(firstKey);
    } else {
      document.getElementById('reviewBody').innerHTML = `
        <div class="generate-prompt">
          <p style="font-size:16px;margin-bottom:4px;">暂无已生成的复习资料</p>
          <p style="color:var(--text-secondary);margin-bottom:16px;">上传录音或课件后，即可一键生成复习资料</p>
          <button class="btn btn-primary" id="genFirstBtn" style="height:36px;padding:0 20px;">生成第一份复习资料</button>
        </div>`;
      document.getElementById('genFirstBtn').onclick = openGenerateModal;
    }
  } catch (e) {
    document.getElementById('reviewBody').innerHTML =
      `<div class="empty-state"><p>加载失败: ${escapeHtml(e.message)}</p></div>`;
    showToast(`加载失败: ${e.message}`, 'error');
  }
}

// ============================================================
// Sidebar
// ============================================================
function renderSidebar() {
  const sidebar = document.getElementById('reviewSidebar');
  if (!sidebar) return;

  sidebar.innerHTML = '';

  // Generate button
  const genBtn = document.createElement('button');
  genBtn.className = 'btn btn-primary sidebar-gen-btn';
  genBtn.textContent = '生成新资料';
  genBtn.onclick = openGenerateModal;
  sidebar.appendChild(genBtn);

  // KB actions
  const kbSection = document.createElement('div');
  kbSection.className = 'sidebar-kb';
  if (!kbReady) {
    kbSection.innerHTML = '<span class="kb-badge off" style="margin-bottom:8px;">知识库未构建</span>';
    const buildBtn = document.createElement('button');
    buildBtn.className = 'btn sidebar-action-btn';
    buildBtn.textContent = '构建知识库';
    buildBtn.onclick = buildKB;
    kbSection.appendChild(buildBtn);
  } else {
    kbSection.innerHTML = '<span class="kb-badge ready" style="margin-bottom:8px;">知识库就绪</span>';
    const rebuildBtn = document.createElement('button');
    rebuildBtn.className = 'btn sidebar-action-btn';
    rebuildBtn.textContent = '重建知识库';
    rebuildBtn.onclick = buildKB;
    kbSection.appendChild(rebuildBtn);
  }
  sidebar.appendChild(kbSection);

  // Material groups
  const order = ['outline', 'notes', 'graph', 'quiz'];
  order.forEach(key => {
    const typeName = getTypeNameFromKey(key);
    const info = TYPE_MAP[typeName] || { icon: '📄', short: key };
    const items = materialList.filter(m => getTabKey(m) === key);

    const group = document.createElement('div');
    group.className = 'sidebar-material-group';

    const header = document.createElement('div');
    header.className = 'sidebar-material-group-header';
    header.innerHTML = `<span>${info.icon}</span> <span>${info.short}</span> <span class="sidebar-count">${items.length}</span>`;
    group.appendChild(header);

    if (items.length > 0) {
      items.forEach(item => {
        const row = document.createElement('div');
        row.className = 'sidebar-material-item' + (currentTab === key ? ' active' : '');
        row.innerHTML = `
          <span class="sidebar-material-name">${escapeHtml(item.display_name)}</span>
          <span class="sidebar-material-actions">
            <button class="act-btn" title="下载">↓</button>
            <button class="act-btn danger" title="删除">×</button>
          </span>
        `;
        row.onclick = () => switchMaterialTab(key);
        row.querySelector('.act-btn').onclick = (e) => {
          e.stopPropagation();
          downloadMaterial(item);
        };
        row.querySelector('.act-btn.danger').onclick = (e) => {
          e.stopPropagation();
          deleteMaterial(item);
        };
        group.appendChild(row);
      });
    } else {
      const empty = document.createElement('div');
      empty.className = 'sidebar-material-empty';
      empty.textContent = '暂无';
      group.appendChild(empty);
    }

    sidebar.appendChild(group);
  });
}

async function downloadMaterial(item) {
  window.open(`/api/courses/${encodeURIComponent(Store.get('currentCourse'))}/materials/${encodeURIComponent(item.display_name)}/download`, '_blank');
}

async function deleteMaterial(item) {
  const course = Store.get('currentCourse');
  if (!confirm(`确定要删除 "${item.display_name}" 吗？`)) return;
  try {
    await del(`/courses/${encodeURIComponent(course)}/materials/${encodeURIComponent(item.display_name)}`);
    showToast(`"${item.display_name}" 已删除`, 'success');
    await loadReviewData();
  } catch (e) {
    showToast(`删除失败: ${e.message}`, 'error');
  }
}

// ============================================================
// Material Tabs
// ============================================================
function switchMaterialTab(key) {
  if (currentTab) {
    const contentArea = document.getElementById('reviewContent');
    if (contentArea) scrollPositions[currentTab] = contentArea.scrollTop;
  }
  currentTab = key;
  renderSidebar();
  renderCurrentMaterial();

  requestAnimationFrame(() => {
    const contentArea = document.getElementById('reviewContent');
    if (contentArea && scrollPositions[key] !== undefined) {
      contentArea.scrollTop = scrollPositions[key];
    }
  });
}

function findCurrentMaterial() {
  return materialList.find(m => getTabKey(m) === currentTab) || null;
}

function renderCurrentMaterial() {
  const body = document.getElementById('reviewBody');
  const mat = findCurrentMaterial();

  if (!mat) {
    body.innerHTML = '<div class="empty-state"><p>暂无该类型资料</p></div>';
    return;
  }

  if (tabMaterials[currentTab] && tabMaterials[currentTab].content) {
    const course = Store.get('currentCourse');
    renderMarkdown(tabMaterials[currentTab].content, body, course, mat.display_name);
    return;
  }

  body.innerHTML = '<div class="empty-state"><p>加载中...</p></div>';
  loadMaterialContent(mat);
}

async function loadMaterialContent(mat) {
  try {
    if (mat.content) {
      tabMaterials[currentTab] = mat;
      const body = document.getElementById('reviewBody');
      renderMarkdown(mat.content, body, Store.get('currentCourse'), mat.display_name);
    }
  } catch (e) {
    document.getElementById('reviewBody').innerHTML =
      `<div class="empty-state"><p>加载失败: ${escapeHtml(e.message)}</p></div>`;
  }
}

// ============================================================
// Generate Modal
// ============================================================
async function openGenerateModal() {
  const course = Store.get('currentCourse');

  try {
    const data = await get(`/courses/${encodeURIComponent(course)}/sources`);
    document.getElementById('genSourceInfo').textContent =
      `转录 ${data.transcripts ? data.transcripts.length : 0} 份, 课件 ${data.docs ? data.docs.length : 0} 份`;
  } catch (e) {
    document.getElementById('genSourceInfo').textContent = '加载失败';
  }

  const types = [
    '复习提纲（核心概念 + 重点/难点标注 + 公式定理）',
    '详细笔记（逐章知识点详细梳理）',
    '知识结构图（章节层级结构 + 知识关联）',
    '自测题库（单选题 + 简答题 + 答案）',
  ];
  document.getElementById('genTypes').innerHTML = types.map((t, i) =>
    `<label><input type="checkbox" value="${escapeHtml(t)}"${i === 0 ? ' checked' : ''}> ${escapeHtml(t)}</label>`
  ).join('');

  document.getElementById('genExtra').value = '';
  document.getElementById('genProgress').textContent = '';
  document.getElementById('genStartBtn').disabled = false;
  document.getElementById('genModal').classList.add('open');
}

function closeGenerateModal() {
  document.getElementById('genModal').classList.remove('open');
}

async function startGenerate() {
  const course = Store.get('currentCourse');
  const checks = document.querySelectorAll('#genTypes input:checked');
  const materialTypes = Array.from(checks).map(c => c.value);
  if (materialTypes.length === 0) {
    showToast('请选择至少一种资料类型', 'warning');
    return;
  }

  const customExtra = document.getElementById('genExtra').value;

  isGenerating = true;
  document.getElementById('genProgress').textContent = '正在生成...';
  document.getElementById('genStartBtn').disabled = true;
  closeGenerateModal();

  const body = document.getElementById('reviewBody');
  body.innerHTML = '<div class="empty-state"><p>正在生成复习资料...</p></div>';

  for (const typeName in TYPE_MAP) {
    if (materialTypes[0].indexOf(typeName) !== -1) {
      currentTab = TYPE_MAP[typeName].key;
      break;
    }
  }

  try {
    let streamContent = '';
    let lastKatexTime = 0;

    for await (const evt of sseStream(
      `/courses/${encodeURIComponent(course)}/generate`,
      { material_types: materialTypes, custom_extra: customExtra }
    )) {
      if (evt.type === 'chunk') {
        streamContent += evt.content;
        body.innerHTML = `<div class="content-body">${renderInline(streamContent)}</div>`;
        const now = Date.now();
        if (now - lastKatexTime > 300) {
          renderMathAndMermaid(body);
          lastKatexTime = now;
        }
        const contentArea = document.getElementById('reviewContent');
        if (contentArea) contentArea.scrollTop = contentArea.scrollHeight;
      } else if (evt.type === 'status') {
        const prog = document.getElementById('genProgress');
        if (prog) prog.textContent = evt.message;
      } else if (evt.type === 'done') {
        streamContent = '';
        await loadReviewData();
      } else if (evt.type === 'error') {
        body.innerHTML += `<div style="color:#e5484d;margin-top:8px;">错误: ${escapeHtml(evt.message)}</div>`;
        showToast(`生成失败: ${evt.message}`, 'error');
      }
    }

    if (streamContent) {
      body.innerHTML = `<div class="content-body">${renderInline(streamContent)}</div>`;
    }
    renderMathAndMermaid(body);
  } catch (e) {
    body.innerHTML = `<div style="color:#e5484d;">生成失败: ${escapeHtml(e.message)}</div>`;
    showToast(`生成失败: ${e.message}`, 'error');
  }

  isGenerating = false;
  document.getElementById('genProgress').textContent = '';
}

// ============================================================
// KB
// ============================================================
async function buildKB() {
  const course = Store.get('currentCourse');
  const chatHeader = document.getElementById('chatHeader');
  const statusEl = document.getElementById('chatStatus');

  chatHeader.innerHTML = '<span class="kb-badge building">知识库构建中...</span>';
  statusEl.innerHTML = '<div class="kb-progress"><div class="progress-bar small"><div class="progress-fill" style="width:0%"></div></div><span id="kbMsg">准备中...</span></div>';

  try {
    for await (const evt of sseStream(`/courses/${encodeURIComponent(course)}/build-kb`, {}, 'POST')) {
      if (evt.type === 'status') {
        const msgEl = document.getElementById('kbMsg');
        if (msgEl) msgEl.textContent = evt.message;
        const fillEl = statusEl.querySelector('.progress-fill');
        if (fillEl && evt.progress) fillEl.style.width = evt.progress + '%';
      } else if (evt.type === 'done') {
        kbReady = true;
        updateKBIndicator();
        renderSidebar();
        showToast(`知识库构建完成，${evt.doc_count || 0} 个文本块已索引`, 'success');
        statusEl.textContent = '';
      } else if (evt.type === 'error') {
        updateKBIndicator();
        showToast(`知识库构建失败: ${evt.message}`, 'error');
        statusEl.textContent = '';
      }
    }
  } catch (e) {
    updateKBIndicator();
    showToast(`知识库构建失败: ${e.message}`, 'error');
    statusEl.textContent = '';
  }
}

function updateKBIndicator() {
  const hdr = document.getElementById('chatHeader');
  if (!hdr) return;
  if (kbReady) {
    hdr.innerHTML = '<span class="kb-badge ready">知识库就绪</span>';
  } else {
    hdr.innerHTML = '<span class="kb-badge off">知识库未构建</span>';
  }
}

// ============================================================
// Chat
// ============================================================
async function sendMessage() {
  const course = Store.get('currentCourse');
  if (!kbReady) {
    showToast('请先构建知识库', 'warning');
    return;
  }

  const input = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  input.style.height = 'auto';
  input.disabled = true;
  document.getElementById('sendBtn').disabled = true;

  appendChatMessage('user', message);
  chatHistory.push({ role: 'user', content: message });
  saveChatHistory(course);

  const aiEl = appendChatMessage('assistant', '');
  document.getElementById('chatStatus').textContent = '思考中...';

  try {
    let fullContent = '';
    let lastKatexTime = 0;

    for await (const evt of sseStream(
      `/courses/${encodeURIComponent(course)}/chat`,
      { message, history: chatHistory.slice(0, -1) }
    )) {
      if (evt.type === 'chunk') {
        fullContent += evt.content;
        aiEl.querySelector('.msg-content').innerHTML = renderInline(fullContent);
        const now = Date.now();
        if (now - lastKatexTime > 300) {
          renderMathAndMermaid(aiEl);
          lastKatexTime = now;
        }
        scrollChatBottom();
      } else if (evt.type === 'done') {
        fullContent = evt.content || fullContent;
        aiEl.querySelector('.msg-content').innerHTML = renderInline(fullContent);
        renderMathAndMermaid(aiEl);
        if (evt.sources && evt.sources.length > 0) {
          const srcDiv = document.createElement('details');
          srcDiv.className = 'chat-sources';
          srcDiv.innerHTML = '<summary>参考来源</summary>' +
            evt.sources.map(s =>
              `<div class="src-item"><strong>${escapeHtml(s.source_file)}</strong> (${escapeHtml(s.source_type)}, 相似度 ${(s.score || 0).toFixed(2)})<br>${escapeHtml((s.content || '').substring(0, 200))}</div>`
            ).join('');
          aiEl.appendChild(srcDiv);
        }
        chatHistory.push({ role: 'assistant', content: fullContent, sources: evt.sources || [] });
        saveChatHistory(course);
        document.getElementById('chatStatus').textContent = '';
      } else if (evt.type === 'error') {
        aiEl.querySelector('.msg-content').innerHTML =
          `<span style="color:#e5484d;">错误: ${escapeHtml(evt.message)}</span>`;
        document.getElementById('chatStatus').textContent = '';
        showToast(`问答失败: ${evt.message}`, 'error');
      }
    }
  } catch (e) {
    aiEl.querySelector('.msg-content').innerHTML =
      `<span style="color:#e5484d;">请求失败: ${escapeHtml(e.message)}</span>`;
    document.getElementById('chatStatus').textContent = '';
  }

  input.disabled = false;
  document.getElementById('sendBtn').disabled = false;
  input.focus();
}

function appendChatMessage(role, content) {
  const container = document.getElementById('chatMessages');
  const empty = container.querySelector('.empty-state');
  if (empty) empty.remove();

  const el = document.createElement('div');
  el.className = `msg msg-${role}`;
  const inner = role === 'assistant' && content ? renderInline(content) : escapeHtml(content);
  el.innerHTML = `<div class="msg-content">${inner}</div>`;
  container.appendChild(el);
  scrollChatBottom();
  return el;
}

function scrollChatBottom() {
  const el = document.getElementById('chatMessages');
  const threshold = 80;
  if (el.scrollHeight - el.scrollTop - el.clientHeight < threshold) {
    el.scrollTop = el.scrollHeight;
  }
}

// ============================================================
// Chat Persistence
// ============================================================
function saveChatHistory(course) {
  try {
    localStorage.setItem('la-chat-' + course, JSON.stringify(chatHistory));
  } catch (e) { /* localStorage full */ }
}

function restoreChatHistory(course) {
  try {
    const saved = localStorage.getItem('la-chat-' + course);
    chatHistory = saved ? JSON.parse(saved) : [];
  } catch (e) {
    chatHistory = [];
  }
}

function renderChatHistory() {
  const container = document.getElementById('chatMessages');
  if (!container) return;
  container.innerHTML = '';
  if (chatHistory.length === 0) {
    container.innerHTML = '<div class="empty-state" style="padding:30px 10px;"><p>在此输入问题，AI 基于课件和录音回答</p></div>';
    return;
  }
  chatHistory.forEach(m => {
    const el = document.createElement('div');
    el.className = 'msg msg-' + m.role;
    const inner = m.role === 'assistant' && m.content ? renderInline(m.content) : escapeHtml(m.content);
    el.innerHTML = '<div class="msg-content">' + inner + '</div>';
    if (m.sources && m.sources.length > 0) {
      const srcDiv = document.createElement('details');
      srcDiv.className = 'chat-sources';
      srcDiv.innerHTML = '<summary>参考来源</summary>' +
        m.sources.map(s =>
          '<div class="src-item"><strong>' + escapeHtml(s.source_file) + '</strong> (' + escapeHtml(s.source_type) + ', 相似度 ' + (s.score || 0).toFixed(2) + ')<br>' + escapeHtml((s.content || '').substring(0, 200)) + '</div>'
        ).join('');
      el.appendChild(srcDiv);
    }
    container.appendChild(el);
  });
  scrollChatBottom();
}

function clearChat() {
  const course = Store.get('currentCourse');
  chatHistory = [];
  localStorage.removeItem('la-chat-' + course);
  document.getElementById('chatMessages').innerHTML =
    '<div class="empty-state" style="padding:30px 10px;"><p>在此输入问题，AI 基于课件和录音回答</p></div>';
  showToast('对话已清空', 'info');
}

// ============================================================
// Export
// ============================================================
function exportChat() {
  if (chatHistory.length === 0) {
    showToast('暂无对话内容', 'info');
    return;
  }
  const text = chatHistory.map(m => {
    const label = m.role === 'user' ? '你' : 'AI';
    return `**${label}**: ${m.content}`;
  }).join('\n\n---\n\n');
  const blob = new Blob([text], { type: 'text/markdown' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = (Store.get('currentCourse') || 'chat') + '_对话导出.md';
  a.click();
  URL.revokeObjectURL(a.href);
}
