# CLAUDE.md — Lecture Assistant

课堂录音转文字 + 课件解析 + AI 复习资料生成 + 智能问答，一站式 Streamlit 应用。

> 总代码量 ~3100 行 Python | 所有核心模块已完成 | 169 个单元测试

## 当前进度（截至 2026-05-28）

**当前阶段**：P6 — 工程化收尾 + GitHub 发布准备

**核心链路全部跑通**。

### 会话 1 完成（P0: 5 个 bug 修复）
- [x] `config.yaml` 明文 API key → `${DEEPSEEK_API_KEY}`
- [x] `requirements.txt` 补全 `python-pptx` + `olefile`
- [x] `run.py` 添加 `logging.basicConfig(level=logging.INFO)`，激活所有 logger
- [x] `chunker.py:144` 硬编码 800 → `self._chunk_size`（`_split_protected` 从 static method 改为实例方法）
- [x] `course_manager.py` 5 处静默 `except Exception` 加上 `logger.warning(..., exc_info=True)`
- [x] `pytest tests/ -v` 61 passed 无回归

### 会话 2 完成（P1: pyproject.toml）
- [x] 创建 `pyproject.toml`：含 project metadata、dependencies、dev deps（ruff+mypy+pytest）
- [x] `requirements.txt` 保留作为过渡（pyproject.toml 成为主声明）
- [x] ruff 配置：target-version py312, line-length 100, select E/F/I/W/UP, quote-style double
- [x] mypy 配置：非 strict 模式，check_untyped_defs=true
- [x] pytest 配置：testpaths = ["tests"]
- [x] ruff + mypy 已安装到项目 .venv
- [x] 首次检查结果：ruff 54 个诊断 | ruff format 20 文件待格式化 | mypy 27 个诊断

### 会话 3 完成（P1: ruff format + lint 修复）
- [x] `ruff format` 格式化全项目 20 个文件
- [x] `ruff check --fix` 自动修复 20 个问题（unused imports, import sorting, f-strings 等）
- [x] 手动修复 23 个剩余问题：
  - E402: `pages/*.py` 和 `src/config.py` 添加 `# noqa: E402`（必须放在 `st.set_page_config()` / 环境变量设置之后，有意为之）
  - E501: 5 处长字符串换行
  - E741: `ppt_extractor.py` 中 `l` → `line`
  - F841: `ppt_extractor.py` 中未使用的 `ver_inst` 加 `_` 前缀
- [x] `pytest tests/ -v` 61 passed 无回归
- [x] `ruff check src/ pages/` 零错误

### 会话 4 完成（P1: course_manager.py 单元测试）
- [x] Plan Mode 制定测试计划（12 个测试类，55 个测试方法）
- [x] 新建 `tests/test_course_manager.py`（~430 行）
- [x] 覆盖所有公开方法：课程 CRUD、状态持久化、聊天历史、复习资料完整生命周期、统计、路径助手、数据类默认值
- [x] 覆盖边界情况：空名/空白名 ValueError、重复创建幂等、损坏 JSON 恢复、索引过期条目清理、中文名称、特殊字符过滤
- [x] 发现并修复 bug：`create_course` 调用 `self._save_state()` → `self.save_state()`（方法名错误，导致无法创建课程）
- [x] `pytest tests/ -v` 116 passed（61 原有 + 55 新增），无回归
- [x] `ruff check src/ pages/ tests/test_course_manager.py` 零错误

### 会话 5 完成（P1: chroma_store.py 单元测试）
- [x] Plan Mode 制定测试计划（7 个测试类，33 个测试方法）
- [x] 新建 `tests/test_chroma_store.py`（~350 行）
- [x] 覆盖所有 7 个方法：init、add_documents、search、delete_collection、count、update_documents、delete_by_id
- [x] Mock ChromaDB PersistentClient + BaseEmbedder，不启动真实 ChromaDB
- [x] 发现并修复 bug：`search` 中 `results["documents"]` 括号访问 → `results.get("documents")`（ChromaDB 可能不返回该 key，导致 KeyError）
- [x] `pytest tests/ -v` 149 passed（116 原有 + 33 新增），无回归
- [x] `ruff check src/ pages/ tests/test_chroma_store.py` 零错误

### 5 会话路线图完成
P0 → P1 工程化基础建设完成：
- P0: 5 个 bug 修复（安全、日志、依赖）
- P1: pyproject.toml + ruff format/lint + course_manager 测试 + chroma_store 测试
- 测试从 61 → 149 个，覆盖 config/chunker/embedder/llm/merger/course_manager/chroma_store
- 源码 bug 修复：`_save_state` 方法名错误、`search` 中 KeyError 风险、`_split_protected` 硬编码 chunk_size

### 后续建议方向
- 补充 `pages/` 中 Streamlit 页面的集成测试（需 streamlit AppTest）
- 添加 CI/CD（GitHub Actions: ruff + mypy + pytest）
- 配置 pre-commit hooks

### P4 功能增强 — 全部完成 ✅

### 会话 6 完成（P4-1: 多 LLM Provider 支持）
- [x] `LLMConfig` 新增 `openai_api_key`、`anthropic_api_key`、`max_retries` 字段
- [x] `config.yaml` 补全多 provider 注释和字段
- [x] 新建 `src/llm/openai_llm.py`：OpenAI 原生 API 实现
- [x] 新建 `src/llm/factory.py`：`get_llm(config)` 根据 provider 分发，预留 `"anthropic"` 扩展点
- [x] `DeepSeekLLM` 重试次数改用 `config.max_retries`（不再硬编码 3）
- [x] `pages/2_复习与问答.py` + `test_pipeline.py` 改用 `get_llm()` 工厂
- [x] `pytest tests/ -v` 149 passed | `ruff check` 零错误

### 会话 7 完成（P4-2: 去除 page_icon emoji）
- [x] `pages/1_资料录入.py` + `pages/2_复习与问答.py` 中 `page_icon` 改为空字符串

### 会话 8 完成（P4-3: 移动端响应式优化）
- [x] 新增 `@media (max-width: 480px)` 断点：列强制堆叠、触控目标 44px、标题缩放、内边距收紧
- [x] 增强 `@media (max-width: 768px)`：侧边栏按钮增大触控区域

### 会话 9a 完成（P4-4a: i18n 基础设施 + sidebar/run.py 翻译）
- [x] 新建 `src/i18n/__init__.py`：`t(key, **kwargs)`、`set_language()`、`get_language()`、`get_available_languages()`
- [x] 新建 `src/i18n/zh.json`：~45 个中文翻译 key
- [x] 新建 `src/i18n/en.json`：~45 个英文翻译 key
- [x] `sidebar.py` 新增语言切换器（selectbox，存储在 `st.session_state.language`）
- [x] `sidebar.py` 所有 ~25 个用户可见字符串改为 `t()` 调用
- [x] `run.py` 所有 ~15 个用户可见字符串改为 `t()` 调用
- [x] 材料类型映射（`_material_type_short`）改用 `t()` 实现中英切换
- [x] `pytest tests/ -v` 149 passed | `ruff check` 零错误

### 会话 9b 完成（P4-4b: 翻译 pages/ 子页面）
- [x] `pages/1_资料录入.py`：~55 个 UI 字符串改为 `t()` 调用
- [x] `pages/2_复习与问答.py`：~65 个 UI 字符串改为 `t()` 调用
- [x] 更新 `_material_type_short`（page 2 本地副本）使用 `t()` 映射
- [x] LLM prompt 模板（`_build_type_sections` / `_build_generation_prompt`）保持中文不动（发送给 LLM 的提示词）
- [x] 生成类型选项保持中文不动（用于 prompt 匹配逻辑的 key）
- [x] `zh.json` / `en.json` 新增 ~110 个翻译 key（总计 ~155 个）
- [x] 修复 F402: 循环变量 `t` 与 i18n `t()` 重名，重命名为 `tr`
- [x] `pytest tests/ -v` 149 passed | `ruff check` 零错误

### 会话 9c 完成（P4-4c: 翻译 prompts/ 模板）
- [x] 创建 `prompts/zh/` + `prompts/en/` 子目录，按语言组织 3 个 .txt 模板
- [x] `prompts/zh/`：原有中文模板（`review_generation.txt`、`summary.txt`、`qa_system.txt`）
- [x] `prompts/en/`：英译版本（保持相同的 `{variable}` 占位符）
- [x] `BaseLLM.load_prompt()` 根据当前语言自动选择 `prompts/<lang>/`，CLI 环境默认 zh
- [x] `summary.txt` 确认无引用（预留模板），一并翻译
- [x] `pytest tests/ -v` 149 passed | `ruff check` 零错误

### 会话 11 完成（P6: 工程化收尾）
- [x] 初始化 git 仓库 + 首次 commit + push 到 GitHub（`chu-qin/lecture-assistant`）
- [x] `.gitignore` 新增 `.claude/` 排除（Claude Code 本地权限文件不应提交）
- [x] `src/config.py` 新增 `load_dotenv()`，启动时自动从 `.env` 文件加载环境变量
- [x] `setup_env.bat` 全面翻新：中文化 + 步骤 6 交互式 API Key 配置（选择 provider → 输入 key → 自动写入 `.env`）
- [x] `start.bat` 中文化 + 启动前检查 `.env` 是否存在并提示
- [x] `README.md` 快速开始章节重写（`.env` 方式 + 5 步使用流程）
- [x] 修复 3 个配置 bug：
  - `openai_api_key` / `anthropic_api_key` 缺少默认值导致未配置时启动崩溃 → 加 `${VAR:}` 空默认值
  - `start.bat` 手动 `start "" http://...` 导致双浏览器窗口 → 删除，只剩 Streamlit 自动打开
  - `config.example.yaml` 模型名用已废弃的 `deepseek-chat` → 改为 `deepseek-v4-flash`
- [x] `config.yaml` + `config.example.yaml` 模型注释更新为 V4 系列
- [x] `pytest tests/ -v` 145 passed（config 13/13）
- [x] `pyproject.toml` + `requirements.txt` 新增 `ebooklib>=0.17` + `html2text>=2024.2`
- [x] 新建 `src/parser/epub_parser.py`（~120 行）：EpubParser 类 + get_epub_parser() 工厂
- [x] EPUB → Markdown：ebooklib 读取元数据/章节，html2text 转换 HTML → Markdown，图片提取到 `images/`
- [x] 单文件 `.md` 输出到 `parsed_docs/`，与下游 ContentMerger/ChromaDB/页面 2 零改动兼容
- [x] `src/parser/__init__.py` 导出 EPUB 相关符号
- [x] `pages/1_资料录入.py` 新增第三个 Tab「书本导入」
- [x] `src/ui/session_state.py` 新增 `book_results` 默认值 + reset 清理
- [x] `zh.json` / `en.json` 新增 18 个翻译 key（`page1.tab_book` / `page1.book_*`）
- [x] `src/parser/mineru_parser.py` streamlit import 改为条件导入（测试兼容）
- [x] 新建 `tests/test_epub_parser.py`：7 个测试类，20 个测试方法
- [x] 修复 `test_chunker.py` 中 2 个 F841（未使用变量）
- [x] `pytest tests/ -v` 169 passed（149 + 20 新增）| `ruff check` 零错误

### P4 功能增强 — 全部完成
P4 四项全部完成：
- P4-1: 多 LLM Provider 支持（DeepSeek + OpenAI + 预留 Anthropic）
- P4-2: 去除 page_icon emoji
- P4-3: 移动端响应式 CSS（480px + 768px 断点）
- P4-4: i18n 多语言支持（3 个子会话：基础设施 → 页面翻译 → prompt 模板）
- 测试始终 149+ passed 无回归
- 总计新增/修改 ~800 行代码

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
src/i18n/         # 多语言：zh.json + en.json + t() 函数
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
