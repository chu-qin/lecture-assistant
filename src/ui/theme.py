"""Editorial Academic 主题 — 自定义 CSS 注入。"""

import streamlit as st


def inject_theme_css() -> None:
    """注入轻量自定义 CSS，仅覆盖组件级样式。

    所有颜色使用 rgba 半透明值或继承主题，避免硬编码破坏深色模式。
    """
    st.markdown(
        """<style>
    /* ---- 隐藏 Streamlit 原生页面导航 ---- */
    [data-testid="stSidebarNav"] {
        display: none;
    }

    /* ---- 缩减顶部空白 ---- */
    [data-testid="stAppViewContainer"] > .main .block-container {
        padding-top: 1rem !important;
    }
    [data-testid="stSidebarContent"] {
        padding-top: 1rem !important;
    }

    /* ---- 分割线 ---- */
    hr {
        border: none;
        border-top: 1px solid rgba(128, 128, 128, 0.2);
        margin: 1rem 0;
    }

    /* ---- 卡片容器 ---- */
    [data-testid="stExpander"] {
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-radius: 4px;
    }

    /* ---- 聊天消息气泡 ---- */
    [data-testid="stChatMessage"] {
        border-radius: 4px;
        padding: 0.75rem 1rem;
    }

    /* ---- 代码块 ---- */
    code {
        background: rgba(128, 128, 128, 0.1);
        border-radius: 3px;
        padding: 0.15em 0.4em;
    }
    pre code {
        background: rgba(128, 128, 128, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-radius: 4px;
        padding: 1rem;
    }

    /* ---- 标签/徽章 ---- */
    .material-type-tag {
        display: inline-block;
        font-size: 0.8rem;
        border-radius: 3px;
        padding: 2px 8px;
        background: rgba(128, 128, 128, 0.12);
    }
    .material-type-tag.active {
        background: rgba(128, 128, 128, 0.22);
    }

    /* ---- 侧边栏微调 ---- */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        border: none;
        background: transparent;
    }
    [data-testid="stSidebar"] .stButton button {
        text-align: left;
        font-size: 0.9rem;
    }

    /* ---- 状态标记 ---- */
    .status-ready { color: #5B8266; }
    .status-pending { color: #8B8B8B; }
    .status-warning { color: #C4945C; }
    .status-error { color: #C4665F; }

    /* ---- 左右分栏独立滚动 ---- */
    [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:has(.st-key-workspace-right)) {
        align-items: flex-start !important;
    }
    /* 左栏独立滚动 */
    [data-testid="stColumn"]:has(.st-key-workspace-left) {
        position: sticky;
        top: 2.5rem;
        align-self: flex-start;
        max-height: calc(100vh - 2.5rem - 1.5rem);
        overflow-y: auto;
    }
    /* 右栏独立滚动 */
    [data-testid="stColumn"]:has(.st-key-workspace-right) {
        position: sticky;
        top: 2.5rem;
        align-self: flex-start;
        max-height: calc(100vh - 2.5rem - 1.5rem);
        overflow-y: auto;
        z-index: 1;
        box-shadow: -1px 0 4px rgba(0, 0, 0, 0.04);
    }
    /* 标签页按钮 sticky（背景用半透明保证 sticky 时内容不穿透） */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        position: sticky;
        top: 0;
        z-index: 10;
        background: rgba(128, 128, 128, 0.05);
        backdrop-filter: blur(6px);
        padding-top: 0.25rem;
    }
    /* 聊天输入框 sticky */
    .st-key-workspace-input {
        position: sticky !important;
        bottom: 0 !important;
        background: rgba(128, 128, 128, 0.03);
        backdrop-filter: blur(6px);
        z-index: 5;
        padding-top: 0.5rem;
        padding-bottom: 0.25rem;
    }
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"]:has(
            [data-testid="stColumn"]:has(.st-key-workspace-right)
        ) {
            align-items: stretch !important;
        }
        [data-testid="stColumn"]:has(.st-key-workspace-left),
        [data-testid="stColumn"]:has(.st-key-workspace-right) {
            position: static;
            max-height: none;
            overflow-y: visible;
            box-shadow: none;
        }
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            position: static;
        }
        .st-key-workspace-input {
            position: static !important;
        }
        /* 平板及以下：侧边栏按钮增大触控区域 */
        [data-testid="stSidebar"] .stButton button {
            min-height: 40px;
            font-size: 0.95rem;
        }
    }

    @media (max-width: 480px) {
        /* 手机端：强制列纵向堆叠 */
        [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 0.5rem !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width: 100% !important;
            flex: none !important;
        }
        /* 触控目标最小 44px (iOS/Android 标准) */
        button, .stButton button, [data-testid="baseButton-secondary"] {
            min-height: 44px;
            font-size: 0.95rem;
        }
        input, textarea, [data-testid="stTextInput"] input {
            min-height: 44px;
            font-size: 16px;  /* 16px 防止 iOS 缩放 */
        }
        /* 标题缩小 */
        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.15rem !important; }
        h3 { font-size: 1.05rem !important; }
        /* 卡片和展开器内边距收紧 */
        [data-testid="stExpander"] {
            padding: 0.35rem 0.5rem;
        }
        /* 文件上传器内边距缩小 */
        [data-testid="stFileUploader"] {
            padding: 0.5rem;
        }
    }
    </style>""",
        unsafe_allow_html=True,
    )


def inject_workspace_layout() -> None:
    """注入 JS：右栏自动滚动到底部（布局由 CSS sticky 控制）。"""
    st.markdown(
        """<script>
    (function() {
        var SCROLL_THRESHOLD = 50;

        function getRightColumn() {
            return document.querySelector(
                '[data-testid="stColumn"]:has(.st-key-workspace-right)'
            );
        }

        function isNearBottom(col) {
            return (col.scrollHeight - col.scrollTop - col.clientHeight) < SCROLL_THRESHOLD;
        }

        function scrollToBottom(col, force) {
            if (col && (force || isNearBottom(col))) {
                col.scrollTop = col.scrollHeight;
            }
        }

        function setupScrollSync(col) {
            scrollToBottom(col, true);
            var debounceTimer = null;
            function debouncedScroll() {
                if (debounceTimer) clearTimeout(debounceTimer);
                debounceTimer = setTimeout(function() {
                    scrollToBottom(col, false);
                }, 80);
            }
            var observer = new MutationObserver(function(mutations) {
                var hasRelevantChange = false;
                for (var i = 0; i < mutations.length; i++) {
                    var m = mutations[i];
                    if (m.type === 'childList' && m.addedNodes.length > 0) {
                        hasRelevantChange = true; break;
                    }
                    if (m.type === 'characterData') {
                        hasRelevantChange = true; break;
                    }
                }
                if (hasRelevantChange) {
                    debouncedScroll();
                }
            });
            observer.observe(col, {
                childList: true,
                subtree: true,
                characterData: true
            });
        }

        function init() {
            var col = getRightColumn();
            if (col) {
                setupScrollSync(col);
            }
        }

        if (typeof requestAnimationFrame !== 'undefined') {
            requestAnimationFrame(function() {
                requestAnimationFrame(init);
            });
        } else {
            setTimeout(init, 150);
        }
    })();
    </script>""",
        unsafe_allow_html=True,
    )


def inject_mermaid() -> None:
    """注入 Mermaid.js，将代码块中的 Mermaid 语法渲染为图表。

    LLM 在生成"知识结构图"时经常输出 graph TD / flowchart 等 Mermaid 语法，
    Streamlit 原生 st.markdown 不支持渲染，需要通过 JS 在客户端转换。

    注意：不能用 <script src> 标签（React innerHTML 不执行），
    必须用 document.createElement('script') 动态加载。
    """
    st.markdown(
        """<script>
(function() {
    // 动态加载 Mermaid.js（避免 React innerHTML 不执行外部脚本的问题）
    var mermaidScript = document.createElement('script');
    mermaidScript.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js';
    mermaidScript.onload = initMermaid;
    document.head.appendChild(mermaidScript);

    function isMermaidDiagram(text) {
        var t = text.trim();
        var kw = '^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|'
            + 'erDiagram|gantt|pie|mindmap|timeline|journey|quadrantChart|'
            + 'sankey-beta|xychart-beta|block-beta|packet-beta|'
            + 'requirementDiagram|C4Context|C4Container|C4Component|'
            + 'C4Dynamic|C4Deployment|gitGraph)\\b';
        return new RegExp(kw).test(t);
    }

    function detectTheme() {
        var bg = getComputedStyle(document.body).backgroundColor;
        var match = bg.match(/[\\d.]+/g);
        if (match && match.length >= 3) {
            var r = parseFloat(match[0]), g = parseFloat(match[1]), b = parseFloat(match[2]);
            return (r * 0.299 + g * 0.587 + b * 0.114) > 128 ? 'default' : 'dark';
        }
        return 'default';
    }

    function renderMermaidBlocks() {
        var blocks = document.querySelectorAll('pre code');
        var pending = [];
        for (var i = 0; i < blocks.length; i++) {
            var code = blocks[i];
            if (code.dataset.mermaidChecked) continue;
            code.dataset.mermaidChecked = '1';
            var text = code.textContent || '';
            if (isMermaidDiagram(text)) {
                var pre = code.parentElement;
                var div = document.createElement('div');
                div.className = 'mermaid';
                div.textContent = text;
                div.style.margin = '1rem 0';
                div.style.overflowX = 'auto';
                pre.replaceWith(div);
                pending.push(div);
            }
        }
        if (pending.length > 0) {
            mermaid.initialize({ startOnLoad: false, theme: detectTheme() });
            mermaid.run({ nodes: pending }).catch(function(err) {
                console.warn('Mermaid render failed, keeping code blocks');
            });
        }
    }

    function initMermaid() {
        setTimeout(renderMermaidBlocks, 200);
        var observer = new MutationObserver(function() {
            setTimeout(renderMermaidBlocks, 200);
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }
})();
</script>""",
        unsafe_allow_html=True,
    )
