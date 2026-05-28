# CLAUDE.md — Lecture Assistant

课堂录音转文字 + 课件解析 + AI 复习资料生成 + 智能问答，一站式 Streamlit 应用。

> 总代码量 ~3100 行 Python | 所有核心模块已完成 | 169 个单元测试

## 当前进度（截至 2026-05-28）

**当前阶段**：P6 — 工程化收尾 + GitHub 发布准备，核心链路全部跑通。

已完成里程碑：
- P0: 安全/日志/依赖 5 个 bug 修复
- P1: pyproject.toml、ruff/mypy/pytest 配置、course_manager + chroma_store 单元测试（测试 61→149）
- P4: 多 LLM Provider、移动端响应式、i18n 多语言（中/英 155 keys）、EPUB 书本导入
- P6: Git 初始化 + GitHub 发布、.env 配置、setup_env.bat/start.bat 中文化
- UI 优化: 摘要持久化、sticky 布局、KaTeX 字符级扫描器、主题切换修复
- 测试: 169 passed、ruff 零错误

### 后续优化方向

#### 高优先级

- **CI/CD**：GitHub Actions 跑 ruff + mypy + pytest，PR 门禁
- **pre-commit hooks**：本地提交前自动 ruff format + check
- **Streamlit 集成测试**：用 `streamlit.testing.AppTest` 覆盖页面核心流程（上传文件 → ASR → 生成资料 → 问答）

#### 前端框架迁移（中远期，视需要决定）

截至 2026-05，Streamlit 存在以下**无法通过 CSS hack 根治**的限制：

| 痛点 | 说明 |
|------|------|
| **Sticky 定位不可靠** | 左右栏独立滚动 + 标签页/输入框 sticky 完全依赖 CSS `:has()` 选择器和 `position: sticky`，Streamlit 升级可能改变 DOM 结构导致失效 |
| **KaTeX 报错无容错** | `st.markdown()` 内部启用 KaTeX strict 模式，无法配置关闭。LLM 输出格式稍有偏差（未闭合 `$`、中文紧贴公式等）即大面积报错。当前通过字符级扫描器 `_scan_math_delimiters()` 转义孤立 `$` 来缓解，但仍有极端 case 可能漏过 |
| **无离线/PWA 能力** | Streamlit 是纯服务端渲染，断网不可用，无法打包为桌面应用 |
| **组件黑盒** | 无法直接控制 DOM/CSS，自定义 UI 行为全靠 `data-testid` 属性选择器 hack，升级风险高 |
| **会话状态不持久** | 刷新页面后 session_state 丢失（除课程数据已持久化到磁盘），用户需重新操作 |

##### 候选替代框架

| 框架 | 技术栈 | 优势 | 风险 |
|------|--------|------|------|
| **NiceGUI** | Python + Vue/Quasar (服务端渲染) | UI 控件丰富（sticky 原生支持），数学公式可用 `ui.markdown()` 或 `ui.math()`，学习曲线平缓，可打包为桌面应用 | 生态较小（14k stars），社区资源少，复杂布局不如 Streamlit 直观 |
| **Gradio** | Python + Svelte (服务端渲染) | ML 场景成熟（HuggingFace 官方），组件丰富，支持 `gr.Markdown()` 含 LaTeX，天然支持 streaming | 定制化能力弱，多页面/复杂布局不友好，侧边栏导航需自己实现 |
| **Reflex** (原 Pynecone) | Python → React (编译为 Next.js) | 完全控制前端（React 组件级），数学可用 KaTeX/MathJax 自定义配置，sticky/滚动等原生 DOM 能力，可导出静态站点/PWA | 学习曲线陡（需理解 React 概念），生态最小（15k stars），API 仍在快速变化 |
| **Dash** (Plotly) | Python + React (服务端渲染) | 企业级成熟度，Plotly 图表原生支持，回调系统清晰，Layout 完全可控 | 重度依赖回调模式（代码量大于声明式），UI 外观偏企业/过时，移动端适配需额外工作 |

##### 迁移策略建议

如果决定迁移，推荐分三步走：

1. **抽离 UI 层接口**（0 风险，可在 Streamlit 内完成）
   - 定义抽象 UI 层（`BaseUI`），将页面逻辑与框架解耦
   - 当前 `pages/*.py` 中直接调用 `st.xxx()` 的地方，封装为 `ui.markdown()` / `ui.button()` / `ui.chat_message()` 等
   - 这一步不改变任何功能，只是代码重构

2. **选型 PoC**（选 1 个框架做最小可行原型）
   - 只迁移**一个页面**（建议"复习与问答"，因为它是 sticky + 公式问题的重灾区）
   - 验证：sticky 效果、公式渲染容错、移动端表现、Chat 组件可用性
   - 评估标准：DOM 控制力 > 公式渲染容错 > 迁移成本 > 生态成熟度
   - 当前倾向：**NiceGUI**（平衡控制力和低成本）或 **Reflex**（最大控制力但成本高）

3. **完整迁移**（PoC 通过后）
   - 按页面逐一迁移，每迁移一个页面就回归测试
   - 保留 Streamlit 分支作为回退方案
   - 目标：sticky/公式问题彻底消失，可打包为桌面应用（Electron/PyInstaller）

##### 暂不推荐

- **完全自研前端（React/Vue + FastAPI）**：灵活性最大但成本极高，需同时维护前后端两套代码，对个人项目不划算
- **Next.js / SvelteKit 等全栈框架**：强迫用 JS/TS 重写全部后端逻辑，工作量大且打破 Python 全栈的统一性

## 技术栈
- Python 3.10+, Windows 10+, Streamlit 1.28+
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
src/ui/          # Streamlit 公共组件：sidebar + session_state
src/i18n/        # 多语言：zh.json + en.json + t() 函数
pages/           # Streamlit 2 个子页面 (1-2)
prompts/         # LLM 提示词模板，按语言分子目录 (zh/ + en/)
tools/           # ffmpeg 绿色版、LibreOffice 便携版
data/courses/    # 用户数据，按课程分子目录
```

## 编码约定（必须遵守）

### 架构模式
- **每个模块必有 `base.py`**：定义抽象基类 + dataclass 数据契约 + 模块专属异常类
- **具体实现在独立文件**：如 `funasr_asr.py`、`deepseek_llm.py`，接受对应 Config dataclass
- **抽象基类只声明方法签名，不实现**

### 配置系统
- 所有配置是 `@dataclass`，字段有默认值，定义在 `src/config.py`
- `AppConfig` 是顶层容器，包含 `ASRConfig`, `LLMConfig` 等子配置
- 用 `get_config()` 获取全局单例，不要重复读取 YAML
- 支持 `${ENV_VAR:default}` 环境变量引用语法

### Streamlit 页面
- 每个 `pages/*.py` 开头必须有：
  ```python
  import sys
  from pathlib import Path
  _project_root = Path(__file__).resolve().parent.parent
  if str(_project_root) not in sys.path:
      sys.path.insert(0, str(_project_root))
  ```
- 每页调用 `init_session_state()` + `render_sidebar()` 开始
- 用 `get_state(key, default)` / `set_state(key, value)` 读写 session state，不要直接用 `st.session_state`
- 前置条件检查后 `st.stop()`，不要用 if/else 嵌套
- **Streamlit 嵌套按钮陷阱**：`st.popover` 内嵌套 `if button:` 不可靠，改用 session state 标记 + inline 确认/取消双按钮

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

### 多轮续写策略（页面 2: 复习与问答）
- 第 1 轮正常生成 → 如果输出 ≥ 1500 字符且不含 "[生成完毕]"，发起续写 → 最多 3 轮
- 启发式终止：输出 < 1500 字符或含 "[生成完毕]" 时停止
- **Streamlit 节流渲染**：每 8 个 token chunk 才更新一次 `output_placeholder.markdown()`，避免第 2+ 轮时 `full_output` 已累积数千字后每个 chunk 都重渲染整块 markdown 导致界面卡死。每轮流式结束后有最后一次补渲染确保所有内容上屏

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
| 文本嵌入 | `get_embedder(config.embedding).embed(texts)` | `src/knowledge/embedder.py` |
| 向量存储 | `ChromaVectorStore(config.chromadb)` | `src/knowledge/chroma_store.py` |
| 语义分块 | `MarkdownChunker(chunk_size, overlap).chunk_text(text, meta)` | `src/knowledge/chunker.py` |
| 课件+录音合并 | `ContentMerger.merge(...)` | `src/merger/content_merger.py` |
| 多课程管理 | `CourseManager(data_dir)` | `src/course_manager.py` |
| 复习资料 CRUD | `cm.save/list/load/delete_review_material(...)` | `src/course_manager.py` |
| 侧边栏 | `render_sidebar()` | `src/ui/sidebar.py` |
| Session State | `get_state(k, d)` / `set_state(k, v)` | `src/ui/session_state.py` |
| CSS 主题 | `inject_theme_css()` | `src/ui/theme.py` |
| 多语言 | `t("key", **kwargs)` / `set_language("en")` | `src/i18n/__init__.py` |

## 已知限制
- **ChromaDB 只有 add + delete_all**，没有 update/delete_by_id
- **切换课程会清空内存中的 ASR/解析结果**，只有已保存到磁盘的文件能恢复
- **生成中断后无断点续传**，需手动重新点击
- **测试覆盖 8 个模块 169 例**（config/chunker/embedder/llm/merger/course_manager/chroma_store/epub_parser），均通过 mock 隔离外部依赖

## 常用命令
```bash
# 启动
.venv\Scripts\activate && streamlit run run.py

# 测试
pytest tests/ -v

# 单独跑一个页面（调试用）
streamlit run pages/1_资料录入.py

# 清理字节码缓存（修改 src/ 后报 AttributeError 时执行）
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
```

## 已知陷阱

### 修改 src/ 模块后报 AttributeError
Streamlit 会缓存已导入模块的 `.pyc` 字节码。修改 `src/` 下的模块（如 `course_manager.py`）后，必须清理 `__pycache__` 目录，否则可能加载旧版本导致 `object has no attribute` 错误。**每次修改 src/ 下的类定义或新增方法后，先执行上面的清理字节码命令再启动 Streamlit。**

### Streamlit 页面中辅助函数的定义顺序
Streamlit 页面脚本是**从头到尾顺序执行**的。所有在页面主体代码中调用的辅助函数必须**先定义后使用**——即函数 `def` 必须写在 `if st.button(...):` 等调用代码之前。Python 对 `def` 内部的延迟调用没有顺序要求，但对模块顶层直接执行的调用有要求。**所有 helper 函数放在 `init_session_state()` / `render_sidebar()` 之前。**

### Streamlit Widget 会话状态限制
新版 Streamlit 禁止在 widget 实例化后修改其绑定的 `st.session_state` key。聊天输入用 `st.chat_input`（自动清空），不要用 `st.text_input` + 手动重置 session_state。`st.switch_page` 路径相对于入口脚本目录，子页面中需动态检测前缀（见 `sidebar.py` 的 `_PAGE_PREFIX`）。

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

### Streamlit 自动打开浏览器
- `streamlit run` 默认会自动打开浏览器到 `http://localhost:8501`
- **不要**在启动脚本里额外加 `start "" http://localhost:8501`，会导致双窗口
- 如需禁用自动打开：在 `.streamlit/config.toml` 设 `[server] headless = true`
