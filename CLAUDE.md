# CLAUDE.md — Lecture Assistant

课堂录音转文字 + 课件解析 + AI 复习资料生成 + 智能问答，一站式 Web 应用。

> 总代码量 ~3100 行 Python | 所有核心模块已完成 | 169 个单元测试

## 当前进度（截至 2026-05-29）

**当前阶段**：全部已知 Bug 已修复。Mermaid 11.x 兼容 + LaTeX/MathJax 3 渲染正常。169 测试通过。

已完成里程碑：
- P0-P6: 安全/日志/依赖修复、pyproject.toml/ruff/pytest 配置、多 LLM Provider、i18n、EPUB、GitHub 发布
- **NiceGUI 迁移 (6 步全部完成)**：Streamlit → NiceGUI 前端框架迁移
  - Step 0: `src/i18n/__init__.py` 解耦 Streamlit（模块级变量 + import bridge）
  - Step 1-2: 骨架搭建 + 复习问答页面（async 流式 LLM、Mermaid、MathJax）
  - Step 3-4: 资料录入页面 + 首页
  - Step 5-6: 删除旧 Streamlit 代码（run.py, pages/, .streamlit/, src/ui/）+ 回归测试
  - **BugFix (2026-05-28)**: `app.storage.tab` 需 WebSocket 连接 → 页面函数改为 `async def` + `await ui.context.client.connected()`
  - **BugFix (2026-05-29)**: Streamlit 警告日志 → 移除 i18n 中的 Streamlit bridge 代码
  - **BugFix (2026-05-29)**: 进入复习与问答页面自动弹出下载框 → `ui.download.content()` 是函数调用，返回 None，不能作为按钮元素 → 包在 `ui.button(on_click=...)` 中
  - **BugFix (2026-05-29)**: 子页面侧边栏消失 → `render_sidebar()` 需在每个页面函数中调用（review_qa + material_input）
  - **BugFix (2026-05-29)**: Mermaid "Syntax error in text" (v11.15.0) → Mermaid 11 移除了 `graph` 关键字 → `_normalize_mermaid()` 函数自动将 `graph TD/LR/TB` 替换为 `flowchart TD/LR/TB`
- 测试: 169 passed、ruff 零错误

## 已修复 Bug（2026-05-29）

### Mermaid 11.x 子图语法修复

**问题**：LLM 生成的 Mermaid 使用 `graph TD` + `subgraph "标题"` + 体内 `direction LR`，Mermaid 11.x 均不支持。

**修复**（`nicegui_app/pages/review_qa.py` `_normalize_mermaid()`）：
1. `graph` → `flowchart`（已有）
2. Unicode 花引号 `""` → `[""]`（新增 — LLM 常生成 `""` 而非 `""`）
3. 体内 `direction LR` → 声明行内联 `subgraph LR ["title"]`（Mermaid 11 不支持体内 direction，必须写为 `subgraph direction ["title"]`）

Playwright 验证：Mermaid 渲染为有效 SVG（763x577 viewBox），零控制台错误。

### MathJax 3 LaTeX 不渲染修复

**问题**：`inject_theme()` 在页面函数内调用（`@ui.page` 装饰的函数中），`add_head_html`/`add_body_html` 此时 HTML 已发送到浏览器，脚本通过 WebSocket 动态注入。浏览器不执行通过 `innerHTML` 添加的 `<script>` 标签（安全策略），导致 MathJax 配置和 CDN 脚本从未执行。

**修复**（`nicegui_app/main.py` + `nicegui_app/components/theme.py`）：
1. `inject_theme()` 在模块顶层（`ui.run()` 之前）调用，确保脚本包含在初始 HTML 响应中
2. `add_body_html()` 使用 `shared=True` 参数（NiceGUI 要求在页面上下文之外调用时必须传此参数）
3. MathJax CDN 改为动态加载（`document.createElement('script')`），避免 `async` 属性导致的竞态
4. `typesetAll()` 中添加 `MathJax.typesetClear([el])` 清除内部状态后再渲染

Playwright 验证：186 个 `mjx-container` 渲染元素，`window.MathJax.typesetPromise` 可用，零控制台错误。

### 当前目录结构

```
nicegui_app/            # NiceGUI 前端（唯一前端）
├── main.py             # 入口，ui.run() + 首页路由
├── state.py            # app.storage 状态管理（user 持久化 + tab 内存）
├── components/
│   ├── sidebar.py      # left_drawer 侧边栏（课程列表 + 导航 + 语言切换）
│   └── theme.py        # MathJax 3 LaTeX + 自定义 CSS
└── pages/
    ├── review_qa.py    # 复习与问答（异步流式 LLM + Mermaid + 聊天）
    └── material_input.py  # 资料录入（ASR + 课件解析 + EPUB 导入）

src/                    # 业务逻辑（零改动）
tests/                  # 169 个单元测试
prompts/                # LLM 提示词模板（zh/ + en/）
tools/                  # ffmpeg 绿色版、LibreOffice 便携版
data/courses/           # 用户数据，按课程分子目录
```

## 技术栈
- Python 3.12+, Windows 10+, **NiceGUI 3.12.1** (Vue/Quasar)
- FunASR SenseVoiceSmall (ASR) | DeepSeek API (LLM, OpenAI 兼容)
- ChromaDB + BAAI/bge-small-zh-v1.5 (RAG 语义检索, 512 维, cosine 距离)
- python-pptx + olefile + magic-pdf (文档解析)
- 所有模型缓存在 `data/model_cache/`，删除目录即卸载

## 目录职责
```
src/asr/         # 语音识别：BaseASR → FunASRSenseVoiceASR
src/parser/      # 文档解析：ppt_extractor (PPT/PPTX) + mineru_parser (PDF) + epub_parser (EPUB)
src/llm/         # LLM 调用：deepseek_llm (OpenAI 兼容接口)
src/knowledge/   # RAG：chunker (语义分块) + embedder (BGE) + chroma_store
src/merger/      # 课件+录音内容合并
src/i18n/        # 多语言：zh.json + en.json + t() 函数
nicegui_app/     # NiceGUI 前端（main.py, state.py, pages/, components/）
prompts/         # LLM 提示词模板，按语言分子目录 (zh/ + en/)
tools/           # ffmpeg 绿色版、LibreOffice 便携版
data/courses/    # 用户数据，按课程分子目录
```

## 编码约定（必须遵守）

### NiceGUI 页面 — 关键模板
```python
@ui.page("/path/{param}")
async def page_func(param: str):                # 必须是 async def
    """页面说明。"""
    await ui.context.client.connected()          # 必须在最前面！否则 app.storage.tab 报 RuntimeError
    inject_theme()
    render_sidebar()
    # ... 页面逻辑
```

- 每个页面用 `@ui.page('/path/{param}')` 装饰器注册路由
- **页面函数必须是 `async def`，第一行必须 `await ui.context.client.connected()`**
  - 原因：`app.storage.tab` 需要浏览器 WebSocket 连接就绪，`client.connected()` 阻塞等待握手完成
  - 这是 NiceGUI 3.12.1 的正确 API，**不是** `ui.client_connected()`（该 API 不存在）
- 页面函数开头调用 `inject_theme()` + `render_sidebar()`
- 用 `get_cache(key)` / `set_cache(key, value)` 读写内存状态（tab 级，重对象）
- 用 `get_user(key)` / `set_user(key, value)` 读写持久化状态（user 级，轻量键，跨页面/重启存活）
- 阻塞调用（LLM, ASR）用 `await asyncio.to_thread(fn, *args)` 包装，避免冻结事件循环
- 流式 LLM 输出通过 `_stream_llm_to_element()` 辅助函数实现（asyncio.Queue + ThreadPoolExecutor）

### 架构模式
- **每个模块必有 `base.py`**：定义抽象基类 + dataclass 数据契约 + 模块专属异常类
- **具体实现在独立文件**：如 `funasr_asr.py`、`deepseek_llm.py`，接受对应 Config dataclass
- **抽象基类只声明方法签名，不实现**

### 配置系统
- 所有配置是 `@dataclass`，字段有默认值，定义在 `src/config.py`
- `AppConfig` 是顶层容器，包含 `ASRConfig`, `LLMConfig` 等子配置
- 用 `get_config()` 获取全局单例，不要重复读取 YAML
- 支持 `${ENV_VAR:default}` 环境变量引用语法

### 通用约定
- 文件路径用 `pathlib.Path`，不要用 `os.path` 或字符串拼接
- 日志用 `logging.getLogger(__name__)`
- 保存 TXT 给用户下载用 `utf-8-sig`（Windows BOM），保存 JSON 用 `utf-8`
- 类型标注必须有：函数参数和返回值
- 所有用户数据通过 `CourseManager` 管理，不要直接读写 `data/courses/`
- 异常定义在所在模块的 `base.py` 中

### 不要做的事
- **所有改动必须局限在项目目录内**（`D:\lecture-assistant\`），不允许修改系统文件、用户目录、注册表、环境变量（进程内的除外）或项目外的任何路径。项目设计目标是"删除目录即彻底卸载"
- 不要引入新的框架或依赖，先确认是否可用已有技术栈替代
- 不要在页面文件中写业务逻辑，页面只做 UI + 调用
- 不要修改 `config.example.yaml`，只改 `config.yaml`
- 不要绕过 CourseManager 直接操作文件系统
- 不要用 `os.path` 做路径拼接，统一用 `pathlib.Path`
- 不要创建新的文档文件（README/CHANGELOG 等）除非明确要求
- 不要在 UI 中使用装饰性 emoji，用简洁文字 + Unicode 符号（✓/○）

## 关键设计决策（不要推翻）

### LLM 参数硬编码
- **temperature = 0.3**：教育内容需要事实准确 + 语言自然，0.3 是平衡点。不在 UI 暴露给用户
- **max_tokens = None**：不设输出上限，让 API 使用模型自然最大输出

### DeepSeek API 模型命名（2026-05 更新）
- **当前代**：V4 系列（2026-04-24 发布）
  - `deepseek-v4-flash`：快速/便宜，284B MoE / 13B 活跃参数，1M 上下文
  - `deepseek-v4-pro`：旗舰推理，1.6T MoE / 49B 活跃参数
- **即将废弃**（2026-07-24 硬截止）：
  - `deepseek-chat` → 迁移到 `deepseek-v4-flash`（非思考模式）
  - `deepseek-reasoner` → 迁移到 `deepseek-v4-flash`（思考模式）
- **base_url**：`https://api.deepseek.com`（不要加 `/v1`，OpenAI SDK 自动拼接路径）
- 本项目默认用 `deepseek-v4-flash`，性价比最高。如需更强推理可改为 `deepseek-v4-pro`

### Config 环境变量 `${VAR:}` 语法
- `${DEEPSEEK_API_KEY}` — 必填，未设置则抛出 `ConfigurationError`
- `${OPENAI_API_KEY:}` — 可选，未设置时用空字符串（`:}` = 空默认值）
- **规则**：只有当前 provider 对应的 key 必填（如 deepseek → `DEEPSEEK_API_KEY`），其他 provider 的 key 用 `${VAR:}` 可选语法，避免未配置时启动崩溃

### 多轮续写策略（复习与问答页）
- 第 1 轮正常生成 → 如果输出 ≥ 1500 字符且不含 "[生成完毕]"，发起续写 → 最多 3 轮
- 启发式终止：输出 < 1500 字符或含 "[生成完毕]" 时停止
- NiceGUI 版：每 chunk 立即更新 `ui.markdown.set_content()`，不再需要节流渲染

### 知识库按课程隔离
- 每课程独立 ChromaDB collection：`c_{md5(course_name)[:12]}`
- 持久化目录：`data/courses/{course}/chroma_db/`
- 状态持久化：`state.json` 中 `vector_store_ready` 字段
- 切换课程时懒加载 vector_store：sidebar 恢复 ready 状态，复习与问答页面用到时才初始化

### PPT 解析纯 Python
- python-pptx + olefile 实现，不依赖 LibreOffice
- 仅 PDF 解析需要 LibreOffice（magic-pdf 依赖）
- 旧格式 .ppt 只能提取文本，无法提取图片和公式

## 已有能力清单（不要重复造轮子）

| 能力 | 调用方式 | 所在文件 |
|------|---------|---------|
| 语音转文字 | `get_asr_model(config.asr).transcribe(audio_path)` | `src/asr/funasr_asr.py` |
| PPT/PPTX 文本提取 | `extract_pptx_text(path)` / `extract_ppt_text(path)` | `src/parser/ppt_extractor.py` |
| PDF 解析 | `get_parser(config.parser).parse(path, out_dir)` | `src/parser/mineru_parser.py` |
| EPUB 书本导入 | `get_epub_parser().parse(path, out_dir)` | `src/parser/epub_parser.py` |
| LLM 调用 | `DeepSeekLLM(config.llm).chat(messages)` | `src/llm/deepseek_llm.py` |
| LLM 流式 | `DeepSeekLLM(config.llm).stream_chat(messages)` | `src/llm/deepseek_llm.py` |
| 文本嵌入 | `get_embedder(config.embedding).embed(texts)` | `src/knowledge/embedder.py` |
| 向量存储 | `ChromaVectorStore(config.chromadb)` | `src/knowledge/chroma_store.py` |
| 语义分块 | `MarkdownChunker(chunk_size, overlap).chunk_text(text, meta)` | `src/knowledge/chunker.py` |
| 课件+录音合并 | `ContentMerger.merge(...)` | `src/merger/content_merger.py` |
| 多课程管理 | `CourseManager(data_dir)` | `src/course_manager.py` |
| 复习资料 CRUD | `cm.save/list/load/delete_review_material(...)` | `src/course_manager.py` |
| 多语言 | `t("key", **kwargs)` / `set_language("en")` | `src/i18n/__init__.py` |

NiceGUI 组件：
| 能力 | 调用方式 | 所在文件 |
|------|---------|---------|
| 侧边栏 | `render_sidebar()` | `nicegui_app/components/sidebar.py` |
| 主题注入 | `inject_theme()` | `nicegui_app/components/theme.py` |
| Tab 缓存（重对象） | `get_cache(key)` / `set_cache(key, val)` | `nicegui_app/state.py` |
| User 持久化（轻量键） | `get_user(key)` / `set_user(key, val)` | `nicegui_app/state.py` |
| 流式 LLM 到元素 | `_stream_llm_to_element(llm, messages, el)` | `nicegui_app/pages/review_qa.py` |

## 已知限制
- **ChromaDB 只有 add + delete_all**，没有 update/delete_by_id
- **切换课程会清空内存中的 ASR/解析结果**，只有已保存到磁盘的文件能恢复
- **生成中断后无断点续传**，需手动重新点击
- **测试覆盖 8 个模块 169 例**（config/chunker/embedder/llm/merger/course_manager/chroma_store/epub_parser），均通过 mock 隔离外部依赖

## 常用命令
```bash
# 启动
.venv\Scripts\activate && python nicegui_app/main.py
# 或双击 start.bat

# 测试
pytest tests/ -v

# 代码检查
ruff check

# 清理字节码缓存（修改代码后报 AttributeError 时执行）
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
```

## 已知陷阱

### NiceGUI 3.12.1: `app.storage.tab` 需要客户端连接

**症状**：`RuntimeError: app.storage.tab can only be used with a client connection`

**根因**：`app.storage.tab` 内部检查 `client.has_socket_connection`，该属性在浏览器 SocketIO 握手完成后才为 `True`。

**修复**：页面函数必须是 `async def`，第一行调用 `await ui.context.client.connected()`：
```python
@ui.page("/")
async def home():
    await ui.context.client.connected()  # 等待 WebSocket 握手完成
    # 现在可以安全使用 get_cache() / app.storage.tab
```

**不是** `await ui.client_connected()` — NiceGUI 3.x 中不存在该 API。

### NiceGUI 3.12.1: `ui.download.content()` 是函数调用，不是按钮

**症状**：进入页面后浏览器自动弹出下载框，无需任何点击。

**根因**：`ui.download.content()` 是**命令式函数**（`nicegui/functions/download.py`），调用时立即触发浏览器下载，返回值是 `None`（不是 UI 元素）。

**错误用法**：
```python
# 页面渲染时立即触发下载！不是按钮！
ui.download.content(content_bytes, filename="file.md")
```

**正确用法**：包在 `ui.button(on_click=...)` 回调中：
```python
def do_download():
    ui.download.content(content_bytes, filename="file.md")

ui.button("下载", on_click=do_download)
```

### NiceGUI 事件回调中的阻塞调用
NiceGUI 事件循环是单线程的，所有 UI 回调必须是非阻塞的。同步阻塞调用（LLM、ASR）必须用 `await asyncio.to_thread(fn, *args)` 包装，否则整个 UI 冻结。

### NiceGUI 流式渲染
流式 LLM 响应用 `_stream_llm_to_element()` 实现：sync generator → ThreadPoolExecutor → `loop.call_soon_threadsafe(queue.put_nowait, chunk)` → 主事件循环逐 chunk 更新 `ui.markdown.set_content()`。

### 修改代码后报 AttributeError
修改 `src/` 下模块后，Python 可能加载旧的 `.pyc` 字节码。执行上面的"清理字节码缓存"命令后重启应用。`start.bat` 已包含自动清理逻辑。

### Windows Batch 文件三大陷阱

**1. UTF-8 编码必须带 BOM**
- `.bat` 文件含中文 → 必须保存为 **UTF-8 with BOM**（`utf-8-sig`），否则 cmd.exe 用 GBK 读 UTF-8 字节 → 中文全部乱码 + 特殊字符（`^` 转义符等）失效 → 脚本解析崩溃
- 文件头 3 字节 `EF BB BF` = BOM 标记，告诉 Windows 这是 UTF-8 文件
- 写 `.bat` 文件后用 Python `pathlib.Path.write_text(content, encoding='utf-8-sig')` 确保 BOM

**2. `if (...)` 块内不要有括号**
- batch 的 `if` 用 `(...)` 作为块边界，块内的 `(` 或 `)` 会提前关闭块
- 如 `echo # 此文件被 gitignore 排除 (.gitignore)` → `.gitignore` 外的括号会终止 if 块
- **正确做法**：用 `if ... goto :label` 跳过，不用括号块

**3. 用 `echo/` 代替 `echo.` 输出空行**
- `echo.` 在某些 Windows 版本会被解析为"查找名为 echo 的文件"，导致意外行为
- 统一用 `echo/` 输出空行，安全可靠

### NiceGUI reload 模式下的多进程
`ui.run(reload=True)` 会启动 watchdog 监控文件变化。如果手动 `taskkill` 杀进程不干净，可能留多个进程竞争同一端口。右键点 `start.bat` → "以管理员身份运行" 或重新双击启动前，确保没有残留 Python 进程（任务管理器检查）。

### Mermaid 11.x 语法变更
NiceGUI 3.12.1 内置 Mermaid 11.15.0，该版本：
- 移除了 `graph` 关键字，只接受 `flowchart`
- **不支持 subgraph 体内的 `direction` 关键字**（会导致 "Parse error"），必须写为声明行内联：`subgraph LR ["title"]`
- subgraph 标题必须用方括号：`["title"]`

LLM 常生成旧语法：`graph TD` + `subgraph "标题"` + 体内 `direction LR` + Unicode 花引号 `""`。

**修复**：`_normalize_mermaid()` 函数自动处理全部 3 种情况。`_normalize_content()` 包含 LaTeX + Mermaid 两个规范化。

### `add_head_html`/`add_body_html` 在页面函数之外调用需 `shared=True`

NiceGUI 要求：在 `@ui.page` 函数之外调用 `add_head_html`/`add_body_html`/`add_css` 时，必须传 `shared=True`，否则 `ui.run()` 抛出 RuntimeError。

```python
# 顶层调用（import 时）
ui.add_body_html("<script>...</script>", shared=True)

# 页面函数内调用（无需 shared）
@ui.page("/")
async def home():
    ui.add_body_html("<script>...</script>")
```

为防止脚本被 innerHTML 注入后不执行（浏览器安全策略），应在 `ui.run()` 之前调用，确保脚本包含在初始 HTML 响应中。
