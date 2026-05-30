# 复习与问答页面迁移方案

## 背景与目标

`pages/2_复习与问答.py` 存在两个无法在 Streamlit 内根本解决的交互问题：

1. **聊天输入框不固定**：对话框跟在最后一条消息后面，用户每次提问都要向下滚动
2. **切换资料要回到顶部**：复习提纲/笔记/结构图/题库的切换入口在页面顶部，
   看完内容后切换另一份资料，再切回来，页面滚动位置全部丢失

这两个问题是 Streamlit 的 DOM 结构限制，CSS 无法解决。

**迁移范围**：只迁移这一个页面。
- `pages/1_资料录入.py` 和 `run.py` 不动
- `src/` 下所有后端模块一行不动
- 新增 `src/api/review_api.py`（FastAPI 路由）和 `assets/review.html`（新前端）

---

## 第一步：添加 FastAPI 路由

新建 `src/api/review_api.py`，从现有模块中调用逻辑，暴露以下接口。
接口设计以"最小改动现有代码"为原则，不重构任何 `src/` 模块。

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import json

# 复用现有模块，不修改它们
from src.course_manager import CourseManager
from src.llm.factory import get_llm
from src.knowledge.chroma_store import ChromaStore
from src.config import load_config

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# GET /api/courses
# 返回课程列表和每个课程的已生成资料状态
# 复用 CourseManager 的现有方法

# GET /api/courses/{course_id}/materials
# 返回指定课程的已生成资料（提纲/笔记/结构图/题库）
# 从 CourseManager 读取已保存的 Markdown 内容

# POST /api/courses/{course_id}/generate
# body: {"material_type": "outline"|"notes"|"graph"|"quiz"}
# 调用现有生成逻辑，SSE 流式返回生成进度和内容

# POST /api/courses/{course_id}/chat
# body: {"message": "用户问题", "history": [...]}
# 调用现有 RAG 问答逻辑，SSE 流式返回回答
```

在 `run.py` 中挂载 FastAPI：

```python
# run.py 顶部追加（不删除现有 streamlit 代码）
from src.api.review_api import app as fastapi_app
import threading
import uvicorn

def start_api():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8502, log_level="error")

# 在 Streamlit 启动时同时启动 API
threading.Thread(target=start_api, daemon=True).start()
```

这样：
- Streamlit 在 8501 端口（保留资料录入页面）
- FastAPI 在 8502 端口（新的复习问答页面）

---

## 第二步：HTML 前端

新建 `assets/review.html`。这是一个单文件页面，用原生 HTML/CSS/JS 实现，
不引入任何构建工具，所有依赖通过 CDN 加载。

### 页面布局结构

```
┌──────────────────────────────────────────────────┐
│  [课程名]  提纲  笔记  结构图  题库              │  <- 顶部导航栏，fixed
├──────────────────────┬───────────────────────────┤
│                      │  智能问答                  │
│   内容区             │  ──────────────────────   │
│   （独立滚动）       │  对话历史区                │
│                      │  （独立滚动）              │
│                      │  ──────────────────────   │
│                      │  [输入框]  [发送]          │  <- 固定在右侧底部
└──────────────────────┴───────────────────────────┘
```

关键 CSS 结构（解决两个核心问题）：

```css
/* 顶部导航固定 */
.top-nav {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 48px;
    z-index: 100;
}

/* 主区域布局 */
.main-layout {
    display: flex;
    height: 100vh;
    padding-top: 48px; /* 为顶部导航留空间 */
}

/* 内容区：独立滚动 */
.content-area {
    flex: 1;
    overflow-y: auto;  /* 关键：内容区独立滚动 */
    padding: 24px 32px;
}

/* 右侧聊天面板：flex 列布局 */
.chat-panel {
    width: 360px;
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--border);
}

/* 对话历史：占满剩余空间，独立滚动 */
.chat-messages {
    flex: 1;
    overflow-y: auto;  /* 关键：对话区独立滚动 */
    padding: 16px;
}

/* 输入框：固定在底部 */
.chat-input-area {
    flex-shrink: 0;    /* 关键：不被压缩 */
    padding: 12px 16px;
    border-top: 1px solid var(--border);
}
```

### 渲染需求

内容区需要渲染 Markdown + LaTeX 公式 + Mermaid 图表，与现有 Streamlit 页面一致。
通过 CDN 引入（无需安装）：

```html
<!-- Markdown 渲染 -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

<!-- KaTeX 公式渲染（与现有 Streamlit 页面一致） -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex/dist/contrib/auto-render.min.js"></script>

<!-- Mermaid 图表渲染（与现有 Streamlit 页面一致） -->
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
```

渲染顺序：Markdown → KaTeX → Mermaid（与 Streamlit 页面的现有逻辑保持一致）。

### SSE 流式接收

```javascript
async function sendMessage(message) {
    const response = await fetch('/api/courses/${courseId}/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message, history: chatHistory})
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    // 在对话区插入一个空的 AI 消息气泡，边收边填充
    const msgEl = appendAiMessage('');

    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        // 更新气泡内容并重新渲染公式
        msgEl.innerHTML = renderContent(buffer);
        renderKatex(msgEl);
        // 保持对话区滚动到底部
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    }
    await renderMermaid(msgEl);
}
```

### 导航切换（不丢失内容区滚动位置）

```javascript
// 每个 tab 对应的内容区滚动位置独立保存
const scrollPositions = {outline: 0, notes: 0, graph: 0, quiz: 0};
let currentTab = 'outline';

function switchTab(tabName) {
    // 保存当前 tab 的滚动位置
    scrollPositions[currentTab] = contentAreaEl.scrollTop;

    // 切换
    currentTab = tabName;
    loadMaterial(tabName);  // 从 API 获取内容

    // 恢复目标 tab 的滚动位置（如果已访问过）
    contentAreaEl.scrollTop = scrollPositions[tabName] || 0;
}
```

---

## 第三步：在 Streamlit 复习页面添加跳转入口

修改 `pages/2_复习与问答.py`，在页面顶部加一个跳转链接，
让用户可以选择用旧界面还是新界面：

```python
st.markdown(
    '<a href="http://localhost:8502/assets/review.html" target="_blank">'
    '在新界面中打开（推荐）</a>',
    unsafe_allow_html=True
)
```

迁移完成并验证稳定后，可以把这个页面整体替换为跳转页。

---

## 实施顺序

1. 先写 `src/api/review_api.py`，把现有功能接口化，在命令行测试接口返回值
2. 写 `assets/review.html`，先用静态数据调通布局和渲染（公式、Mermaid）
3. 接入 SSE 流式接口，测试聊天功能
4. 接入资料生成接口，测试四种资料的切换
5. 在 `run.py` 中启动 FastAPI，端到端联调

---

## 不要碰的部分

- `src/` 下所有模块
- `pages/1_资料录入.py`
- `run.py` 的 Streamlit 部分（只追加 FastAPI 启动代码）
- `assets/styles/` 的现有 CSS（新 HTML 页面有自己的样式）
- 测试文件

---

## 验收标准

1. 聊天输入框在右侧面板底部固定，无论对话多长都不需要滚动
2. 切换资料 tab 后再切回来，内容区滚动位置不丢失
3. LaTeX 公式和 Mermaid 图表渲染正常（对照现有 Streamlit 页面）
4. 流式输出时公式可以在最终收到完整内容后正确渲染（不要每个 token 都重渲染）
5. 资料录入页面（8501）不受任何影响
