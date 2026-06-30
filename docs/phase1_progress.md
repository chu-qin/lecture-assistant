# Phase1 Fixes — 开发进度与下一步计划

> **最后更新**: 2026-06-30  
> **Branch**: `phase1_fixes`  
> **状态**: 核心架构已完成 (Phase 1-3)，待完成 Phase 4-7

---

## 一、已完成 (Phase 1-3)

### Phase 1: 项目脚手架 ✅

| 条目 | 状态 |
|------|------|
| Vite + Vanilla JS 项目骨架 | ✅ |
| CSS 变量体系 (light/dark 双主题) | ✅ |
| 6 个 CSS 模块 (base / components / nav / home / materials / review) | ✅ |
| npm 依赖 (marked / katex / mermaid / vite) | ✅ |

### Phase 2: 前端核心模块 ✅

| 条目 | 状态 |
|------|------|
| `router.js` — Hash 路由 + `onBeforeChange` 钩子 | ✅ |
| `store.js` — 全局状态管理 + 监听器 | ✅ |
| `i18n.js` — 客户端翻译 (zh/en) | ✅ |
| `theme.js` — 主题初始化和切换 | ✅ |
| `api.js` — HTTP 客户端 + SSE 流读取器 | ✅ |
| `markdown.js` — Marked + KaTeX + Mermaid 渲染 | ✅ |
| `nav.js` — 顶栏导航组件 | ✅ |
| `toast.js` — Toast 通知组件 | ✅ |

### Phase 3: 后端 API 重构 ✅

| 条目 | 状态 |
|------|------|
| `src/api/server.py` — FastAPI 应用工厂 + 静态文件 | ✅ |
| `src/api/courses.py` — 课程 CRUD | ✅ |
| `src/api/asr_routes.py` — ASR 转录 API (SSE) | ✅ |
| `src/api/parser_routes.py` — 课件解析 API (SSE) | ✅ |
| `src/api/materials.py` — 复习资料管理 API | ✅ |
| `src/api/generate.py` — 资料生成 API (SSE 流式) | ✅ |
| `src/api/chat.py` — RAG 问答 API (SSE 流式) | ✅ |
| `src/llm/prompts.py` — Prompt 构建去重 | ✅ |
| `src/llm/latex_utils.py` — LaTeX 工具去重 | ✅ |
| `src/llm/section_split.py` — 章节拆分去重 | ✅ |

---

## 二、前端页面实现状态

### 首页 (home.js) — 205 行

| 功能 | 状态 |
|------|------|
| 课程卡片列表 (名称 / 统计 / KB 状态) | ✅ |
| 当前课程 Hero 区 | ✅ |
| 创建新课程 | ✅ |
| 删除课程 (确认弹窗) | ✅ |
| 空状态引导 | ✅ |
| 进入课程工作区 | ✅ |

### 资料录入页 (materials.js) — 411 行

| 功能 | 状态 |
|------|------|
| 3 个 Workflow 卡片 (ASR / 课件 / EPUB) | ✅ |
| 拖拽上传区 | ✅ |
| 文件列表管理 | ✅ |
| 转录进度 (SSE 流式) | ✅ |
| 解析进度 | ✅ |
| EPUB 导入 | ✅ |
| 已有文件侧边栏 | ✅ |
| 自动 AI 摘要 | ⚠️ 待验证 |
| AI 修正并排对比 | ⚠️ 待验证 |
| Tab 切换保持状态 | ⚠️ 待验证 |

### 复习问答页 (review.js) — 686 行

| 功能 | 状态 |
|------|------|
| 资料 Tab 列表 (提纲/笔记/结构图/题库) | ✅ |
| Markdown + KaTeX + Mermaid 渲染 | ✅ |
| 生成弹窗 (资料类型多选 / 附加要求) | ✅ |
| SSE 流式生成预览 | ✅ |
| 知识库构建按钮 (含进度) | ✅ |
| 聊天面板 (消息列表 / 流式回复) | ✅ |
| 来源引用显示 | ⚠️ 待验证 |
| 重新生成 (风格变化) | ⚠️ 待验证 |
| 导出对话 | ⚠️ 待验证 |
| 知识库未就绪时禁用输入 | ⚠️ 待验证 |

---

## 三、待完成 (Phase 4-7)

### 🔴 高优先级 — 功能验证与修复

1. **端到端测试** — 真实运行一遍完整用户流程
   - 创建课程 → 上传音频 → ASR 转录 → 上传课件 → 解析 → 生成复习资料 → RAG 问答
2. **SSE 重连机制** — 长生成任务中断后自动恢复
3. **错误处理** — 所有 API 错误在前端有友好提示
4. **空状态与加载态** — 确保每个页面都有合理的空/加载/错误三态

### 🟡 中优先级 — UI 打磨

5. **响应式布局** — 手机端适配 (目前仅有桌面布局)
6. **Toast 通知完善** — 目前组件存在但使用覆盖率不完整
7. **Modal 弹窗组件** — 计划中但未独立实现 (确认删除等操作目前用原生 confirm)
8. **chat.css / modal.css / toast.css** — 计划中的独立 CSS 文件

### 🟢 低优先级 — 工程完善

9. **前端测试** — 目前前端零测试覆盖
10. **API 路由测试** — 后端新 API 缺少单元测试
11. **streamlit 旧页面清理** — `pages/` 目录下的 `.py` 文件仅 streamlit 模式需要，与新的 SPA 架构重复
12. **Tauri 打包准备** — 计划中但未开始

---

## 四、技术债务

| 债务 | 说明 | 建议 |
|------|------|------|
| `src/api/review_api.py` 仅 34 行 | 已被拆分为多个路由文件，保留仅为兼容 `run.py` 中的 streamlit 模式 | 待 streamlit 废弃后删除 |
| `pages/` 目录 | Streamlit 旧 UI，与新 SPA 功能完全重复 | 在 Phase 7 中清理 |
| `frontend/dist/` 未提交 | 需 `npm install && npm run build` 生成 | 已在 .gitignore 中排除 |
| `node_modules/` 未提交 | 需 `npm install` | 已在 .gitignore 中排除 |
| LaTeX 扫描器 JS 移植 | 从 Python `_scan_math_delimiters` 移植到 `markdown.js` | 需用真实内容验证渲染正确性 |

---

## 五、下次开发建议 (优先级排序)

### Sprint 1: 验证与修复 (预计 2-3h)

1. 在有 `node` 环境的电脑上 `npm install && npm run build`
2. 用真实课程数据跑通全流程
3. 修复 SSE 断连问题
4. 补全 toast/modal 组件
5. 响应式布局适配

### Sprint 2: 测试补全 (预计 1-2h)

6. 后端 API 集成测试 (FastAPI TestClient)
7. 前端关键路径的 E2E 测试

### Sprint 3: 发布准备 (预计 1-2h)

8. 更新 README 文档 (去除 streamlit 启动方式，改为 npm+uvicorn)
9. 清理 streamlit 旧页面
10. 版本号 bump 到 v1.0.0
11. 合并到 main 并打 tag
