# Lecture Assistant — 前端重设计规格文档

> 本文档是给 Claude Code 的设计与实施规格说明。请在开始写任何代码前完整阅读。
> 实施过程中以本文档为准，如有冲突优先遵守「安全边界」一节。

---

## 一、核心目标

将现有 Streamlit 原型改造为具有成熟产品感的学习工具。参照风格：Notion（信息密度与排版）、Linear（简洁专业）。

目标不是视觉炫技，而是让用户每天打开都觉得顺手、干净、层次清晰。

---

## 二、技术路线

### 方案：保留 Streamlit + CSS 覆盖层（最小改动路径）

不迁移到 React/FastAPI。所有后端逻辑、session_state、文件结构均不触碰。改动范围严格限制在：

- 页面布局函数（`st.columns`、`st.sidebar` 的结构）
- 渲染函数里的 HTML/CSS（`st.markdown(..., unsafe_allow_html=True)`）
- 独立的 CSS 文件（`assets/styles/main.css`）

### 文件组织

```
lecture-assistant/
  assets/
    styles/
      main.css          ← 新建，所有自定义样式集中在此
      components.css    ← 新建，组件级样式
  app.py                ← 只在顶部加 CSS 注入，其余不动
```

在 `app.py` 的 `st.set_page_config` 之后立即注入：

```python
st.set_page_config(
    page_title="课程助手",
    layout="wide",
    initial_sidebar_state="expanded"
)

with open("assets/styles/main.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
with open("assets/styles/components.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
```

---

## 三、安全边界（必须遵守，不得绕过）

### 3.1 公式渲染保护

`st.latex()` 和 markdown 里的 `$...$` 使用 KaTeX 渲染。KaTeX 有自己的字体（KaTeX_Math、KaTeX_Main 等）和精确的 box-model。以下选择器及其后代绝对不能出现在自定义 CSS 中：

```css
/* 禁止覆盖这些容器 */
.katex          /* KaTeX 根容器 */
.katex-html     /* KaTeX HTML 渲染层 */
.katex-mathml   /* KaTeX MathML 无障碍层 */
mjx-container   /* MathJax 容器（如有） */
```

具体来说，**不能**写：
```css
/* 错误示例 — 会破坏 KaTeX 字体 */
* { font-family: 'Inter', sans-serif; }

/* 错误示例 — 会破坏公式行高 */
p { line-height: 1.7; }
```

**正确做法**：所有文字样式必须加作用域限制：

```css
/* 正确：限定在内容容器内，排除 KaTeX */
.lecture-content p:not(.katex *) {
    line-height: 1.7;
    font-family: 'Inter', -apple-system, 'PingFang SC', sans-serif;
}
```

### 3.2 图表渲染保护

Plotly、Altair、matplotlib 等图表渲染在特定容器里。不能对这些容器设置 `overflow: hidden`、固定 `height`、或修改 `display` 属性：

```css
/* 禁止覆盖这些容器的 display、height、overflow */
[data-testid="stPlotlyChart"]
[data-testid="stVegaLiteChart"]
[data-testid="stArrowVegaLiteChart"]
[data-testid="stImage"]
.js-plotly-plot
.vega-embed
```

如需给图表区域增加视觉包装（如卡片边框），只能在图表容器的**父级**加样式，不能影响图表容器本身。

### 3.3 全局选择器限制

禁止使用无作用域的全局选择器：

```css
/* 以下写法全部禁止 */
* { ... }
body { font-family: ...; }
p { ... }
h1, h2, h3 { ... }
div { ... }
```

所有选择器必须以特定的父级类名开头，或使用 Streamlit 的 `data-testid` 精确定位。

---

## 四、主题兼容方案

### 4.1 核心原则

Streamlit 主题切换时，框架会重新注入以下 CSS 变量到 `:root`：

```
--background-color          主背景色
--secondary-background-color  次级背景色（侧边栏、卡片）
--text-color                主文字色
--primary-color             主题强调色（来自 config.toml）
--font                      字体（由主题配置决定）
```

我们的自定义变量必须**建立在这些变量之上**，而不是用硬编码色值覆盖它们。这样 Streamlit 切换主题时，我们的样式会自动跟随变化。

### 4.2 变量定义规范

```css
/* main.css */

:root {
    /* ===== 直接映射 Streamlit 主题变量 ===== */
    --la-bg-base:    var(--background-color);
    --la-bg-surface: var(--secondary-background-color);
    --la-text:       var(--text-color);
    --la-accent:     var(--primary-color, #4f7cff);

    /* ===== 派生变量（基于透明度，自动适配亮/暗两种主题） ===== */
    /* 透明度叠加方案：在任何背景色上都能形成层次感 */
    --la-bg-elevated:  color-mix(in srgb, var(--background-color) 85%, white 15%);
    --la-border:       rgba(128, 128, 128, 0.15);
    --la-border-focus: rgba(128, 128, 128, 0.4);
    --la-shadow:       0 1px 4px rgba(0, 0, 0, 0.15);

    /* 文字派生 */
    --la-text-secondary: color-mix(in srgb, var(--text-color) 60%, transparent);
    --la-text-muted:     color-mix(in srgb, var(--text-color) 35%, transparent);

    /* 强调色派生 */
    --la-accent-subtle: color-mix(in srgb, var(--primary-color, #4f7cff) 12%, transparent);
    --la-accent-hover:  color-mix(in srgb, var(--primary-color, #4f7cff) 85%, white 15%);

    /* 功能色（透明度叠加方案，亮暗均可见） */
    --la-success:        #34d399;
    --la-success-subtle: rgba(52, 211, 153, 0.1);
    --la-warning:        #fbbf24;

    /* 间距系统（8px 基准） */
    --la-space-1: 4px;
    --la-space-2: 8px;
    --la-space-3: 12px;
    --la-space-4: 16px;
    --la-space-6: 24px;
    --la-space-8: 32px;

    /* 圆角 */
    --la-radius-sm: 4px;
    --la-radius-md: 8px;
    --la-radius-lg: 12px;
}
```

> `color-mix()` 在主流浏览器（Chrome 111+、Firefox 113+、Safari 16.2+）均已支持。
> 如需兼容更旧的浏览器，将派生变量改为在 `[data-theme]` 选择器里分别定义（见 4.3）。

### 4.3 主题差异处理（针对无法用透明度解决的情况）

Streamlit 在 `stApp` 容器或 `body` 上设置主题标识。针对少量需要亮/暗分开处理的样式：

```css
/* 暗色主题特定样式 */
@media (prefers-color-scheme: dark) {
    :root {
        --la-bg-elevated: rgba(255, 255, 255, 0.05);
        --la-border: rgba(255, 255, 255, 0.08);
    }
}

/* 亮色主题特定样式 */
@media (prefers-color-scheme: light) {
    :root {
        --la-bg-elevated: rgba(0, 0, 0, 0.04);
        --la-border: rgba(0, 0, 0, 0.1);
    }
}
```

注意：`prefers-color-scheme` 跟随系统设置，Streamlit 手动切换主题时会与系统设置不同步。如果项目需要精确跟随 Streamlit 手动切换，改用以下选择器（需要测试当前 Streamlit 版本是否生效）：

```css
/* Streamlit 暗色主题 */
[data-theme="dark"] {
    --la-bg-elevated: rgba(255, 255, 255, 0.05);
}

/* Streamlit 亮色主题 */
[data-theme="light"] {
    --la-bg-elevated: rgba(0, 0, 0, 0.04);
}
```

---

## 五、信息架构重设计

### 现有问题

当前导航有三层：侧边栏按钮切换主功能区 > 主区域 tab > 内容子 tab。用户到达目标内容需要点击多次。

### 重设计方案

```
[侧边栏 ~220px]              [主内容区]                [AI 面板 ~340px]
────────────────             ──────────────────        ─────────────────
课程助手                      [当前页面标题]             知识库状态
────────────────             [正文内容]                ─────────────────
信号与系统                                              [对话历史]
  > 复习提纲    <- 当前
    详细笔记                                            [输入框]
    知识结构图
    自测题库
────────────────
+ 新建课程
────────────────
设置 / 资料录入
```

关键改动：
1. 将「已保存资料的 5 个 tab」改为侧边栏直达导航项，一层即达
2. 「资料录入」降级，移至侧边栏底部或独立入口
3. AI 问答面板固定在右侧，切换内容页时不消失、不重置

---

## 六、布局实施（Streamlit 具体代码）

### 6.1 Streamlit 默认元素的覆盖

以下样式隐藏 Streamlit 自带的顶部 header 和底部 footer，不影响任何功能：

```css
/* main.css */
#MainMenu { visibility: hidden; }
footer[data-testid="stFooter"] { visibility: hidden; }
header[data-testid="stHeader"] { visibility: hidden; }

/* 调整主容器内边距 */
[data-testid="stAppViewContainer"] > .main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 1rem;
    max-width: 100%;
}
```

### 6.2 主区域三列布局

```python
# 内容区 + AI 面板
col_main, col_ai = st.columns([2.2, 1], gap="small")

with col_main:
    render_content_area()  # 现有函数，不改内部逻辑

with col_ai:
    render_ai_panel()      # 现有函数，只改样式包装
```

### 6.3 侧边栏导航

```python
with st.sidebar:
    st.markdown(
        '<div class="la-sidebar-logo">课程助手</div>',
        unsafe_allow_html=True
    )
    st.markdown('<hr class="la-divider">', unsafe_allow_html=True)
    st.markdown(
        '<div class="la-sidebar-section-label">信号与系统</div>',
        unsafe_allow_html=True
    )

    pages = [
        ("复习提纲",   "outline"),
        ("详细笔记",   "notes"),
        ("知识结构图", "graph"),
        ("自测题库",   "quiz"),
    ]

    for label, key in pages:
        is_active = st.session_state.get("current_page") == key
        active_class = "la-nav-item la-nav-item--active" if is_active else "la-nav-item"
        # 用 st.button 承载点击事件，CSS 覆盖其外观
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state["current_page"] = key
            st.rerun()
```

对应的按钮样式覆盖（在 CSS 里精确定位侧边栏内的按钮）：

```css
/* components.css */

/* 侧边栏 Logo */
.la-sidebar-logo {
    font-size: 15px;
    font-weight: 600;
    color: var(--la-text);
    padding: var(--la-space-2) var(--la-space-3);
    letter-spacing: -0.01em;
}

/* 分隔线 */
hr.la-divider {
    border: none;
    border-top: 1px solid var(--la-border);
    margin: var(--la-space-2) 0;
}

/* section 标签 */
.la-sidebar-section-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--la-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: var(--la-space-2) var(--la-space-3) var(--la-space-1);
}

/* 侧边栏内的 st.button 覆盖为导航样式 */
[data-testid="stSidebar"] [data-testid="stButton"] > button {
    background: transparent !important;
    border: none !important;
    border-radius: var(--la-radius-md) !important;
    color: var(--la-text-secondary) !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    text-align: left !important;
    padding: 7px 12px !important;
    width: 100% !important;
    box-shadow: none !important;
    transition: background 0.12s ease, color 0.12s ease !important;
}

[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
    background: var(--la-bg-elevated) !important;
    color: var(--la-text) !important;
}

/* active 状态需要通过 session_state 在 Python 侧渲染带 active class 的 HTML，
   因为纯 CSS 无法感知 Streamlit 的 session_state。
   推荐用 st.markdown 渲染 active 项，用 st.button 渲染非 active 项。 */
.la-nav-item--active {
    background: var(--la-accent-subtle) !important;
    color: var(--la-accent) !important;
    font-weight: 500 !important;
    position: relative;
}

.la-nav-item--active::before {
    content: '';
    position: absolute;
    left: 0;
    top: 4px;
    bottom: 4px;
    width: 3px;
    background: var(--la-accent);
    border-radius: 0 2px 2px 0;
}
```

---

## 七、核心组件样式

### 7.1 内容卡片（包裹现有 st.markdown 内容区域）

```css
/* 所有样式限定在 la-content-card 作用域内 */
.la-content-card {
    background: var(--la-bg-surface);
    border: 1px solid var(--la-border);
    border-radius: var(--la-radius-lg);
    padding: var(--la-space-6);
    margin-bottom: var(--la-space-4);
}

/* 限定在卡片内的标题，不影响全局 */
.la-content-card h1,
.la-content-card h2,
.la-content-card h3 {
    color: var(--la-text);
    font-weight: 600;
    letter-spacing: -0.01em;
    /* 不设置 font-family，沿用 Streamlit 主题的字体配置 */
}

.la-content-card h2 {
    font-size: 18px;
    padding-bottom: var(--la-space-4);
    border-bottom: 1px solid var(--la-border);
    margin-bottom: var(--la-space-6);
}

/* 限定在卡片内的段落，排除 KaTeX 子元素 */
.la-content-card p:not([class*="katex"]) {
    color: var(--la-text);
    line-height: 1.75;
    font-size: 14px;
}

/* 限定在卡片内的列表 */
.la-content-card li:not([class*="katex"]) {
    line-height: 1.7;
    font-size: 14px;
    color: var(--la-text);
}
```

### 7.2 AI 对话面板

```css
.la-chat-panel {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--la-border);
    border-radius: var(--la-radius-lg);
    overflow: hidden;
    background: var(--la-bg-surface);
}

.la-chat-header {
    padding: var(--la-space-3) var(--la-space-4);
    border-bottom: 1px solid var(--la-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 13px;
    font-weight: 600;
    color: var(--la-text);
}

/* 知识库状态标签 */
.la-kb-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    background: var(--la-success-subtle);
    border: 1px solid rgba(52, 211, 153, 0.25);
    border-radius: 20px;
    color: var(--la-success);
    font-size: 11px;
    font-weight: 500;
}

.la-chat-messages {
    flex: 1;
    padding: var(--la-space-4);
    display: flex;
    flex-direction: column;
    gap: var(--la-space-3);
    overflow-y: auto;
}

.la-msg-user {
    align-self: flex-end;
    background: var(--la-accent);
    color: #ffffff;
    padding: 8px 14px;
    border-radius: 12px 12px 2px 12px;
    max-width: 85%;
    font-size: 13px;
    line-height: 1.6;
}

.la-msg-ai {
    align-self: flex-start;
    background: var(--la-bg-elevated);
    color: var(--la-text);
    padding: 10px 14px;
    border-radius: 12px 12px 12px 2px;
    max-width: 88%;
    font-size: 13px;
    line-height: 1.75;
}

.la-chat-input-wrapper {
    padding: var(--la-space-3) var(--la-space-4);
    border-top: 1px solid var(--la-border);
}

/* 覆盖 Streamlit 的 text_input / text_area 样式，限定在聊天面板内 */
.la-chat-input-wrapper [data-testid="stTextInput"] input,
.la-chat-input-wrapper [data-testid="stTextArea"] textarea {
    background: var(--la-bg-base) !important;
    border: 1px solid var(--la-border) !important;
    border-radius: var(--la-radius-md) !important;
    color: var(--la-text) !important;
    font-size: 13px !important;
}

.la-chat-input-wrapper [data-testid="stTextInput"] input:focus,
.la-chat-input-wrapper [data-testid="stTextArea"] textarea:focus {
    border-color: var(--la-accent) !important;
    box-shadow: 0 0 0 3px var(--la-accent-subtle) !important;
}
```

### 7.3 题目卡片

```css
.la-question-card {
    background: var(--la-bg-surface);
    border: 1px solid var(--la-border);
    border-radius: var(--la-radius-lg);
    padding: 20px var(--la-space-6);
    margin-bottom: var(--la-space-3);
    transition: border-color 0.15s ease;
}

.la-question-card:hover {
    border-color: var(--la-border-focus);
}

.la-question-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--la-accent);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: var(--la-space-2);
}

/* 题目内的公式不受影响（.katex 不在覆盖范围内） */
.la-question-card p:not([class*="katex"]) {
    font-size: 14px;
    line-height: 1.75;
    color: var(--la-text);
}

.la-answer-block {
    margin-top: var(--la-space-4);
    padding: var(--la-space-3) var(--la-space-4);
    background: var(--la-success-subtle);
    border-left: 3px solid var(--la-success);
    border-radius: 0 var(--la-radius-sm) var(--la-radius-sm) 0;
    font-size: 13px;
    color: var(--la-text-secondary);
    line-height: 1.7;
}
```

---

## 八、图表和公式的包装方式

当需要在图表或公式周围加视觉卡片时，只能包装父容器，不能改图表容器本身：

```python
# 正确做法：包装父级
st.markdown('<div class="la-content-card">', unsafe_allow_html=True)
st.latex(r"\int_{-\infty}^{\infty} x(t)\delta(t-t_0)dt = x(t_0)")  # 不受影响
st.plotly_chart(fig)   # 不受影响
st.markdown('</div>', unsafe_allow_html=True)
```

```css
/* 只给父容器加样式，图表容器本身不动 */
.la-content-card {
    background: var(--la-bg-surface);
    border: 1px solid var(--la-border);
    border-radius: var(--la-radius-lg);
    padding: var(--la-space-6);
    /* 不能设置 overflow: hidden，否则 Plotly tooltip 会被裁剪 */
}
```

---

## 九、实施优先级

### Phase 1（视觉骨架，优先完成）

- [ ] 新建 `assets/styles/main.css`，写入变量系统（第四节）和 Streamlit 默认元素覆盖
- [ ] 新建 `assets/styles/components.css`，写入侧边栏导航样式
- [ ] 修改侧边栏导航结构：5 个 tab 改为直达导航项
- [ ] 主内容区和 AI 面板的基础排版（字号、间距、卡片边框）

### Phase 2（细节完善）

- [ ] 对话面板的消息气泡、输入框样式
- [ ] 题目卡片的答案展开/折叠交互
- [ ] 加载状态（AI 生成时的占位动画）
- [ ] 确认图表（Plotly/Altair）和公式（KaTeX）在亮/暗两个主题下均正常

### Phase 3（可选）

- [ ] 响应式：侧边栏在窄屏自动折叠
- [ ] 键盘导航支持

---

## 十、验收标准

1. **主题切换**：Streamlit 设置里切换亮/暗主题，所有自定义样式跟随变化，无色彩残留
2. **公式正常**：`st.latex()` 渲染的数学公式字体、大小、对齐不变
3. **图表正常**：Plotly/Altair 图表可正常渲染，tooltip 不被裁剪
4. **导航层级**：从侧边栏一次点击到达任意内容页
5. **AI 面板常驻**：切换内容页时对话历史不重置
6. **无裸露原生样式**：不出现 Streamlit 默认的按钮、tab 原生样式

---

*文档版本：v1.1 | 更新：移除 emoji、增加主题兼容方案、增加公式/图表安全边界*
