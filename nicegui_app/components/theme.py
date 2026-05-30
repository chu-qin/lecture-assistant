"""NiceGUI 主题注入 — MathJax LaTeX + Mermaid + 自定义 CSS。

NiceGUI 原生支持 Mermaid（extras=['mermaid']），只需通过 add_head_html
注入 MathJax 处理 LaTeX 公式。
"""

from nicegui import ui


def inject_mathjax() -> None:
    """加载 MathJax 3，通过 MutationObserver 自动重新渲染动态内容。"""
    ui.add_body_html(
        """<script>
(function() {
    // 配置 MathJax
    window.MathJax = {
        tex: {
            inlineMath: [['$', '$'], ['\\(', '\\)']],
            displayMath: [['$$', '$$'], ['\\[', '\\]']],
        },
        options: {
            ignoreHtmlClass: 'no-mathjax',
        },
    };

    // 动态加载 MathJax CDN
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js';
    script.onload = function() {
        var pending = null;

        function typesetAll() {
            if (window.MathJax && window.MathJax.typesetPromise) {
                var elements = document.querySelectorAll('.nicegui-markdown');
                elements.forEach(function(el) {
                    if (window.MathJax.typesetClear) {
                        MathJax.typesetClear([el]);
                    }
                    window.MathJax.typesetPromise([el]).catch(function(){});
                });
            }
        }

        function debouncedTypeset() {
            if (pending) clearTimeout(pending);
            pending = setTimeout(typesetAll, 200);
        }

        // 首次渲染
        setTimeout(typesetAll, 0);

        // 监听后续变化
        var observer = new MutationObserver(function(mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var target = mutations[i].target;
                // 检查目标元素本身是否在 .nicegui-markdown 内
                if (target.nodeType === 1
                    && target.closest
                    && target.closest('.nicegui-markdown')) {
                    debouncedTypeset();
                    break;
                }
                // 检查新增节点（.nicegui-markdown 被添加到 DOM 时，target 是其父节点）
                var added = mutations[i].addedNodes;
                for (var j = 0; j < added.length; j++) {
                    var node = added[j];
                    if (node.nodeType === 1) {
                        if ((node.classList && node.classList.contains('nicegui-markdown')) ||
                            (node.querySelector && node.querySelector('.nicegui-markdown'))) {
                            debouncedTypeset();
                            break;
                        }
                    }
                }
            }
        });
        observer.observe(document.body, {childList: true, subtree: true});
    };
    document.head.appendChild(script);
})();
</script>""",
        shared=True,
    )


def inject_custom_css() -> None:
    """注入自定义 CSS（暗色模式兼容，使用 rgba 半透明色）。"""
    ui.add_body_html(
        """<style>
/* ---- 分割线 ---- */
hr {
    border: none;
    border-top: 1px solid rgba(128, 128, 128, 0.2);
    margin: 1rem 0;
}

/* ---- 卡片容器 ---- */
.review-card {
    border: 1px solid rgba(128, 128, 128, 0.15);
    border-radius: 4px;
    padding: 1rem;
    margin: 0.5rem 0;
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

/* ---- 状态标记 ---- */
.status-ready { color: #5B8266; }
.status-pending { color: #8B8B8B; }
.status-warning { color: #C4945C; }
.status-error { color: #C4665F; }

/* ---- 移动端响应式 ---- */
@media (max-width: 480px) {
    button, .q-btn {
        min-height: 44px;
        font-size: 0.95rem;
    }
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.15rem !important; }
    h3 { font-size: 1.05rem !important; }
}
</style>""",
        shared=True,
    )


def inject_theme() -> None:
    """注入所有主题资源。"""
    inject_mathjax()
    inject_custom_css()
