"""Editorial Academic 主题 — 自定义 CSS 注入。"""

import streamlit as st


def inject_theme_css() -> None:
    """注入轻量自定义 CSS，仅覆盖组件级样式。"""
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
        border-top: 1px solid #E8E5DF;
        margin: 1rem 0;
    }

    /* ---- 卡片容器 (st.expander, div[data-testid="stExpander"]) ---- */
    [data-testid="stExpander"] {
        border: 1px solid #E8E5DF;
        border-radius: 4px;
        background: #FFFFFF;
    }

    /* ---- 聊天消息气泡 ---- */
    [data-testid="stChatMessage"] {
        border-radius: 4px;
        padding: 0.75rem 1rem;
    }

    /* ---- 代码块 ---- */
    code {
        background: #F4F3EF;
        border-radius: 3px;
        padding: 0.15em 0.4em;
    }
    pre code {
        background: #F4F3EF;
        border: 1px solid #E8E5DF;
        border-radius: 4px;
        padding: 1rem;
    }

    /* ---- 标签/徽章 ---- */
    .material-type-tag {
        display: inline-block;
        font-size: 0.8rem;
        border-radius: 3px;
        padding: 2px 8px;
        color: #78766F;
        background: #F2F0EB;
    }
    .material-type-tag.active {
        color: #2C3E5C;
        background: #E8E5DF;
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
    .status-pending { color: #B0AEA6; }
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
    /* 标签页按钮 sticky */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        position: sticky;
        top: 0;
        z-index: 10;
        background: #FFFFFF;
        padding-top: 0.25rem;
    }
    /* 聊天输入框 sticky */
    .st-key-workspace-input {
        position: sticky !important;
        bottom: 0 !important;
        background: #F9F8F6;
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
