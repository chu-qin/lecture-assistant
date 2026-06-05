# HTML 全端迁移计划

> 将 Streamlit monolith 替换为 Vanilla JS + Vite 前端 + FastAPI 后端 SPA 架构。

---

## 目录

1. [架构概览](#1-架构概览)
2. [前端架构设计](#2-前端架构设计)
3. [后端 API 设计](#3-后端-api-设计)
4. [分步实施计划](#4-分步实施计划)
5. [可行性验证](#5-可行性验证)
6. [附录：对照检查清单](#6-附录对照检查清单)

---

## 1. 架构概览

### 1.1 改造前后对比

```
BEFORE (Streamlit monolith)              AFTER (SPA + API)
─────────────────────────────            ───────────────────────
run.py  ──→ Streamlit UI                 run.py  ──→ FastAPI only
  │                                        │
  ├─ pages/1_资料录入.py                    ├─ frontend/       (Vite SPA)
  │   ├─ ASR 转录                            │   ├─ #home       (课程管理)
  │   ├─ 课件解析                            │   ├─ #materials  (资料录入)
  │   └─ EPUB 导入                           │   └─ #review     (复习问答)
  │                                        │
  ├─ pages/2_复习与问答.py                  └─ src/api/        (FastAPI routes)
  │   ├─ 资料生成                              ├─ courses.py
  │   ├─ RAG 问答                              ├─ asr_routes.py
  │   └─ 知识库管理                            ├─ parser_routes.py
  │                                            ├─ materials.py
  └─ src/                                      ├─ generate.py
      ├─ asr/                                  └─ chat.py
      ├─ parser/
      ├─ knowledge/
      └─ ...                             src/ (unchanged)
                                           ├─ asr/
                                           ├─ parser/
                                           ├─ knowledge/
                                           └─ ...
```

### 1.2 数据流

```
浏览器 (SPA)
  │
  ├─ 页面加载
  │   GET /api/courses ──────────→ 课程列表
  │
  ├─ 文件上传 + 转录
  │   POST /api/courses/{id}/transcribe (multipart)
  │   ← SSE: progress → result
  │
  ├─ 文件上传 + 解析
  │   POST /api/courses/{id}/parse (multipart)
  │   ← SSE: progress → result
  │
  ├─ 复习资料生成
  │   POST /api/courses/{id}/generate (JSON)
  │   ← SSE: chunks → done
  │
  └─ RAG 问答
      POST /api/courses/{id}/chat (JSON)
      ← SSE: chunks → done (with sources)
```

### 1.3 端口与代理

| 环境 | 前端 | 后端 | 说明 |
|------|------|------|------|
| 开发 | Vite :5173 | FastAPI :8502 | Vite proxy `/api` → `:8502` |
| 生产 | FastAPI :8502 直接 serve | 同端口 | 静态文件从 `frontend/dist/` 提供 |
| Tauri | WebView → localhost | :8502 sidecar | Tauri 启动时拉起 Python 进程 |

---

## 2. 前端架构设计

### 2.1 项目结构

```
frontend/
├── index.html                  ← SPA 入口，含 KaTeX/Mermaid CDN
├── package.json                ← npm 依赖
├── vite.config.js              ← Vite 配置 + API 代理
│
├── public/
│   └── locales/
│       ├── zh.json             ← 从 src/i18n/zh.json 复制
│       └── en.json             ← 从 src/i18n/en.json 复制
│
└── src/
    ├── main.js                 ← 应用入口：初始化主题、i18n、路由、渲染导航
    ├── router.js               ← Hash 路由器：onHashChange → renderPage
    ├── store.js                ← 全局状态：currentCourse, theme, language, kbReady
    │
    ├── api.js                  ← HTTP 客户端 + SSE 流读取器
    │
    ├── pages/
    │   ├── home.js             ← 首页：课程卡片列表、创建/删除课程
    │   ├── materials.js        ← 资料录入：ASR 转录、课件解析、EPUB 导入
    │   └── review.js           ← 复习问答：资料查看、生成、知识库、聊天
    │
    ├── components/
    │   ├── nav.js              ← 顶栏导航（课程选择、页面标签、操作按钮）
    │   ├── theme.js            ← 主题系统（读取/设置 data-theme、切换按钮）
    │   ├── modal.js            ← 通用弹窗（打开/关闭/ESC 关闭/点击遮罩关闭）
    │   └── toast.js            ← Toast 通知（success/error/warning/info）
    │
    ├── utils/
    │   ├── markdown.js         ← Marked + KaTeX + Mermaid 渲染
    │   ├── i18n.js             ← 客户端 i18n：t(key, params)、setLanguage()
    │   └── dom.js              ← DOM 工具：$、$$、createElement、escapeHtml
    │
    └── styles/
        ├── base.css            ← CSS 变量（light/dark）、reset、排版
        ├── nav.css             ← 导航栏样式
        ├── home.css            ← 首页课程卡片
        ├── materials.css       ← 资料录入页（上传区、进度条、预览）
        ├── review.css          ← 复习页（资料查看、生成区）
        ├── chat.css            ← 聊天面板
        ├── modal.css           ← 弹窗/对话框
        └── toast.css           ← Toast 通知
```

### 2.2 npm 依赖

```json
{
  "name": "lecture-assistant-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "katex": "^0.16.11",
    "marked": "^15.0.3",
    "mermaid": "^11.0.0"
  },
  "devDependencies": {
    "vite": "^6.0.0"
  }
}
```

CDN 方案 vs npm 打包：
- **KaTeX**: npm 打包 → 需要配置字体文件路径。CDN 方式字体自动加载。→ 用 npm，配置 `katex/dist/katex.min.css` 导入，字体文件由 Vite 处理。
- **Mermaid**: npm 打包 ~2MB，按需加载。→ 用 npm。
- **Marked**: npm 打包 ~50KB。→ 用 npm。

依赖从 CDN 全部迁移到 npm 打包，离线可用，为 Tauri 打包做准备。

### 2.3 Vite 配置

```javascript
// vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: './',  // 相对路径，适配 Tauri/Capacitor
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8502',
        changeOrigin: true,
      },
    },
  },
});
```

### 2.4 SPA 路由设计

Hash 路由，三个页面 + 一个默认路由：

| Hash | 页面 | 说明 |
|------|------|------|
| `#home` | 首页 | 课程列表/创建/选择 |
| `#materials` | 资料录入 | ASR + 解析 + EPUB |
| `#review` | 复习问答 | 资料查看 + 生成 + 聊天 |
| (default) | 首页 | 无 hash 时默认 #home |

路由实现：

```javascript
// router.js
const routes = {
  home: { render: renderHomePage, title: '课程' },
  materials: { render: renderMaterialsPage, title: '资料录入' },
  review: { render: renderReviewPage, title: '复习问答' },
};

function getCurrentRoute() {
  const hash = window.location.hash.replace('#', '');
  return routes[hash] ? hash : 'home';
}

window.addEventListener('hashchange', () => {
  const route = getCurrentRoute();
  routes[route].render();
  updateNavActiveTab(route);
});

// 初次加载
window.addEventListener('DOMContentLoaded', () => {
  const route = getCurrentRoute();
  if (!window.location.hash) {
    window.location.hash = '#home'; // 触发 hashchange
  } else {
    routes[route].render();
  }
});
```

### 2.5 全局状态管理

```javascript
// store.js
const Store = {
  _state: {
    currentCourse: '',
    courses: [],
    theme: localStorage.getItem('la-theme') || 'dark',
    language: localStorage.getItem('la-language') || 'zh',
    kbReady: false,
    materialList: [],
    chatHistory: [],
  },
  _listeners: {},

  get(key) {
    return this._state[key];
  },

  set(key, value) {
    this._state[key] = value;
    (this._listeners[key] || []).forEach(fn => fn(value));
  },

  on(key, fn) {
    (this._listeners[key] = this._listeners[key] || []).push(fn);
  },

  // 批量更新，只触发一次通知
  batch(updates) {
    for (const [key, value] of Object.entries(updates)) {
      this._state[key] = value;
    }
    for (const key of Object.keys(updates)) {
      (this._listeners[key] || []).forEach(fn => fn(this._state[key]));
    }
  },
};

export default Store;
```

### 2.6 主题系统（沿用现有方案）

CSS 自定义属性方案已证明可靠（`assets/review.html` 中有完整实现）。

暗色/亮色双主题，通过 `<html data-theme="dark|light">` 切换。主题偏好存入 `localStorage`。

初始化脚本内联在 `<head>` 中（**必须在 index.html 内联，不能外置 JS**），防止页面闪烁：

```html
<script>
(function() {
  var saved = localStorage.getItem('la-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
})();
</script>
```

### 2.7 客户端 i18n

```javascript
// utils/i18n.js
let _locale = {};
let _lang = 'zh';

async function setLanguage(lang) {
  const resp = await fetch(`/locales/${lang}.json`);
  _locale = await resp.json();
  _lang = lang;
  localStorage.setItem('la-language', lang);
}

function t(key, params) {
  let val = _locale[key] || key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      val = val.replace(`{${k}}`, v);
    }
  }
  return val;
}

export { setLanguage, t };
```

i18n JSON 文件从 `src/i18n/zh.json` 和 `src/i18n/en.json` 复制到 `frontend/public/locales/`。

### 2.8 API 客户端设计

```javascript
// api.js
const API_BASE = '/api';

// --- 普通 JSON 请求 ---
async function get(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw await apiError(res);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(API_BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await apiError(res);
  return res.json();
}

async function del(path) {
  const res = await fetch(API_BASE + path, { method: 'DELETE' });
  if (!res.ok) throw await apiError(res);
  return res.json();
}

// --- 文件上传（带进度回调） ---
function uploadWithProgress(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', API_BASE + path);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(xhr.responseText));
      }
    };
    xhr.onerror = () => reject(new Error('上传失败'));
    xhr.send(formData);
  });
}

// --- SSE 流读取 ---
async function* sseStream(path, body) {
  const res = await fetch(API_BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}

// --- SSE 流（POST multipart，用于 ASR/解析）---
async function* sseUpload(path, formData) {
  const res = await fetch(API_BASE + path, {
    method: 'POST',
    body: formData,  // 不设 Content-Type，让浏览器自动设置 multipart boundary
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}

async function apiError(res) {
  try {
    const data = await res.json();
    return new Error(data.detail || `HTTP ${res.status}`);
  } catch {
    return new Error(`HTTP ${res.status}`);
  }
}

export { get, post, del, uploadWithProgress, sseStream, sseUpload };
```

### 2.9 Markdown/Math/Diagram 渲染

**KaTeX auto-render 导入说明：** KaTeX 的 auto-render 扩展是独立的入口点：
```javascript
import 'katex/dist/katex.min.css';
import renderMathInElement from 'katex/dist/contrib/auto-render.js';
```
Vite 会自动处理 CSS 中的字体文件引用，无需额外配置。

```javascript
// utils/markdown.js
import { marked } from 'marked';
import renderMathInElement from 'katex/dist/contrib/auto-render.js';
import mermaid from 'mermaid';

// 配置 Marked
marked.setOptions({
  breaks: false,
  gfm: true,
});

// 配置 Mermaid (不自动渲染)
mermaid.initialize({ startOnLoad: false, theme: 'neutral' });

// LaTeX 扫描器（复用 Python 版逻辑）
function normalizeLatex(text) {
  // 同 _normalize_latex 逻辑，JavaScript 重写
  // 关键：配对 $...$ / $$...$$，转义孤立 $
  // 实现见下方
}

// 渲染 Markdown + KaTeX + Mermaid
function renderMarkdown(md, container) {
  const normalized = normalizeLatex(md);
  const html = marked.parse(normalized);
  container.innerHTML = html;
  renderMath(container);
  renderMermaid(container);
}

function renderMath(container) {
  // 使用 KaTeX auto-render
  renderMathInElement(container, {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '$', right: '$', display: false },
    ],
    throwOnError: false,
  });
}

async function renderMermaid(container) {
  const blocks = container.querySelectorAll('pre code.language-mermaid');
  for (let i = 0; i < blocks.length; i++) {
    const code = blocks[i].textContent;
    const id = 'mermaid-' + Date.now() + '-' + i;
    try {
      const { svg } = await mermaid.render(id, code);
      const wrapper = document.createElement('div');
      wrapper.innerHTML = svg;
      wrapper.style.textAlign = 'center';
      wrapper.style.margin = '1em 0';
      blocks[i].parentElement.replaceWith(wrapper);
    } catch (e) {
      console.warn('Mermaid render error:', e);
    }
  }
}

export { renderMarkdown, normalizeLatex, renderMath, renderMermaid };
```

**关键风险点：LaTeX 扫描器的 JavaScript 重写。** 现有 Python 版 `_scan_math_delimiters` 约 60 行逻辑，需要逐字符精确移植到 JS。这是显示正确性的核心——移植错误会导致 KaTeX 渲染失败。必须在 Phase 2 完成时用真实内容测试验证。

**Markdown 图片 URL 重写：** 解析产出的 Markdown 中包含本地图片路径（如 `images/page_001.jpg`）。前端渲染前需将图片路径重写为 API 端点：
```javascript
// 将相对图片路径重写为 API URL
function rewriteImageUrls(markdown, courseId, docName) {
  return markdown.replace(
    /!\[([^\]]*)\]\((?!https?:\/\/)([^)]+)\)/g,
    `![$1](/api/courses/${courseId}/images/${docName}/$2)`
  );
}
```
此逻辑封装在 `renderMarkdown` 内部，调用者无需关心。

### 2.10 页面组件模式

每个页面模块导出 `render` 函数：

```javascript
// pages/home.js
import Store from '../store.js';
import { get, post, del } from '../api.js';
import { t } from '../utils/i18n.js';

export function renderHomePage() {
  const main = document.getElementById('main-content');
  main.innerHTML = '';
  // 构建 DOM
  main.appendChild(buildCourseGrid());
  main.appendChild(buildCreateForm());
}

function buildCourseGrid() { /* ... */ }
function buildCreateForm() { /* ... */ }
```

组件函数返回 DOM 元素，页面函数组装它们。不做虚拟 DOM diff——直接操作真实 DOM 节点。对于这个规模的应用（3 个页面，每个页面 3-5 个功能区），直接 DOM 操作足够清晰。

---

## 3. 后端 API 设计

### 3.1 路由拆分

将 `src/api/review_api.py`（~615 行单文件）拆分为模块化路由：

```
src/api/
├── __init__.py
├── server.py              ← FastAPI app 工厂 + CORS + 静态文件挂载
├── courses.py             ← 课程 CRUD
├── asr_routes.py          ← ASR 转录（SSE）
├── parser_routes.py       ← 课件解析 + EPUB 导入（SSE）
├── materials.py           ← 资料列表/查看/下载/删除
├── generate.py            ← 复习资料生成（SSE，从 review_api.py 提取）
└── chat.py                ← RAG 问答（SSE，从 review_api.py 提取）
```

### 3.2 共享依赖提取

多个路由模块共用的逻辑抽取到 `api/__init__.py` 或 `api/deps.py`：

```python
# src/api/deps.py
from src.config import get_config
from src.course_manager import CourseManager

_config = get_config()
_cm = CourseManager(_config.project.data_dir)

def get_cm(): return _cm
def get_config_obj(): return _config
```

### 3.3 完整 API 端点列表

#### 课程管理 (`courses.py`)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/courses` | 列出所有课程 | — | `{courses: [{name, audio_files, ..., kb_ready, materials_count}]}` |
| POST | `/api/courses` | 创建课程 | `{name: string}` | `{success: true, name: string}` |
| DELETE | `/api/courses/{course_id}` | 删除课程 | — | `{success: true}` |

#### 文件管理 (`materials.py`)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/courses/{id}/transcripts` | 列出转录文件 | — | `{transcripts: [{name, char_count, has_correction}]}` |
| GET | `/api/courses/{id}/documents` | 列出解析文档 | — | `{documents: [{name, char_count, type}]}` |
| DELETE | `/api/courses/{id}/transcripts/{name}` | 删除转录及关联文件 | — | `{success: true}` |
| DELETE | `/api/courses/{id}/documents/{name}` | 删除文档及关联源文件 | — | `{success: true}` |
| GET | `/api/courses/{id}/transcripts/{name}/download` | 下载转录 TXT | — | `text/plain` 文件流 |
| GET | `/api/courses/{id}/documents/{name}/download` | 下载文档 MD | — | `text/markdown` 文件流 |
| GET | `/api/courses/{id}/images/{doc}/{file}` | 提供解析产出的图片 | — | 图片二进制流（根据扩展名自动设 Content-Type） |

**图片服务说明：** PDF/PPT 解析会提取图片存入 `parsed_docs/{doc}_images/`。前端在渲染 Markdown 时，图片 `src` 指向此端点。路由需验证 `course_id` 存在且路径不越界（防止目录遍历攻击）。

#### ASR 转录 (`asr_routes.py`)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| POST | `/api/courses/{id}/transcribe` | 上传音频 + 转录 | multipart: `files` | SSE stream (见下方) |
| POST | `/api/courses/{id}/transcripts/confirm-correction` | 确认/放弃 AI 修正 | `{action: "confirm" \| "discard"}` | `{success: true}` |

**ASR SSE 事件类型：**

```json
{"type": "status", "phase": "loading_model", "message": "正在加载 ASR 模型..."}
{"type": "status", "phase": "transcribing", "file": "lecture1.mp3", "index": 1, "total": 3}
{"type": "result", "file": "lecture1.mp3", "text": "...", "segments": 42, "duration_sec": 3600}
{"type": "status", "phase": "summarizing", "message": "正在生成摘要..."}
{"type": "summary", "text": "本节课主要讲解了微积分基础概念..."}
{"type": "status", "phase": "correcting", "message": "检测到课件，正在自动修正转录..."}
{"type": "correction", "original": "...", "corrected": "..."}
{"type": "done", "results": [...]}
{"type": "error", "file": "bad.mp3", "message": "..."}
```

**AI 修正流程：** 转录完成后，后端自动检查是否有解析好的课件。如有，自动执行 AI 修正并推送 `correction` 事件。前端在收到 `correction` 事件后展示并排对比界面（原始 vs 修正），用户可选择"确认修正"（保存到 `_transcript_corrected.txt`）或"放弃修正"（保留原始转录）。确认/放弃操作通过 `POST /api/courses/{id}/transcripts/correct` 端点提交。如无课件，跳过修正步骤，`done` 事件直接发出。

#### 课件解析 (`parser_routes.py`)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| POST | `/api/courses/{id}/parse` | 上传 + 解析课件 | multipart: `files`, `options`(JSON) | SSE stream |
| POST | `/api/courses/{id}/import-epub` | 上传 + 导入 EPUB | multipart: `files` | SSE stream |

**解析 SSE 事件类型：**

```json
{"type": "status", "phase": "parsing", "file": "ch1.pdf", "index": 1, "total": 5}
{"type": "result", "file": "ch1.pdf", "markdown": "...", "formulas": 23, "tables": 5, "images": 8}
{"type": "done", "results": [...]}
{"type": "error", "file": "bad.pdf", "message": "..."}
```

#### 复习资料 (`generate.py`)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| GET | `/api/courses/{id}/materials` | 列出已保存资料 | — | `{materials: [{filename, material_type, ...}]}` |
| GET | `/api/courses/{id}/sources` | 列出可用源材料 | — | `{transcripts: [...], docs: [...]}` |
| POST | `/api/courses/{id}/generate` | 生成复习资料 | `{material_types, custom_extra?}` | SSE stream |
| DELETE | `/api/courses/{id}/materials/{filename}` | 删除资料 | — | `{success: true}` |
| GET | `/api/courses/{id}/materials/{filename}/download` | 下载资料 MD | — | `text/markdown` 文件流 |

**生成 SSE 事件（已有，从 review_api.py 继承）：**
```json
{"type": "status", "message": "正在生成..."}
{"type": "chunk", "content": "## 一、复习提纲\n\n..."}
{"type": "done", "materials": [...], "total_chars": 12345}
{"type": "error", "message": "..."}
```

#### RAG 问答 (`chat.py`)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| POST | `/api/courses/{id}/chat` | 流式问答 | `{message, history?}` | SSE stream |
| POST | `/api/courses/{id}/build-kb` | 构建知识库 | `{sources?: [...]}` | SSE stream |
| GET | `/api/courses/{id}/kb-status` | 查询知识库状态 | — | `{ready: bool, doc_count: int}` |
| DELETE | `/api/courses/{id}/kb` | 清空知识库 | — | `{success: true}` |

**问答 SSE 事件（已有）：**
```json
{"type": "chunk", "content": "根据课程内容..."}
{"type": "done", "content": "完整回答...", "sources": [...]}
{"type": "error", "message": "..."}
```

**构建知识库 SSE 事件：**
```json
{"type": "status", "phase": "chunking", "message": "正在分块..."}
{"type": "status", "phase": "embedding", "message": "正在向量化...", "progress": 45}
{"type": "done", "doc_count": 230}
{"type": "error", "message": "..."}
```

### 3.4 静态文件服务（生产模式）

```python
# server.py
from fastapi.staticfiles import StaticFiles
from pathlib import Path

_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

app = FastAPI(title="Lecture Assistant API")
app.add_middleware(CORSMiddleware, ...)

# API 路由
app.include_router(courses.router)
app.include_router(asr_routes.router)
# ... etc

# 生产模式：serve 前端静态文件
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
```

开发模式：Vite dev server (:5173) 代理 `/api` 到 FastAPI (:8502)。前端开发时不走 FastAPI 静态文件。

### 3.5 run.py 简化

```python
"""Lecture Assistant 主入口"""
import sys
import uvicorn
from pathlib import Path

_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from src.api.server import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8502)
```

不再启动 Streamlit。FastAPI 同时 serve API + 前端静态文件。

---

## 4. 分步实施计划

### Phase 1: 项目脚手架 (预计 1 个 session)

**目标：** 搭建 Vite 项目骨架 + CSS 变量体系，不写业务逻辑。

#### Step 1.1: 创建 Vite 项目

```bash
cd frontend/
npm init -y
npm install katex marked mermaid
npm install -D vite
```

#### Step 1.2: 创建文件

**`frontend/index.html`** — SPA 入口
- `<head>` 内联主题防闪烁脚本
- `<link>` 引入 KaTeX CSS
- `<div id="app">` 结构：顶栏 `#nav` + 主内容 `#main-content`
- `<script type="module" src="/src/main.js">`

**`frontend/vite.config.js`** — 见 2.3 节

**`frontend/src/styles/base.css`** — CSS 变量 + reset
- 从 `assets/review.html` 提取 `:root` 和 `[data-theme="light"]` 变量定义（已生产验证）
- 排版、滚动条样式
- **遵守安全边界：不设 `* { font-family }`，不碰 `.katex` 系列类**

#### Step 1.3: 复制 i18n 文件

```bash
cp src/i18n/zh.json frontend/public/locales/zh.json
cp src/i18n/en.json frontend/public/locales/en.json
```

#### Step 1.4: 验证

```bash
cd frontend && npx vite
# 打开 http://localhost:5173，确认白屏无报错
# 确认 data-theme 属性正确设置
```

---

### Phase 2: 前端核心模块 (预计 1 个 session)

**目标：** router、store、i18n、theme、api、markdown 六大核心模块全部可工作。

#### Step 2.1: 实现核心模块

按顺序创建：
1. `utils/dom.js` — `$`(querySelector), `$$`(querySelectorAll), `createElement(tag, attrs, children)`, `escapeHtml(str)`
2. `utils/i18n.js` — `setLanguage()`, `t()`
3. `store.js` — 见 2.5 节
4. `router.js` — 见 2.4 节
5. `components/theme.js` — `initTheme()`, `toggleTheme()`
6. `api.js` — 见 2.8 节（先实现 `get`/`post`/`del`，SSE 在 Phase 4/5 实现）
7. `utils/markdown.js` — 见 2.9 节（**重点：LaTeX 扫描器 JS 移植**）

#### Step 2.2: LaTeX 扫描器 JS 移植验证

用现有 Python 版测试用例（从 `_scan_math_delimiters` 的单元测试或手动用例）验证 JS 版输出一致：

| 输入 | 期望输出 |
|------|----------|
| `$x^2$` | `$x^2$` |
| `$x^2 + y$` | `$x^2 + y$` |
| `$$a+b$$` | `$$a+b$$` |
| `$未闭合` | `\$未闭合` |
| `价格$100` | `价格\$100` |
| `公式$E=mc^2$和$F=ma$` | `公式$E=mc^2$和$F=ma$` |
| `中文$公式$中文` | `中文$公式$中文` |

**此步骤是最容易出错的环节。** 必须在此验证通过后再继续。

#### Step 2.3: 实现导航栏组件

`components/nav.js` — 顶栏：
- 左侧：Logo/标题 → 链接 `#home`
- 中间：当前课程名 + 页面标签（资料录入 / 复习问答）
- 右侧：主题切换按钮 + 语言切换按钮

`styles/nav.css` — 从 `assets/review.html` 的 `.top-nav` 提取（已验证样式）

#### Step 2.4: 实现 main.js

组装所有模块：

```javascript
// main.js
import './styles/base.css';
import './styles/nav.css';
import { initTheme } from './components/theme.js';
import { setLanguage } from './utils/i18n.js';
import { renderNav } from './components/nav.js';
import Store from './store.js';

async function init() {
  initTheme();
  await setLanguage(Store.get('language'));
  renderNav();
  // 路由在 DOMContentLoaded 后自动触发首次渲染
}

init();
```

#### Step 2.5: 验证

- 导航栏渲染正确（暗色/亮色）
- 主题切换按钮工作
- 语言切换加载不同 JSON
- 浏览器 console 无报错

---

### Phase 3: 后端 API 重构 (预计 1 个 session)

**目标：** 拆分 `review_api.py` + 新增缺失的 API 端点，所有路由可测试。

#### Step 3.1: 提取共享依赖

创建 `src/api/deps.py`：

```python
from src.config import get_config
from src.course_manager import CourseManager

_config = get_config()
_cm = CourseManager(_config.project.data_dir)
```

#### Step 3.2: 拆分现有路由

从 `review_api.py` 提取并创建：

**`src/api/server.py`**：
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .courses import router as courses_router
from .materials import router as materials_router
from .generate import router as generate_router
from .chat import router as chat_router
from .asr_routes import router as asr_router
from .parser_routes import router as parser_router

app = FastAPI(title="Lecture Assistant API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(courses_router)
app.include_router(materials_router)
app.include_router(generate_router)
app.include_router(chat_router)
app.include_router(asr_router)
app.include_router(parser_router)
```

**`src/api/courses.py`** — GET/POST/DELETE `/api/courses`
- GET — 从 `review_api.py` 的 `list_courses()` 提取
- POST — 新增：验证课程名、创建目录、初始化状态
- DELETE — 新增：删除整个课程目录

**`src/api/materials.py`** — GET/DELETE 资料和源文件
- 从 `review_api.py` 的 `get_materials()` 和 `get_sources()` 提取
- 新增 DELETE 和 download 端点

**`src/api/generate.py`** — POST `/api/courses/{id}/generate` (SSE)
- 从 `review_api.py` 的 `generate_material()` 完整提取
- 包括所有 helper 函数（`_build_type_sections`, `_build_generation_prompt`, `_normalize_latex`, `_split_by_sections`）——这些是当前唯一存在的副本，提取后 Streamlit 版和 API 版共享同一个来源

**`src/api/chat.py`** — POST `/api/courses/{id}/chat` (SSE)
- 从 `review_api.py` 的 `chat()` 完整提取

#### Step 3.3: 新增 API 端点

**`src/api/asr_routes.py`**：
```python
router = APIRouter(prefix="/api")

@router.post("/courses/{course_id}/transcribe")
async def transcribe(course_id: str, files: list[UploadFile]):
    # 1. 保存所有上传文件到 audio/
    # 2. SSE stream: 加载模型 → 逐文件转录 → 自动摘要 → (可选)AI修正
    # 复用 src/asr/funasr_asr.py 的 get_asr_model() 和 transcribe()
    pass
```

**`src/api/parser_routes.py`**：
```python
@router.post("/courses/{course_id}/parse")
async def parse_docs(course_id: str, files: list[UploadFile], options: str = "{}"):
    # 1. 解析 options JSON
    # 2. 保存所有上传文件到 courseware/
    # 3. SSE stream: 逐文件解析 → 返回结果
    pass

@router.post("/courses/{course_id}/import-epub")
async def import_epub(course_id: str, files: list[UploadFile]):
    # 同上，使用 EPUB parser
    pass
```

**`src/api/chat.py`** 新增：
```python
@router.post("/courses/{course_id}/build-kb")
async def build_kb(course_id: str):
    # SSE: 扫描源材料 → 分块 → 嵌入 → 存入 ChromaDB
    pass

@router.get("/courses/{course_id}/kb-status")
async def kb_status(course_id: str):
    # 返回 {ready: bool, doc_count: int}
    pass

@router.delete("/courses/{course_id}/kb")
async def clear_kb(course_id: str):
    # 删除 ChromaDB 集合
    pass
```

#### Step 3.4: 更新 run.py

简化为纯 FastAPI 启动（见 3.5 节）。

#### Step 3.5: 验证

用 curl 测试每个端点：

```bash
# 启动后端
python run.py

# 测试
curl http://localhost:8502/api/courses
curl -X POST http://localhost:8502/api/courses -H 'Content-Type: application/json' -d '{"name":"测试课程"}'
curl http://localhost:8502/api/courses/测试课程/sources
# ... etc
```

---

### Phase 4: 前端 - 首页 (预计 1 session)

**目标：** `#home` 页面完整功能。

#### Step 4.1: 课程列表

`pages/home.js`:
- `renderHomePage()` — 主渲染函数
- 从 `GET /api/courses` 获取课程列表
- 卡片网格布局：每个课程显示名称、资料数、KB 状态
- 空状态：引导创建第一个课程
- 加载中：骨架屏或 spinner

#### Step 4.2: 创建/删除课程

- 创建：输入框 + "创建"按钮 → `POST /api/courses`
- 删除：每个卡片上的删除按钮 → 确认弹窗 → `DELETE /api/courses/{id}`
- 操作成功后刷新列表

#### Step 4.3: 进入课程

- 点击课程卡片 → `Store.set('currentCourse', name)` → `window.location.hash = '#materials'`
- 导航栏自动更新显示当前课程名

#### Step 4.4: 样式

`styles/home.css`:
- 卡片网格（CSS Grid, 响应式列数）
- 卡片悬停效果
- 创建表单样式

#### Step 4.5: 验证

- 课程列表正确加载
- 创建/删除课程后列表刷新
- 空状态正确显示
- 点击课程卡片跳转到资料录入页

---

### Phase 5: 前端 - 资料录入页 (预计 2 sessions)

**目标：** `#materials` 页面完整功能，最复杂的页面。

#### Step 5.1: 页面框架

`pages/materials.js`:
- 三 Tab 布局：语音转文字 / 课件解析 / 电子书导入
- Tab 切换（纯 CSS + JS 显示/隐藏）
- 侧边栏：已有文件列表（转录 + 解析文档）

#### Step 5.2: 文件上传组件

通用的拖拽上传区域：

```javascript
function createDropZone(accept, onFiles) {
  const zone = createElement('div', { class: 'drop-zone' });
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

  return zone;
}
```

#### Step 5.3: ASR 转录功能

流程：
1. 用户在拖拽区上传音频文件 → 文件列表显示（名称 + 大小）
2. 点击 "开始转录" → 构建 FormData → `POST /api/courses/{id}/transcribe`
3. 通过 SSE 流读取进度事件：
   - `loading_model` → 显示 "正在加载语音识别模型..."
   - `transcribing` → 显示进度条 "正在转录 lecture1.mp3 (1/3)..."
   - `result` → 显示转录结果（文本区域 + 字符数统计）
   - `summary` → 显示 AI 自动摘要
   - `correction` → 显示并排对比（原始 vs 修正）
   - `done` → 刷新已有文件列表
4. 用户可确认修正或放弃
5. 下载/删除转录结果

#### Step 5.4: 课件解析功能

流程同 ASR，但针对 PDF/PPT：
1. 上传 → 文件列表
2. 可选配置（公式识别、表格识别勾选框）
3. 开始解析 → SSE 接收进度和结果
4. 结果显示：Markdown 预览 + 公式数/表格数/图片数
5. 下载/删除

#### Step 5.5: EPUB 导入

流程同上，参数更简单（无配置选项）。
显示元数据：书名、作者、章节数。

#### Step 5.6: 已有文件管理

侧边栏显示课程下已有的转录和文档：
- 文件名列表
- 点击可预览
- 删除按钮（含确认）
- 下载按钮

#### Step 5.7: 样式

`styles/materials.css`:
- 拖拽上传区（虚线边框 + 悬停高亮）
- 进度条动画
- 文件列表
- 并排对比面板

#### Step 5.8: 验证

- 拖拽上传音频 → 转录 → 显示结果
- 上传 PDF → 解析 → 预览
- 上传 EPUB → 导入 → 元数据显示
- 删除/下载按钮工作
- Tab 切换保持状态

---

### Phase 6: 前端 - 复习问答页 (预计 2 sessions)

**目标：** `#review` 页面完整功能。基于 `assets/review.html` 的大量现有代码。

#### Step 6.1: 页面布局

左栏（资料区）+ 右栏（聊天区）：
```
+----------------------------------+-------------------+
|  资料 Tab 列表                    |  知识库状态栏       |
|  [提纲] [笔记] [结构图] [题库]    |  聊天消息列表       |
|                                  |                   |
|  资料内容（Markdown 渲染）        |  输入框 + 发送按钮  |
|                                  |                   |
|  [下载] [删除] [导入知识库]       |                   |
+----------------------------------+-------------------+
```

#### Step 6.2: 资料 Tab 栏

- 从 `GET /api/courses/{id}/materials` 获取资料列表
- Tab 标签使用缩写（提纲/笔记/结构图/题库）
- 点击 Tab 加载并渲染内容（`renderMarkdown`）
- 空状态：引导生成第一份资料

#### Step 6.3: 生成资料弹窗

复用 `assets/review.html` 的 modal 组件逻辑：
- 资料类型多选（默认全选）
- 附件要求文本框
- 源材料信息显示
- "开始生成" 按钮 → SSE 流式接收 → 实时渲染
- 生成完成后自动刷新 Tab 列表

**SSE 流式渲染关键逻辑（从 review.html 移植）：**
```javascript
async function startGenerate() {
  const body = { material_types: selectedTypes, custom_extra: extra };
  let streamContent = '';
  let lastKatexTime = 0;

  for await (const evt of sseStream(`/courses/${courseId}/generate`, body)) {
    if (evt.type === 'chunk') {
      streamContent += evt.content;
      contentEl.innerHTML = renderContentLight(streamContent);
      // 每 300ms 重新渲染公式和图表
      const now = Date.now();
      if (now - lastKatexTime > 300) {
        renderMathAndMermaid(contentEl);
        lastKatexTime = now;
      }
      contentArea.scrollTop = contentArea.scrollHeight;
    } else if (evt.type === 'done') {
      contentEl.innerHTML = renderContent(streamContent);
      renderMathAndMermaid(contentEl);
      await loadMaterials(); // 刷新列表
      renderTabs();
    }
  }
}
```

#### Step 6.4: 知识库管理

- 状态指示器：绿点 = 就绪，灰点 = 未构建
- "构建知识库" 按钮 → SSE 接收进度（分块 → 嵌入 → 完成）
- "清空" 按钮 → 确认 → DELETE
- 知识库就绪后启用聊天输入框

#### Step 6.5: RAG 聊天

从 `assets/review.html` 的 `sendMessage()` 完整移植（~90 行 JS）。
关键功能：
- 消息气泡（用户右/ai 左）
- 流式输出（逐 chunk 渲染 + 滚动）
- 来源引用折叠面板
- 重新生成（默认/更详细/更口语化）
- 导出对话
- 清空对话

#### Step 6.6: 样式

- `styles/review.css` — 左右分栏布局
- `styles/chat.css` — 从 `assets/review.html` 提取（已验证）
- `styles/modal.css` — 弹窗样式

#### Step 6.7: 验证

- Tab 切换加载不同资料
- 生成弹窗 → 流式渲染 → 自动保存
- 构建知识库 → 状态更新
- 聊天 → 流式回复 → 来源显示
- 重新生成 → 风格变化
- 导出对话 → 下载 MD 文件

---

### Phase 7: 收尾与清理 (预计 1 session)

#### Step 7.1: 生产构建验证

```bash
cd frontend && npm run build
python run.py  # FastAPI serve frontend/dist/
# 访问 http://localhost:8502 验证完整功能
```

#### Step 7.2: 错误处理完善

- 网络错误：显示 Toast + 重试按钮
- API 错误：显示具体错误信息
- 长时间操作：超时处理 + 取消按钮
- 文件过大：前端校验 + 后端限制

#### Step 7.3: 响应式优化

- 移动端（<768px）：上下布局替代左右分栏
- 平板端（768-1024px）：缩小字体和间距
- 触控优化：所有交互元素 ≥ 32px 点按目标

#### Step 7.4: 清理 Streamlit 代码

- 将 `pages/` 目录重命名为 `pages_streamlit_backup/`
- 将 `src/ui/` 目录重命名为 `src/ui_streamlit_backup/`
- 从 `requirements.txt` 移除 `streamlit` 依赖
- 更新 `README.md` 的安装和启动说明

---

## 5. 可行性验证

### 5.1 技术风险评估

| 风险 | 严重度 | 概率 | 缓解措施 |
|------|--------|------|----------|
| LaTeX 扫描器 JS 移植错误 | **高** | 中 | Phase 2 用测试用例逐条验证；保留 Python 版逻辑不删 |
| FunASR 模型在 FastAPI 线程中加载失败 | 中 | 低 | 已验证 Streamlit 中可加载；FastAPI 同进程，风险极低 |
| MinerU subprocess 在 FastAPI 中阻塞 | 中 | 低 | 使用 `asyncio.to_thread()` 或 `run_in_executor()` |
| SSE 在移动端 WebView 中断连 | 中 | 中 | 实现自动重连 + 断点续传（Phase 7 增强） |
| 大文件上传超时 | 中 | 低 | FastAPI 默认无超时；uvicorn 可配置 `timeout_keep_alive` |
| 浏览器内存（大 Markdown 渲染） | 低 | 低 | 资料按 Tab 懒加载，不一次渲染所有 |
| ChromaDB 文件锁冲突（前后端同时访问） | 低 | 低 | 无 Streamlit，只有 FastAPI 访问，无冲突 |

### 5.2 SSR → SPA 功能等价性

逐项对比 Streamlit 页面功能和 HTML 替代方案：

| Streamlit 功能 | HTML 替代 | 备注 |
|----------------|-----------|------|
| `st.file_uploader` | 自定义拖拽上传区 + `<input type="file">` | 更灵活，支持拖拽 |
| `st.progress` | `<progress>` 元素 + SSE 进度事件 | 更精确 |
| `st.status` | 自定义状态面板 + SSE 事件驱动 | 更实时 |
| `st.tabs` | CSS tabs（radio button hack 或 JS 切换） | 纯 CSS 方案更轻 |
| `st.expander` | `<details><summary>` 原生 HTML | 无需 JS |
| `st.chat_input` | `<textarea>` + 发送按钮 | 已经实现 |
| `st.chat_message` | `<div class="msg msg-user/ai">` | 已经实现 |
| `st.markdown` | `marked.parse()` + KaTeX + Mermaid | 已经实现 |
| `st.dataframe` | N/A（当前未使用） | 不需要 |
| `st.plotly_chart` | N/A（当前未使用） | 不需要 |
| `st.metric` | CSS 卡片 + 数字 | 简单 |
| `st.warning/error/success/info` | Toast 通知 + 内联消息 | 更灵活 |
| `st.rerun()` | 页面状态刷新（重新 fetch 数据） | 按需 fetch，更高效 |
| `st.session_state` | `store.js`（内存 + localStorage 部分持久化） | 首次加载需从 API 恢复状态 |

**结论：所有 Streamlit 功能都有等价或更好的 HTML 替代。无功能丢失。**

### 5.3 代码复用分析

| 组件 | 复用来源 | 复用程度 |
|------|----------|----------|
| CSS 变量体系 | `assets/review.html` `:root` 块 | 95% 直接复制 |
| 聊天 CSS | `assets/review.html` `.msg`, `.chat-*` | 90% 直接复制 |
| 导航 CSS | `assets/review.html` `.top-nav`, `.nav-*` | 85% 直接复制 |
| SSE 流读取 | `assets/review.html` `sendMessage()` 逻辑 | 结构复用，模块化重写 |
| 生成弹窗 | `assets/review.html` modal + `startGenerate()` | 80% 逻辑复用 |
| LaTeX 扫描器 | `review_api.py` `_scan_math_delimiters` | 逐字符移植到 JS |
| Prompt 构建 | `review_api.py` `_build_type_sections` 等 | 后端保留，前端不碰 |
| ASR/Parser 调用 | `1_资料录入.py` 逻辑 | 后端重新封装为 API，前端只调接口 |

**总结：CSS + 聊天 + 导航约 400 行 CSS 和 200 行 JS 逻辑可直接从 `review.html` 移植，大幅减少工作量。**

### 5.4 打包兼容性

| 目标平台 | 方案 | 前端改动 | 后端改动 |
|----------|------|----------|----------|
| Tauri (Win/Mac/Linux) | Rust 壳 + system WebView + Python sidecar | 零改动（Vite 构建产物直接内嵌） | PyInstaller 打包为单文件 exe |
| Capacitor (Android/iOS) | WebView 壳 + 云端 API | `base: './'` 已配置相对路径 | 部署到云服务器，CORS 已配 |
| PWA | Service Worker + manifest | 添加 `manifest.json` + SW 脚本 | 零改动 |

---

## 6. 附录：对照检查清单

### 6.1 页面功能对照

#### 首页 (home)
- [ ] 显示所有课程卡片（名称、文件数、资料数、KB 状态）
- [ ] 创建新课程（输入名称 → 创建）
- [ ] 删除课程（确认弹窗 → 删除）
- [ ] 点击课程进入工作区
- [ ] 空状态：无课程时的引导文案

#### 资料录入 (materials)
- [ ] Tab 1: 语音转文字
  - [ ] 拖拽/点击上传音频文件
  - [ ] 文件列表显示（名称 + 大小）
  - [ ] 开始转录按钮
  - [ ] 转录进度显示（模型加载 → 逐文件转录）
  - [ ] 转录结果展示（文本 + 分段数 + 时长）
  - [ ] 自动 AI 摘要显示
  - [ ] AI 修正（如有课件）：并排对比
  - [ ] 确认/放弃修正
  - [ ] 下载转录 TXT
  - [ ] 删除转录
- [ ] Tab 2: 课件解析
  - [ ] 拖拽/点击上传 PDF/PPT
  - [ ] 解析选项（公式识别、表格识别、方法）
  - [ ] 解析进度
  - [ ] 结果：Markdown 预览 + 统计（公式/表格/图片数）
  - [ ] 下载 Markdown
  - [ ] 删除文档
- [ ] Tab 3: 电子书导入
  - [ ] 拖拽/点击上传 EPUB
  - [ ] 进度显示
  - [ ] 结果：元数据（书名/作者/章节数）+ 预览
  - [ ] 下载 Markdown
  - [ ] 删除
- [ ] 已有文件列表（所有 Tab 共享的侧边栏）

#### 复习问答 (review)
- [ ] 左侧资料区
  - [ ] Tab 标签栏（按类型分组）
  - [ ] 资料内容渲染（Markdown + KaTeX + Mermaid）
  - [ ] 下载资料 MD
  - [ ] 删除资料
  - [ ] 导入资料到知识库
  - [ ] 空状态：引导生成
- [ ] 生成弹窗
  - [ ] 资料类型多选
  - [ ] 源材料信息
  - [ ] 附加要求输入
  - [ ] 流式生成预览
  - [ ] 完成后自动刷新
- [ ] 右侧聊天区
  - [ ] 知识库状态指示器
  - [ ] 构建知识库按钮（含进度）
  - [ ] 清空知识库按钮
  - [ ] 消息列表（用户/AI 气泡）
  - [ ] 流式回复渲染
  - [ ] 来源引用折叠面板
  - [ ] 重新生成（默认/详细/口语化）
  - [ ] 导出对话
  - [ ] 清空对话
  - [ ] 知识库未就绪时禁用输入

### 6.2 全局功能
- [ ] 暗色/亮色主题切换
- [ ] 中/英语言切换
- [ ] 响应式布局（桌面/平板/手机）
- [ ] 所有错误显示友好提示
- [ ] 长时间操作有进度指示

---

## 附录 A: Prompt 逻辑去重方案

当前 `_build_type_sections`、`_build_generation_prompt`、`_normalize_latex`、`_split_by_sections` 在 `pages/2_复习与问答.py` 和 `api/review_api.py` 中完全重复。

Phase 3 将这些函数提取到共享模块：

```
src/llm/
├── prompts.py       ← _build_type_sections, _build_generation_prompt
├── latex_utils.py   ← _normalize_latex, _scan_math_delimiters
└── section_split.py ← _split_by_sections, _CN_SECTION_MAP, _CN_NUMS
```

Streamlit 页面和 API 路由都从这些模块导入，消除重复。

## 附录 B: API 与 Streamlit 功能映射速查

| Streamlit 页面位置 | 功能 | API 端点 |
|-------------------|------|----------|
| `run.py` 课程列表 | 列出课程 | `GET /api/courses` |
| `run.py` 创建课程 | sidebar 创建 | `POST /api/courses` |
| `1_资料录入.py` ASR | 上传+转录 | `POST /api/courses/{id}/transcribe` |
| `1_资料录入.py` 解析 | 上传+解析 | `POST /api/courses/{id}/parse` |
| `1_资料录入.py` EPUB | 上传+导入 | `POST /api/courses/{id}/import-epub` |
| `1_资料录入.py` 已存文件 | 列表/删除 | `GET/DELETE /api/courses/{id}/transcripts` |
| `2_复习与问答.py` 构建KB | 构建知识库 | `POST /api/courses/{id}/build-kb` |
| `2_复习与问答.py` 生成 | 生成资料 | `POST /api/courses/{id}/generate` |
| `2_复习与问答.py` 查看资料 | 资料列表 | `GET /api/courses/{id}/materials` |
| `2_复习与问答.py` 问答 | RAG 聊天 | `POST /api/courses/{id}/chat` |
