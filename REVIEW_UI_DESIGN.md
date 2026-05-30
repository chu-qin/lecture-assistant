# review.html 界面设计规格

> 面向 `assets/review.html`。这是一个纯 HTML/CSS/JS 文件，有完整的 DOM 控制权，
> 不受 Streamlit 任何限制。按本文档实施，不需要迁就框架。

---

## 一、整体风格

参照：Linear、Raycast、Vercel Dashboard。
特点：高密度信息、低噪音视觉、克制的动效、专注内容本身。
不要：渐变大背景、发光特效、过度圆角、卡片堆卡片。

---

## 二、颜色系统

在 `:root` 中定义，支持亮/暗两套，通过 `[data-theme="dark"]` 切换。

```css
:root {
    /* 暗色主题（默认） */
    --bg-app:        #0d0d0f;   /* 最底层，整页背景 */
    --bg-panel:      #111114;   /* 面板背景：侧边栏、顶栏 */
    --bg-surface:    #18181c;   /* 卡片、输入框背景 */
    --bg-hover:      #1f1f24;   /* 悬停状态 */
    --bg-active:     #25252c;   /* 激活/选中状态 */

    --text-primary:  #ededef;   /* 主要文字 */
    --text-secondary:#8b8b9a;   /* 次要文字、标签、占位符 */
    --text-muted:    #4a4a58;   /* 禁用、分隔线旁文字 */

    --accent:        #7c6af7;   /* 主品牌色（紫蓝，学术感） */
    --accent-hover:  #9585f9;
    --accent-dim:    rgba(124, 106, 247, 0.15);

    --border:        rgba(255,255,255,0.07);
    --border-strong: rgba(255,255,255,0.13);

    --success:       #3dd68c;
    --success-dim:   rgba(61, 214, 140, 0.12);
    --warning:       #f5a623;
}

[data-theme="light"] {
    --bg-app:        #f5f5f7;
    --bg-panel:      #ffffff;
    --bg-surface:    #ffffff;
    --bg-hover:      #f0f0f3;
    --bg-active:     #e8e8ed;

    --text-primary:  #1a1a1f;
    --text-secondary:#6b6b7a;
    --text-muted:    #b0b0bc;

    --accent:        #5b4de0;
    --accent-hover:  #4a3ec8;
    --accent-dim:    rgba(91, 77, 224, 0.1);

    --border:        rgba(0,0,0,0.08);
    --border-strong: rgba(0,0,0,0.15);

    --success:       #1a9e5c;
    --success-dim:   rgba(26, 158, 92, 0.1);
    --warning:       #c47d0a;
}
```

---

## 三、字体与排版

```css
body {
    font-family: -apple-system, 'Inter', 'PingFang SC', 'Noto Sans SC', sans-serif;
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-primary);
    background: var(--bg-app);
    -webkit-font-smoothing: antialiased;
}

/* 字号阶梯 */
/* 11px: 徽章、状态标签 */
/* 12px: 辅助说明、时间戳 */
/* 13px: 对话消息、次要信息 */
/* 14px: 正文（默认） */
/* 15px: 小标题 */
/* 18px: 页面内容 h2 */
/* 22px: 页面内容 h1 */

/* 内容区 Markdown 排版 */
.content-body h1 { font-size: 22px; font-weight: 650; letter-spacing: -0.02em; margin: 0 0 20px; }
.content-body h2 { font-size: 18px; font-weight: 600; letter-spacing: -0.01em; margin: 32px 0 12px; }
.content-body h3 { font-size: 15px; font-weight: 600; margin: 24px 0 8px; }
.content-body p  { margin: 0 0 14px; line-height: 1.75; }
.content-body li { line-height: 1.75; margin-bottom: 4px; }

/* 代码块 */
.content-body code {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12.5px;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1px 5px;
}

.content-body pre {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    margin: 12px 0 20px;
}

.content-body pre code {
    background: none;
    border: none;
    padding: 0;
}
```

---

## 四、布局结构

```
┌─────────────────────────── 顶部导航栏 48px fixed ───────────────────────────┐
│ [课程名]    [提纲] [笔记] [结构图] [题库]                    [主题] [导出]   │
├──────────────────────────────────────┬──────────────────────────────────────┤
│                                      │ 智能问答                      [清空] │
│  内容区                              ├──────────────────────────────────────┤
│  overflow-y: auto                    │                                      │
│  padding: 40px 48px                  │  对话历史区                          │
│                                      │  overflow-y: auto                    │
│  （Markdown + KaTeX + Mermaid）      │  flex: 1                             │
│                                      │                                      │
│                                      ├──────────────────────────────────────┤
│                                      │  [textarea]              [发送按钮]  │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

```css
html, body { height: 100%; margin: 0; overflow: hidden; }

.top-nav {
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 48px;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 4px;
    z-index: 200;
}

.main-layout {
    display: flex;
    height: 100vh;
    padding-top: 48px;
}

.content-area {
    flex: 1;
    overflow-y: auto;
    min-width: 0; /* 防止 flex 子项溢出 */
}

.content-body {
    max-width: 760px;
    margin: 0 auto;
    padding: 40px 48px 80px;
}

.chat-panel {
    width: 380px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--border);
    background: var(--bg-panel);
}

.chat-header {
    height: 48px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    padding: 0 16px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
}

.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.chat-input-area {
    flex-shrink: 0;
    padding: 12px 16px;
    border-top: 1px solid var(--border);
    display: flex;
    gap: 8px;
    align-items: flex-end;
}
```

---

## 五、组件规格

### 5.1 顶部导航栏

```css
/* 课程名 */
.nav-course {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    padding: 4px 8px;
    margin-right: 8px;
    white-space: nowrap;
}

/* 分隔线 */
.nav-divider {
    width: 1px;
    height: 16px;
    background: var(--border-strong);
    margin: 0 8px;
}

/* Tab 按钮 */
.nav-tab {
    height: 28px;
    padding: 0 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 450;
    color: var(--text-secondary);
    background: transparent;
    border: none;
    cursor: pointer;
    white-space: nowrap;
    transition: color 0.12s, background 0.12s;
}

.nav-tab:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
}

.nav-tab.active {
    color: var(--text-primary);
    background: var(--bg-active);
    font-weight: 500;
}

/* 右侧工具按钮 */
.nav-actions { margin-left: auto; display: flex; gap: 4px; align-items: center; }

.nav-btn {
    height: 28px;
    padding: 0 10px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--text-secondary);
    background: transparent;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.12s;
}

.nav-btn:hover {
    color: var(--text-primary);
    border-color: var(--border);
    background: var(--bg-hover);
}
```

### 5.2 内容区生成按钮（当该资料未生成时显示）

```css
.generate-prompt {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 320px;
    gap: 16px;
    color: var(--text-muted);
}

.generate-prompt p {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0;
}

.btn-generate {
    height: 36px;
    padding: 0 20px;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.12s, transform 0.08s;
}

.btn-generate:hover  { background: var(--accent-hover); }
.btn-generate:active { transform: scale(0.98); }
```

### 5.3 内容区生成中状态

```css
/* 流式输出时的光标闪烁 */
.streaming-cursor::after {
    content: '|';
    animation: blink 0.9s infinite;
    color: var(--accent);
    font-weight: 300;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0; }
}
```

### 5.4 知识库状态徽章

```css
.kb-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 500;
}

.kb-badge.ready {
    background: var(--success-dim);
    color: var(--success);
    border: 1px solid rgba(61, 214, 140, 0.2);
}

/* 状态点 */
.kb-badge.ready::before {
    content: '';
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--success);
}
```

### 5.5 对话消息气泡

```css
.msg {
    max-width: 88%;
    font-size: 13px;
    line-height: 1.7;
    padding: 10px 14px;
    border-radius: 12px;
    word-break: break-word;
}

.msg-user {
    align-self: flex-end;
    background: var(--accent);
    color: #fff;
    border-radius: 12px 12px 3px 12px;
}

.msg-ai {
    align-self: flex-start;
    background: var(--bg-surface);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 3px 12px 12px 12px;
}

/* AI 消息内的内联公式颜色不受气泡背景影响 */
.msg-ai .katex { color: var(--text-primary); }
```

### 5.6 输入框

```css
.chat-textarea {
    flex: 1;
    min-height: 36px;
    max-height: 120px;
    padding: 8px 12px;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 13px;
    font-family: inherit;
    resize: none;
    outline: none;
    transition: border-color 0.12s;
    line-height: 1.5;
}

.chat-textarea::placeholder { color: var(--text-muted); }

.chat-textarea:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-dim);
}

.btn-send {
    width: 36px;
    height: 36px;
    flex-shrink: 0;
    background: var(--accent);
    border: none;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.12s, transform 0.08s;
    color: #fff;
}

.btn-send:hover  { background: var(--accent-hover); }
.btn-send:active { transform: scale(0.95); }
.btn-send:disabled { background: var(--bg-active); color: var(--text-muted); cursor: not-allowed; }

/* 发送按钮内的箭头图标（纯 CSS，无需图标库） */
.btn-send svg { width: 16px; height: 16px; }
```

### 5.7 滚动条统一样式

```css
* { scrollbar-width: thin; scrollbar-color: var(--border-strong) transparent; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: var(--border-strong);
    border-radius: 2px;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
```

---

## 六、交互细节

### 主题切换

```javascript
function setTheme(theme) {
    // theme: 'dark' | 'light' | 'system'
    const resolved = theme === 'system'
        ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
        : theme;
    document.documentElement.setAttribute('data-theme', resolved);
    localStorage.setItem('la-theme', theme);
}

// 页面加载时立即应用（放在 <head> 里，避免闪烁）
const saved = localStorage.getItem('la-theme') || 'dark';
setTheme(saved);
```

把上面的 `setTheme` 调用放在 `<head>` 的 `<script>` 标签里（非 defer），防止页面加载时出现颜色闪烁。

### textarea 自动高度

```javascript
chatTextarea.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});
```

### Enter 发送 / Shift+Enter 换行

```javascript
chatTextarea.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
```

### 对话区自动滚到底部

```javascript
// SSE 流式输出时调用，只在用户没有向上滚动时才自动滚动
function scrollToBottomIfNeeded() {
    const threshold = 80;
    const isNearBottom = chatMessages.scrollHeight - chatMessages.scrollTop
                         - chatMessages.clientHeight < threshold;
    if (isNearBottom) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}
```

### 生成中禁用切换

资料正在流式生成时，顶部 tab 按钮加 `disabled` 样式（`pointer-events: none; opacity: 0.5`），
生成完成后恢复，防止中途切换导致内容丢失。

---

## 七、不涉及的部分

- API 接口逻辑（已在 MIGRATE_REVIEW_PAGE.md 中定义）
- KaTeX / Mermaid 的渲染逻辑（复用 MIGRATE_REVIEW_PAGE.md 中的方案）
- `assets/styles/` 下的现有 Streamlit CSS 文件

---

## 八、验收标准

1. 暗色/亮色主题切换无闪烁，刷新页面后主题状态保持
2. 内容区与对话区各自独立滚动，互不影响
3. 输入框始终固定在右侧面板底部
4. Tab 切换时内容区滚动位置不丢失
5. 流式生成时顶部 tab 禁用，完成后恢复
6. 在 1280px 和 1440px 宽度下布局不变形
