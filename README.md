# Lecture Assistant

课堂录音转文字 + 课件解析 + AI 复习资料生成 + RAG 智能问答，一站式 Streamlit 应用。

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.28%2B-red)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/tests-169%20passed-green)](tests/)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230)](https://github.com/astral-sh/ruff)

**纯本地运行，所有模型缓存在项目目录内，删除目录即彻底卸载。**

---

## 功能

一个完整的课堂学习辅助工具，覆盖从原始材料到结构化复习资料的全链路：

**材料录入**
- 语音转文字 — FunASR SenseVoiceSmall 模型，支持中/英/粤语，内置 VAD + 标点恢复
- 课件解析 — PPT/PPTX 纯 Python 提取，PDF 经 MinerU 转结构化 Markdown（公式 -> LaTeX，表格保留）
- 书本导入 — EPUB 电子书导入，自动提取元数据/章节，转结构化 Markdown

**复习生成**
- 自动合并课件内容与录音转录文本，调用 LLM 生成四类复习资料：
  - 复习提纲（概念标注重点/难点 + 公式定理 + 常见误区)
  - 详细笔记（逐章逐节知识点详解 + 例题)
  - 知识结构图（章节层级 + 跨章节关联)
  - 自测题库（单选/填空/简答/计算 + 答案解析)
- 多轮续写策略：长内容自动续写最多 3 轮，流式渲染带节流

**RAG 智能问答**
- 基于课件 + 录音转录 + 复习资料构建知识库
- ChromaDB 向量存储 + BGE 嵌入模型，按课程隔离 collection
- 检索增强生成：区分一手资料（课件/录音）和 AI 生成资料（复习材料），优先参考原文

**多课程管理**
- 每课程独立目录，数据在 `data/courses/<课程名>/`
- 课程状态持久化（JSON），聊天历史可导出 Markdown

**多语言**
- 侧边栏一键切换中/英文，155 个翻译 key 覆盖全部 UI
- Prompt 模板按语言分目录，LLM 调用自动匹配

**多 LLM Provider**
- 支持 DeepSeek、OpenAI，预留 Anthropic 扩展点
- 工厂模式 `get_llm(config)` 统一分发

---

## 快速开始

### 1. 环境初始化

**方式 A：一键自动安装**

双击项目目录下的 `setup_env.bat`，脚本会自动完成：
- 检测 Python 环境
- 创建虚拟环境 `.venv`
- 安装所有依赖包
- 下载 ffmpeg 绿色版
- 创建数据目录

**方式 B：手动安装**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置 API Key

在项目根目录新建 `.env` 文件，写入：

```
DEEPSEEK_API_KEY=sk-your-key-here
```

> 注册 [DeepSeek 开放平台](https://platform.deepseek.com/)，在「API Keys」页面创建 Key，新用户免费赠送额度。
>
> `.env` 文件已被 `.gitignore` 排除，不会提交到 GitHub，不用担心泄露。

语音转写和课件解析不需要 Key 即可使用，仅复习资料生成和智能问答需要。

### 3. 创建配置文件

```bash
copy config.example.yaml config.yaml
```

默认配置即可使用。如需使用 OpenAI，修改 `config.yaml` 中 `llm.provider` 为 `"openai"` 并在 `.env` 中追加 `OPENAI_API_KEY`。

### 4. 启动

```bash
# 双击 start.bat，或在终端执行：
.venv\Scripts\activate
streamlit run run.py
```

浏览器自动打开 `http://localhost:8501`。

### 5. 使用流程

1. 侧边栏点击「创建课程」，输入课程名称
2. 进入「资料录入」页面，上传课堂录音或课件文件
3. 进入「复习与问答」页面，选择复习资料类型，点击生成
4. 在聊天框中提问，AI 基于课件和录音内容回答

---

## 项目结构

```
lecture-assistant/
├── run.py                          # Streamlit 入口
├── pages/
│   ├── 1_资料录入.py                # 语音转文字 + 课件解析
│   └── 2_复习与问答.py              # 复习资料生成 + RAG 问答
├── src/
│   ├── config.py                   # 配置加载 + 模型缓存管理
│   ├── course_manager.py           # 多课程管理 + 状态持久化
│   ├── asr/
│   │   ├── base.py                 #   ASR 抽象接口
│   │   └── funasr_asr.py           #   FunASR SenseVoiceSmall 实现
│   ├── parser/
│   │   ├── base.py                 #   解析器抽象接口
│   │   ├── mineru_parser.py        #   magic-pdf 调用
│   │   ├── ppt_extractor.py        #   .ppt/.pptx 纯 Python 文本提取
│   │   └── epub_parser.py          #   EPUB 书本导入（ebooklib + html2text）
│   ├── llm/
│   │   ├── base.py                 #   LLM 抽象接口 + Prompt 加载
│   │   ├── deepseek_llm.py         #   DeepSeek API 实现
│   │   ├── openai_llm.py           #   OpenAI 原生 API 实现
│   │   └── factory.py              #   LLM Provider 工厂
│   ├── knowledge/
│   │   ├── base.py                 #   Embedder / VectorStore 抽象
│   │   ├── embedder.py             #   BGE-small-zh 嵌入实现
│   │   ├── chunker.py              #   Markdown 语义分块
│   │   └── chroma_store.py         #   ChromaDB 向量存储
│   ├── merger/
│   │   └── content_merger.py       # 课件 + 录音内容合并
│   ├── ui/
│   │   ├── sidebar.py              # 统一侧边栏（课程选择 + 导航 + 语言切换）
│   │   ├── session_state.py        # Session State 管理
│   │   └── theme.py                # 自定义 CSS 注入 + 响应式布局
│   └── i18n/
│       ├── __init__.py             # t() 函数 + 语言管理
│       ├── zh.json                 # 中文翻译 (155 keys)
│       └── en.json                 # 英文翻译 (155 keys)
├── prompts/
│   ├── zh/                         # 中文 Prompt 模板
│   └── en/                         # 英文 Prompt 模板
├── tests/                          # 169 个单元测试
├── config.yaml                     # 用户配置（gitignore）
├── config.example.yaml             # 配置模板
├── LICENSE                         # MIT
├── pyproject.toml                  # 项目元数据 + ruff/mypy/pytest 配置
├── requirements.txt                # Python 依赖
├── setup_env.bat                   # 一键环境初始化
└── start.bat                       # 一键启动
```

---

## 架构

```
用户 -> Streamlit UI (run.py + pages/)
     -> CourseManager (多课程隔离, 状态持久化)
     -> FunASR (语音转写) + MinerU (文档解析) + EpubParser (书本导入)
     -> ContentMerger (课件 + 录音合并)
     -> LLM Factory (DeepSeek / OpenAI / Anthropic)
        -> 复习资料生成 (多轮续写)
        -> RAG 智能问答 (ChromaDB + BGE)
```

- 每个功能模块遵循 `base.py` (抽象基类 + 数据契约) + 具体实现的模式
- 配置通过 `@dataclass` 集中管理，支持 `${ENV_VAR:default}` 环境变量引用
- 所有文件路径使用 `pathlib.Path`，用户数据通过 `CourseManager` 统一管理

---

## 配置

```yaml
# 语音识别
asr:
  model: "iic/SenseVoiceSmall"
  device: "cpu"           # cpu / cuda / auto
  language: "zh"          # zh / en / yue / auto
  use_timestamps: true

# 文档解析
parser:
  backend: "magic-pdf"
  method: "auto"          # auto / txt / ocr

# LLM (支持 DeepSeek / OpenAI)
llm:
  provider: "deepseek"    # deepseek / openai
  api_key: "${DEEPSEEK_API_KEY}"
  openai_api_key: "${OPENAI_API_KEY:}"        # 使用 OpenAI 时填写
  anthropic_api_key: "${ANTHROPIC_API_KEY:}"  # 预留
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-flash"    # deepseek-v4-flash (快速) / deepseek-v4-pro (旗舰)
  temperature: 0.3
  max_tokens: 4096
  max_retries: 3
  timeout: 120

# 文本嵌入
embedding:
  model_name: "BAAI/bge-small-zh-v1.5"
  device: "cpu"

# 向量数据库
chromadb:
  chunk_size: 800
  chunk_overlap: 150
  distance_metric: "cosine"
```

GPU 加速：将 `asr.device` 和 `embedding.device` 改为 `cuda`，需安装 CUDA 版 PyTorch。

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# Lint
ruff check src/ pages/

# 格式化
ruff format src/ pages/

# 类型检查
mypy src/
```

**测试覆盖 (169 个)**：config, chunker, embedder, llm, merger, course_manager, chroma_store, epub_parser — 均通过 mock 隔离外部依赖，无需真实 ChromaDB 或 API Key。

修改 `src/` 模块后如果出现 `AttributeError`，清理字节码缓存后重试：

```bash
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
```

---

## FAQ

**启动报错「配置加载失败」？** 确保已从 `config.example.yaml` 复制为 `config.yaml`。

**首次运行 ASR 慢？** 首次从 ModelScope 下载模型 (~300 MB)，缓存于 `data/model_cache/`，后续秒开。

**PPT 解析效果不好？** 旧格式 `.ppt` 只能提取文本。建议导出为 PDF 后用 PDF 模式解析以获得公式和图片。

**PDF 解析报错？** 需要 LibreOffice（magic-pdf 依赖）。安装后加入 PATH 或将便携版放入 `tools/LibreOffice/`。

**数据在哪里？** `data/courses/<课程名>/`，按类型分子目录。删除项目目录即彻底清除。

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 语音识别 | FunASR SenseVoiceSmall | 阿里达摩院，多语言 + VAD + 标点恢复 |
| 文档解析 | python-pptx + olefile + MinerU magic-pdf + ebooklib + html2text | PPT/PDF/EPUB 转结构化 Markdown |
| 大语言模型 | DeepSeek / OpenAI API | OpenAI 兼容协议，工厂模式分发 |
| 文本嵌入 | BAAI/bge-small-zh-v1.5 | 512 维，cosine 距离 |
| 向量存储 | ChromaDB | 按课程隔离 collection，PersistentClient |
| UI 框架 | Streamlit 1.28+ | 浏览器界面，响应式 CSS |
| 多语言 | 自研轻量 JSON i18n | 155 keys，无 gettext 依赖 |
| 音频处理 | ffmpeg | 绿色版，自动下载至 `tools/` |
| 代码质量 | ruff + mypy + pytest | 零 lint 错误，169 个测试 |

## 许可证

MIT
