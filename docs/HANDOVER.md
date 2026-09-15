# 交接文档 · AI Knowledge Structuring Agent

> 生成时间：2026-09-12（Asia/Shanghai）；2026-09-12 晚更新：RAG 链路落地
> 项目路径：`D:\X\codex项目`
> 用途：新开的 Codex 对话或新同事接手时的唯一入口文档。
> 阅读顺序：`AGENTS.md` → `README.md` → 本文档 → `docs/architecture/README.md`

## 0. 一句话现状

闭环已经打通：上传 → 解析 → 内容块入库 → 向量索引（ChromaDB）→ 知识结构（节点/边/证据入库）→ 点击节点提问 → 带引用来源的回答或拒答，全部可在 `http://localhost:3000` 上跑通。

当前是“无模型 Key 也能跑”的降级状态：`EMBEDDING_PROVIDER=deterministic`（本地哈希向量）和文档结构
降级（`tree_mode=structure_fallback`）、原文摘录降级（`answer_mode=extractive_fallback`）。配置
`OPENAI_API_KEY` / `OPENAI_MODEL` 后，知识抽取与问答会自动切换到真实模型，引用校验与拒答策略不变。

下一步的核心工作是配置模型 Key 做真实质量验证，并补齐编辑、检索问答之外的 M4/M5 内容。

## 1. 项目目标与核心闭环

AI 驱动的文档理解与知识探索系统：用户上传 PDF / DOCX / PPTX 等非结构化资料，系统解析为带来源定位的内容块，生成可编辑的知识结构，并提供带证据引用的节点问答。

核心闭环：`上传文件 → 文档处理 → 知识结构 → 证据核验 → 节点问答`

硬性产品原则（详见 `AGENTS.md`）：不是摘要工具；任何没有来源、不可验证的模型结论都不能作为产品结果展示。

## 2. 进度总览（对照 8 周路线图）

路线图来源：`C:\Users\X\Desktop\Workspace\AI_Knowledge_Structuring_Agent_PRD_and_Roadmap.docx`

| 里程碑 | 目标交付物 | 当前状态 |
| --- | --- | --- |
| M0 · 产品基线 | PRD、用户旅程、数据模型、路线图 | 已完成（docx 已交付） |
| M1 · 可用流水线 | 上传、PDF/DOCX 解析、内容块、异步状态面板 | 完成：上传 ✅、解析 ✅、Celery Worker ✅、内容块入库 ✅、前端状态 ✅ |
| M2 · 知识结构 | 主题树、证据绑定、详情、基础编辑 | 基本完成：抽取 ✅、节点/边入库 ✅、接口 ✅、证据绑定 ✅、前端详情 ✅、人工编辑 ❌ |
| M3 · 可信问答 | 节点 RAG、引用跳转、拒答 | 完成主体：切分 ✅、Embedding ✅、Chroma ✅、Retriever ✅、节点问答 ✅、引用 ✅、拒答 ✅；点击引用跳转到原文位置 ❌ |
| M4 · 体验打磨 | 关系图、搜索、缓存、埋点 | 未开始 |
| M5 · Demo/简历 | 部署、演示工作区、指标看板 | 未开始 |

## 3. 已完成的工作（含交付物与验证情况）

### 3.1 产品与架构设计（2026-07-30）

- 交付物（均在桌面 Workspace）：`AI_Knowledge_Structuring_Agent_PRD_and_Roadmap.docx`（PRD、用户流程、核心功能、MVP 范围、技术难点、架构、8 周路线图）、`架构逻辑.docx`、`知识树项目.docx`。
- 架构结论：Next.js 前端 → FastAPI 网关 → 异步任务队列 → 文档解析管线 → LangGraph Agent → 向量库；同步请求快速返回，耗时解析与模型调用一律异步；所有 AI 结论绑定原始证据。

### 3.2 仓库骨架（2026-08-13）

- 建立 monorepo 分层：`frontend/`、`backend/`、`infra/`、`scripts/`、`docs/`。
- `AGENTS.md` 作为长期约束（架构边界、编码规范、Git 规范、测试要求、Agent 原则、架构变更控制）。
- `docker-compose.yml` 编排 7 个服务；`scripts/start.ps1`、`scripts/stop.ps1`；`.env.example` 环境变量模板。
- 注意：该次会话环境没有 Docker CLI，骨架只做了静态校验，未真正启动。

### 3.3 文件上传（2026-08-19）

- 后端 `POST /api/v1/uploads`：只接受 PDF / DOCX；同时校验扩展名与文件内容签名（PDF 头 `%PDF-`、DOCX 的 `word/document.xml`）；默认 25 MB 上限；生成 UUID 存储键并写入 `UPLOAD_DIR`；统一错误响应。
- 前端上传页 `UploadPanel`：选择文件、上传中/成功/失败状态、前端预拦截不支持的类型。
- 主要文件：`backend/app/api/routes/uploads.py`、`backend/app/services/upload_service.py`、`backend/app/schemas/uploads.py`、`frontend/src/features/uploads/UploadPanel.tsx`、`frontend/src/lib/api/uploads.ts`。
- 验证：后端 5 个测试通过（PDF、DOCX、伪装文件、不支持的格式、大小限制）；前端测试文件已写，当时因环境策略未能执行，后在 2026-09-12 补跑通过。

### 3.4 文档处理 / 文档解析（2026-08-19）

- 设计成可扩展解析管线，而不是在服务里按文件类型写死分支。
- 统一契约 `ProcessedDocument { title, sections[], metadata }`；每个 `DocumentSection` 带 `level`、`text` 和 `SourceLocation`（`page_number` 或 `paragraph_index`）。
- `PdfDocumentParser` 用 PyMuPDF，按页输出 section 并保留页码；`DocxDocumentParser` 用 python-docx，按 Heading 层级输出 section 并保留段落索引。
- `DocumentParserRegistry` 负责扩展名到解析器的注册与解析，新增 PPTX 只需新增解析器并注册。
- 主要文件：`backend/app/schemas/documents.py`、`backend/app/pipelines/document_processing/{contracts,registry,service,errors}.py`、`.../parsers/{pdf_parser,docx_parser}.py`。
- **该模块刻意没有暴露 HTTP 接口**：按架构约束，解析应由 Worker 调用，不能放在 HTTP 请求里。

### 3.5 知识抽取（2026-08-19 起草，2026-09-12 完成）

- LangGraph 单节点工作流：Prompt 构建 → 结构化 LLM 输出 → Pydantic 二次校验；LLM 无工具权限，文档内容视为不可信输入。
- 版本化 Prompt：`knowledge-tree-v1`（`backend/app/agents/knowledge_extraction/prompts.py`）。
- 输出 Schema：`KnowledgeTree` / `KnowledgeNode`（递归子节点、关键词、summary、`source_section_indexes` 证据索引），见 `backend/app/schemas/knowledge_tree.py`。
- 生产工厂 `factory.py` 使用 `ChatOpenAI(...).with_structured_output(KnowledgeTree, method="json_schema", strict=True)`，缺少 `OPENAI_API_KEY` / `OPENAI_MODEL` 时直接抛错。
- 验证：本地 `pytest` 全量通过；测试使用确定性假模型，不需要 API Key，也不发真实网络请求。

### 3.6 知识地图前端（2026-09-12）

- 独立 feature `frontend/src/features/knowledge-map/`，直接消费后端 `KnowledgeTree` JSON，前端不生成也不改写知识内容。
- `graph.ts`：纯函数把知识树转成 React Flow 的 nodes/edges（可单测）；`KnowledgeMap.tsx`：容器，管理展开状态与选中节点；`KnowledgeMapNode.tsx`：自定义节点与展开/收缩按钮；`KnowledgeNodeDetails.tsx`：摘要、关键词、来源 section 详情。
- 交互能力：展示节点、展开/收缩、点击查看详情、拖动缩放与 fit view。
- 验证：Vitest 通过（含上传测试）。期间修复了两个既有测试问题：Vitest 的 JSX 转换改为自动运行时、测试之间补充 DOM 清理。
- **尚未接入页面**：`frontend/src/app/page.tsx` 目前只渲染 `UploadPanel`。

### 3.7 Docker 环境（2026-09-12 实际跑通）

- 7 个服务全部成功启动并验证：frontend 3000、backend 8000、worker(Celery)、postgres 5432、redis 6379、chromadb 8001、minio 9000/9001。
- 过程中修复的问题：
  - `backend/.pytest_cache` 的 Windows 权限问题导致 Docker 构建上下文读取失败 → 已取所有权并删除，`.dockerignore` 已忽略 `__pycache__/`、`.pytest_cache/` 等。
  - `frontend/pnpm-workspace.yaml` 内容错误导致 `ERROR packages field missing or empty` → 已删除，且**不允许再创建**。
  - 前端 `node_modules` 重装成功（242 个包，Next.js 15.2.4），并保存在 `frontend_node_modules` 数据卷里，避免 Windows 与 Linux Alpine 的兼容问题。

### 3.8 RAG 检索问答链路（2026-09-12 晚）

设计文档：`docs/adr/0001-rag-pipeline.md`（决策、替代方案、迁移与回滚、降级模式）。

- **分块**：`backend/app/pipelines/chunking/`，段落优先 + 超长窗口重叠切分，保留
  `section_index`、`chunk_index`、页码/段落号与字符偏移，chunk id 由 `uuid5` 确定，可重复索引。
- **Embedding**：`backend/app/embeddings/`，默认 `deterministic`（哈希词袋、L2 归一化，无需 Key）；
  配置 `EMBEDDING_PROVIDER=openai` 时使用 `OPENAI_EMBEDDING_MODEL`。
- **向量库**：`backend/app/vectorstores/chroma_vector_store.py`，按 `document_id` 元数据过滤查询，
  向量库只是派生索引，正文与引用一律从 PostgreSQL 读取。
- **检索**：`backend/app/retrieval/retriever.py`，文档范围 + 节点证据加权 + 最低分阈值过滤。
- **回答**：`backend/app/agents/node_qa/`，LangGraph 两节点（生成草稿 → 校验引用）。模型引用了不存在的
  内容块 id 时，答案会被直接降级为拒答；无模型 Key 时走原文摘录降级。
- **持久化**：`documents`、`content_chunks`、`knowledge_nodes`、`knowledge_edges`、`evidence_links`、
  `questions` 六张表，`evidence_links` 是节点、边与回答链接回内容块的唯一证据实体。
- **Worker**：`backend/app/workers/tasks.py` 三个任务（`documents.index`、`documents.build_knowledge_tree`、
  `questions.answer`），HTTP 层只负责入队与查询状态。
- **前端**：`frontend/src/features/workspace/DocumentWorkspace.tsx` 串联上传→索引→知识树，
  `frontend/src/features/knowledge-map/KnowledgeNodeQa.tsx` 负责节点提问、轮询、回答与引用展示。
- **验证**：后端 35 个测试通过；前端 8 个测试通过、`tsc --noEmit` 无错误；真实链路冒烟脚本
  `scripts/smoke_rag_pipeline.py` 在 Docker 栈内跑通（上传 → 2 个内容块 → 2 个顶层节点 → 带 2 条引用的回答）。

### 3.9 扫描件 OCR 与失败原因提示（2026-09-12 晚）

起因：用户上传了一份 25 页扫描版 PDF（每页一张整图、文字层 0 字符），页面只显示英文
`The document contains no extractable text.`，既无法继续也无法判断原因。分两步处理：

1. **结构化错误码**：解析器区分“无文字层”，写入 `documents.error_code`（`no_text_layer` /
   `unsupported_format` / `processing_failed`），前端 `frontend/src/features/workspace/documentErrors.ts`
   翻译成可操作的中文提示；技术细节仍保留在 `error_message`。
2. **OCR 回落**：`backend/app/pipelines/document_processing/ocr.py` 对文字层不足的页面按 `OCR_DPI` 渲染，
   交给 Tesseract（默认 `chi_sim+eng`）识别；`OCR_MAX_PAGES` 限制成本，单页失败只记日志不中断。识别页数
   记录在 `documents.ocr_page_count`，界面提示“该文件是扫描件，其中 N 页已通过 OCR 识别”。

- 新增依赖：`pytesseract`、`Pillow`（pip）与 `tesseract-ocr`、`tesseract-ocr-eng`、`tesseract-ocr-chi-sim`
  （系统包，位于 `backend/Dockerfile`）。改动这部分需要重建 backend/worker 镜像。
- 实测：同一份 25 页扫描件重新处理，69.3s 完成 OCR（25/25 页），生成 26 个内容块，知识树与带引用回答均正常
  （引用定位到 p.15）。OCR 文本可读但存在噪声（原扫描件密度高、含图表）。
- 已知限制：知识树构建会重新解析文件，扫描件因此会二次 OCR；后续可缓存解析结果。

### 3.10 思维导图化改造（2026-09-12 晚，用户调试反馈）

用户实测后提出四条改进，均已落地：

1. **弹窗展示**：知识地图不再铺在上传区下方，改为全屏对话框（`KnowledgeMapDialog.tsx`，Esc 或按钮关闭）。
2. **滚轮交互**：画布支持滚轮平移、Ctrl+滚轮缩放、拖拽平移，另有「展开全部 / 收起全部」按钮。
3. **两个入口**：上传成功后给出「生成思维导图」（只看结构）与「生成知识地图」（结构 + 搜索 + 问答）
   两个选项，共用同一棵树，切换视图不需要重新处理文档。
4. **章节层级结构**：解析阶段改为识别文档自身大纲：
   - DOCX 综合三种信号得到层级：Word 标题样式（Heading 1/2/…、标题 1/2/…）、显式大纲级别
     （`w:outlineLvl`）、以及作者手写的编号（`第X章` / `一、` / `（一）`）；编号优先，因为学生论文常把章节
     标题统一设成 Word 的 `Title` 样式，单看样式名会把整篇塌成一个「前言」节点；
   - DOCX 的文档标题按 `docProps` → 开头标题行 → 文件名依次回退，不再直接用文件名当思维导图的根节点；
   - PDF 优先用内嵌书签（`get_toc`）；
   - 无书签时按 `第X章` / `一、` / `（一）` / `1.1` 等编号识别标题，字号作为辅助信号；
   - 目录页（点导线或整行页码）会被跳过，重复标题会去重；都识别不到时回退为按页分节。
   结果在 `DocumentMetadata.structure_source` 标注（`docx_headings` / `pdf_outline` /
   `detected_headings` / `pages`）。

知识树随之改为按层级嵌套：根节点是文档标题，一级节点是章节，二级及以下继续下钻；章节节点的证据覆盖其整个子树，
因此在章节节点提问也能检索到子节点内容。前端新增 `layout.ts`（父节点对子节点居中的布局）、
`search.ts` + `NodeSearch.tsx`（节点搜索、命中高亮与定位）、`KnowledgeMapDialog.tsx`（弹窗与两种模式）。

实测：用户那份 25 页扫描件重新处理后结构为「前言 → 第一章…第五章（各含 一、二、三 小节）」，目录页重复章节已消除；
后端 51 个测试、前端 22 个测试通过。

### 3.11 摘要、关键词与前端可见性修复（2026-09-13）

用户第二轮反馈（截图里看到的仍是旧界面）暴露了两个问题：

1. **前端改动没生效**：`frontend/` 是 Windows 目录挂载进容器，Next.js dev server 的文件监听收不到宿主机改动，
   浏览器一直拿到旧包。已在 `docker-compose.yml` 的 frontend 服务增加 `WATCHPACK_POLLING=true` 与
   `CHOKIDAR_USEPOLLING=true`（只加环境变量，未改 command 与卷映射，改完已跑 `docker compose config`）。
   排查方法：在容器内 `ls /app/src/...` 能看到新文件、但页面 chunk 里搜不到新文案，即为此类问题；此时
   `docker compose restart frontend` 并强制刷新浏览器即可。
2. **节点内容与关键词**：结构降级模式下节点摘要原先直接截取 240 字原文，关键词为空。新增
   `backend/app/agents/knowledge_extraction/text_digest.py`：
   - `summarize` 用词频质心选出“最能代表该节的完整一句话”（上限约 80 字），不再照抄整段；
   - `extract_keywords` 基于中文边界切分 + n-gram + 文档词频提取关键词，过滤虚词、数字碎片与已被整体表示的短语；
   - `has_content` 识别 OCR 只留下页码的碎片，这类内容不再生成“摘要：-17-”，而是回落到“该章下含 N 个小节”。
   配置真实模型后，摘要与关键词由模型生成，schema 校验不变。

### 3.12 节点放大视图（2026-09-13）

反馈：节点卡片里的摘要会被两行截断，长内容看不全。新增 `KnowledgeNodeDialog.tsx`：

- 双击任意节点（卡片底部有“双击放大查看完整内容”提示）弹出放大窗口，完整展示节点标题、完整摘要、关键词、
  来源章节；知识地图模式下窗口内还带提问面板。
- 窗口层级高于知识地图弹窗（z-60），Esc 只关闭放大窗口、不会连带关掉地图（地图的 Esc 监听在放大窗口打开时会让路）。
- 地图画布关闭了 `zoomOnDoubleClick`，避免双击被当成画布缩放。

测试：`KnowledgeNodeDialog.test.tsx`（完整摘要、关键词、来源、模式差异、Esc 关闭）与 `graph.test.ts`
中的双击回调连线测试；前端 26 个测试通过，`tsc --noEmit` 无错误。

### 3.13 扫描件识别精度调优（2026-09-13）

反馈：扫描件里「（三）特色化」被识别成「（三）REM」，「（二）」整节丢失（序号从一直接跳到三）。
用 `scripts/ocr_quality_probe.py` 在同一份文件的第 5、6、10、11、12 页上对比了四种配置，结论：

- **300 DPI 是关键**：同一页 200 DPI 识别为「(三) REM: 另辟独特路径」，300 DPI 识别为「(三) 特色化: 另辟独特路径」；
  「(二) 精细化; BERGA, WHR STA」在 300 DPI 下变为「(二) 精细化: 追求卓越品质，弘扬匠心打造精细标」。
- 二值化（`OCR_BINARIZE`）在不同页面互有胜负，默认关闭；`OCR_PSM` 默认 3。
- **丢掉的「（二）」其实是 OCR 把“二”读成了「=」**（原文行为「(=) 梯度赋能筑数转格局…」）。因此标题识别把
  `=`、`I`、`l`、`|`、`≡` 也当作数字处理，`（=）xxx` 现在能正确识别为（二）级标题。

改动：`ocr_dpi` 默认 200 → 300，新增 `OCR_PSM` / `OCR_BINARIZE` / `OCR_BINARIZE_THRESHOLD`；
OCR 渲染与二值化统一收进 `ocr.py`（`OcrEngine.extract_page_text`）；`headings.py` 放宽括号编号识别。
代价：300 DPI 让扫描件处理变慢（约 1.5–2 倍）；如遇性能问题可把 `OCR_DPI` 调回 200。

### 3.14 双 DPI 择优与序号还原（2026-09-13）

上一步改成 300 DPI 后出现新问题：同一份扫描件里 300 DPI 能认出「(三) 特色化」，却把「第四章」整章丢了
（200 DPI 反而认得）。逐页对比确认 **OCR 精度对 DPI 的敏感度是按页变化的**，单一 DPI 必然顾此失彼。

解法（`ocr.py`）：

- `OCR_FALLBACK_DPI`（默认 200）对每页再跑一遍，用 `ocr_text_score` 择优：先比“第X章”数量，再比“一、/（一）”
  数量，最后比中文字数。这样第 5、6 页取 300 DPI 的高质量文本，第 11、21 页取 200 DPI 才有的「(=)」「第四章」。
- 标题渲染前做序号还原（`headings.py`）：括号内的 `=`→二、`I/l/|`→一、`≡`→三，导出标题里显示为
  「(二) 梯度赋能…」而不是「(=) …」；正文不受影响。
- 收紧小数编号规则：`1.1 总体架构` 仍是标题，但正文里的「2.6 倍; 研发人员占比达 25.1%」不再被误判成节点。

实测（同一份 25 页扫描件）：第一章的四级标题为「(一)专业化 / (二)精细化 / (三)特色化 / (四)创新能力」，
第一章第二节补齐「(二) 创新成效逐年增强」，第一章第三节补齐「(二) 梯度赋能筑数转格局」，第四章完整保留。
后端 67 个测试通过。

代价与开关：双 DPI 让扫描件索引时间从约 96s 增加到约 166s（25 页），建树同理；把 `OCR_FALLBACK_DPI` 留空
即可关闭第二遍、退回单一 DPI。仍存在的局限：个别标题字符会被 OCR 认错（内洒/内涵、骨入/嵌入、挖气/挖掘），
这类字符级错误需要在 Tesseract 之外引入更强的中文识别模型或模型后处理。

### 3.15 节点内容与三级/四级结构（2026-09-13）

用户第二轮结构反馈的五点，逐条处理：

1. **定义句优先**：`text_digest.summarize` 现在会先剥掉 OCR 粘在段首的杂字（「业 专业化是指…」「地 创新能力是指…」），
   并对含「是指 / 指的是 / 即为 / 定义为」的句子加权，让节点摘要以定义开头（专业化/特色化/创新能力均已验证）。
2. **补齐漏点**：括号编号允许内部空格，`(三 ) 社会贡献持续活跃` 不再被漏判，「总体态势」恢复为（一）(二)(三)(四) 四点。
3. **标签型三级节点**：新增 `split_label_heading`，把文中作为小标题使用的「传统发展痛点:」「数智化赋能路径:」
   「数智化赋能成效:」「典型案例:」识别为 3 级节点，冒号后的内容作为该节点正文；阿拉伯编号 `(1)(2)(3)`
   统一为 4 级，挂在对应标签节点下（第二章各节因此能看到痛点/路径/成效/案例的层级）。
4. **章标题丢失**：新增 `looks_like_unlabelled_chapter_opener`，当某行短、无编号、且**紧跟一/二/三编号小节**时，
   判为章开头；并用 `next_chapter_prefix` 依据前一章序号补出「第六章」。实测「SAB 数智致远，璧画专精特新发展新图景」
   被正确还原为「第六章 数智致远，璧画专精特新发展新图景」，其下三节不再挂在第五章。
5. **概括 vs 摘抄**：当前无模型 Key，摘要是**抽取式**（选原文中最具代表性的整句，优先定义句），不是改写式概括；
   关键词同样是抽取式。真正的“用自己的话概括”需要配置模型：`.env` 里设置 `OPENAI_API_KEY` +
   `OPENAI_MODEL`（DeepSeek 等 OpenAI 兼容端点再设 `OPENAI_BASE_URL=https://api.deepseek.com`），
   重启 backend 与 worker 后知识抽取与关键词改由模型生成，`knowledge-tree-v2` 提示词已要求按文档大纲组织节点。

验证：后端 78 个测试通过；扫描件最终结构为「前言 + 第一章…第六章（各 3 节）」，第一章的（一）(二)(三)(四)、
第二章的痛点/路径/成效/案例、第六章的三节均已就位。仍存在 OCR 字符级噪声（内洒/内涵、骨入/嵌入、挖气/挖掘）。

### 3.16 接入真实模型（DeepSeek）：结构来自文档、内容来自模型（2026-09-13）

用户提供了 DeepSeek Key。接入过程中的三个关键点：

1. **DeepSeek 不支持 OpenAI 的严格 JSON Schema 输出**。新增 `app/agents/llm.py` 的
   `resolve_structured_output_method()`：`LLM_STRUCTURED_OUTPUT=auto` 时，base_url 是 OpenAI 就用
   `json_schema`（strict），其它兼容端点自动改用 `function_calling`。
2. **不能让模型决定结构**。早期做法是把整份文档丢给模型产出整棵树，结果第一章被提到根层、第六章被并进第五章。
   现在改为两段式：`build_structural_tree` 用解析器得到确定性的章节骨架，模型只通过
   `knowledge_extraction/enrichment.py` 改写每个节点的摘要/关键词，并可**在受限条件下**修正标题
   （编号前缀必须一致、长度差 ≤4、相似度 ≥0.6），因此地图不会再偏离文档。
3. **模型输出要多容忍**：DeepSeek 的函数调用会附带额外字段，原先 `extra="forbid"` 会让整批校验失败并静默回退。
   模型输出的 schema（深度知识树 / 答案草稿 / 节点富化）已改为 `extra="ignore"`，必需字段仍严格校验。

配置（`.env`，勿提交）：`OPENAI_API_KEY=<key>`、`OPENAI_MODEL=deepseek-chat`、
`OPENAI_BASE_URL=https://api.deepseek.com`、`LLM_STRUCTURED_OUTPUT=auto`。Embedding 仍是
`deterministic`，因为 DeepSeek 没有 embedding 接口。

**重要坑**：`docker compose restart` 不会重新读取 `env_file`，改了 `.env` 必须 `docker compose up -d backend worker`
（本次就是因为只 restart 导致 worker 一直以为没有 Key，截图里看到 `structure_fallback`）。

测试隔离：新增 autouse fixture 在测试中清空 `OPENAI_API_KEY/OPENAI_MODEL/OPENAI_BASE_URL`，
确保单测永不真的调用付费模型。

实测（同一份 25 页扫描件）：`mode=llm`，结构为「前言 + 第一章…第六章（各 3 节）」，摘要为模型改写的一句话
（如「专精特新概念包含专业化、精细化、特色化与创新能力四个维度…」），关键词干净（专业化、精细化、特色化、
创新能力），标题错字被修正（内洒→内涵、挖气→挖掘、璧画→擘画）。

### 3.17 第二章节点归属修复（2026-09-13）

用户反馈：第二章「一」的 `(3) 系统匹配` 应属于「传统发展痛点」；「二」缺少路径与成效；「三」几乎所有标签都没生成。诊断结果三条：

1. **自己的去重逻辑误删**：`_deduplicate_sections` 原本对全层级同标题去重，而「传统发展痛点/数智化赋能路径/
   数智化赋能成效」在每节重复出现，于是只保留了第一次出现的那个。现在**只对一级标题去重**（用来消除页眉里
   重复出现的章名），子层级重复一律保留。
2. **标签被 OCR 认花**：`传统发展痛点`→`RRR RB`、`数智化赋能成效`→`BE ACN RE`。新增 `split_noise_label` +
   `repair_label`：噪声标签按“本节还缺哪个标签”的顺序（痛点→路径→成效）结合正文措辞（以「形成/构建/打造…」开头
   判为成效）还原。
3. **分隔符可能是分号**：`数智化赋能成效; 形成具备…` 之前不被识别，现在 `:` `：` `;` `；` 都接受。

另外「典型案例」在同一节出现多次会重名，现在标题带案例名（如「典型案例：长飞光纤一一工业互联网平台赋能全产业」）。

实测：第二章「一」= 传统发展痛点（其下挂 `(3) 系统匹配`）+ 数智化赋能路径（其下挂 `(3) 长效运营层面`）+
数智化赋能成效；「二」「三」四个标签（含典型案例）全部生成。后端 98 个测试通过。

### 3.18 平级编号小点补齐（2026-09-13）

用户指出：`(3) 系统匹配` 成了节点，但同级的 `(1) 知识传承`、`(2) 技术优化` 没有；并要求检查其它节点是否有同样问题。

原因有三：

1. **OCR 把多个小点挤在同一行**（`痛点: (1) 甲; (2) 乙`），只有换行后的 `(3)` 独占一行，所以只有它成为标题。
   新增 `split_inline_items`：在句末标点/冒号后遇到 `(N)` 就拆成独立行。
2. **OCR 把编号留在行尾**：`…促进技术沉淀; (2)` 后面另起一行才是正文。新增 `reattach_trailing_markers`
   把行尾编号移到下一行开头，小点才完整。
3. **标点规则过严**：小点常以分号结尾，被我“句末标点不算标题”的规则挡掉。现在只有 `。！？` 一律拒绝，
   `，；` 只对 1–3 级标题生效，编号小点（4 级）允许分号结尾。

另外：编号小点现在拆成「短标题 + 正文」（`(3) 系统匹配` + 正文），这样每个小点都有内容、能建索引、也能被模型概括；
不在标签块内的编号列举（如正文中的 `（1）`）仍作为普通正文，不生成节点。

实测（同一份扫描件）：第二章一/二/三 三节下的「传统发展痛点」「数智化赋能路径」现在各自带 `(1)(2)(3)` 三个小点，
且每个小点都有模型生成的一句话摘要与关键词（如 `(3) 系统匹配` →「系统匹配方面，通用数字化系统适配不足，工艺经验落地受阻，
技术“难复用”。」，关键词：系统匹配、通用数字化系统、适配不足）。后端 104 个测试通过。

### 3.19 Node AI Assistant 与 Node Context 机制（2026-09-13）

每个知识节点现在具备四种 AI 能力：**解释这个节点 / 举例说明 / 深入学习 / 生成测试问题**，另保留自由提问。

**Node Context 机制**（`backend/app/agents/node_qa/context.py`，设计见 ADR 0001 第 10 节）：

- 上下文内容：文档标题、从根到该节点的 outline 路径、节点标题/摘要/关键词、一层子节点（标题+摘要，≤8）、
  同级节点标题（≤6）、带标签的原文证据块（≤6，标签 `c1…cN` 对应 chunk id），以及截断记账字段。
- 五条不变量：证据优先（无证据直接拒答，不调模型）、标签稳定（模型必须引用标签，未知标签判为无效）、
  有界（默认 6000 字符，超出丢弃证据块而不是截断引文）、确定性（同节点同检索结果必得同上下文）、
  意图影响检索与指令但不放宽接地规则。
- 执行路径：`POST /knowledge-nodes/{id}/questions {intent, question?}` → 入库（记录 intent 与 prompt 版本）
  → Worker 检索（节点证据优先）→ 构建 Node Context → LangGraph（生成 → 校验引用/测试题）→ 持久化答案、
  测试题 payload 与证据链接 → `GET /questions/{id}` 返回。
- 降级：无模型时 explain/ask 返回原文摘录，quiz 依据子节点生成题目（每题带出处），API 标注 `answer_mode`。

实测（对「一、专精特新概念及内涵」执行四个意图，真实 DeepSeek）：
explain 用通俗语言解释并引用 c1/c2；example 按四个维度列举文档中的真实数据；deep_dive 输出结构化要点与
子节点分述；quiz 生成 5 道题（含参考答案与出处）。仅 quiz 意图返回测试题。

本轮还修了两个健壮性问题：模型输出超长（deep_dive 超过 2000 字）会触发 schema 校验失败，现在改为
**超长即截断而非报错**，并把上限放宽到 6000 字；模型调用异常会**把问题标记为 failed**，不再让前端无限轮询。
后端 117 个测试、前端 29 个测试通过。

### 3.20 多智能体重构（2026-09-13）

按用户要求把 AI 层从「各处单次 LLM 调用」重构为 **LangGraph 多智能体工作流**，设计见 `docs/adr/0002-multi-agent-architecture.md`。

五个 Agent（`backend/app/agents/workflow/`）：

| Agent | 职责 | 是否用模型 |
| --- | --- | --- |
| Planner | 分析任务、决定任务类型与执行步骤 | 可选（规则始终保证路由可执行） |
| Document Analyst | 解析文件、产出 digest/大纲/告警 | 否 |
| Knowledge Extraction | 生成大纲骨架 + 模型改写内容，并持久化节点与证据 | 配置后使用 |
| Visualization | 把已持久化节点转换为 `knowledge-map-v1` 视图模型并写入 `documents.map_model` | 否 |
| Tutor | 基于 Node Context 解释/举例/深挖/出题 | 配置后使用 |

工作流骨架：`START → planner → execute_step ─(还有步骤)→ execute_step / ─(完成或失败)→ END`；
State 用 `TypedDict`，每个 Agent 只写自己的 key，`traces`/`errors` 用 `operator.add` 追加形成执行日志。
关键安全约束：Planner 只能选已知路由（模型不能新增步骤）、循环有界、失败即停并记录、
**索引一致性校验**（若已存内容块与本次解析的章节标题不一致则先重建，避免节点绑到过期章节）。

实测日志（真实栈，用户那份扫描件）：
`planner(rules) → document_analyst 165271ms → knowledge_extraction 26784ms used_model=True → visualization 16ms`，
产出 73 个节点、最大深度 4、7 章、72 条边；无证据节点从 34 降到 2（`documents.map_model` 已落库）。
后端 127 个测试（新增 `tests/agents/test_workflow.py`：路由、仅分析、三 Agent 全链路、持久化、
Tutor 经由工作流、过期索引重建、失败短路）与前端 29 个测试通过。

### 3.21 QA 加固与风险清单（2026-09-13）

以 QA 视角补了四类测试，后端从 127 增至 **197**，前端从 29 增至 **48**，后端语句覆盖率 **94%**。

测试分布（`pytest --collect-only`）：agents 71、pipelines 53、api 23、services 9、repositories 9、
vectorstores 9、embeddings 7、workers 5、config/db/health 8。本轮新增的主要文件：
`tests/repositories/test_repositories.py`（幂等重建、证据作用域、问题生命周期）、
`tests/services/test_indexing_service.py`、`tests/services/test_upload_service.py`（路径穿越、大小边界、
容器校验）、`tests/vectorstores/test_chroma_adapter.py`（用假客户端验证 cosine/where/距离换算）、
`tests/workers/test_tasks_and_dispatch.py`（任务体与入队封装）、`tests/test_db_session.py`（提交/回滚）、
`tests/embeddings/test_embedding_factory.py`、`tests/api/test_api_contracts.py`（503/404/422/契约字段）、
`tests/agents/test_workflow_model.py`（Planner 模型细化与守卫、degraded、提示注入）、
`tests/agents/test_degraded_answers.py`、`tests/agents/test_answer_fallback_branches.py`；
前端新增 `NodeSearch.test.tsx`、`KnowledgeMapDialog.test.tsx`、`src/lib/api/api-clients.test.ts`，
并补齐 UploadPanel 失败路径与 DocumentWorkspace 失败/建树失败路径。

本轮 QA 抓到并修复的 3 个真实缺陷：

1. **Planner 的 `_refine` 方法被上一次编辑意外移出类体**，只要配置了模型且请求带 instruction 就会
   `AttributeError`；新增测试立即暴露，已修复。
2. **Planner 会接受请求无法执行的任务类型**（例如没有 node_id 却改判为 teach_node），现在用
   `can_execute()` 守卫，不可执行时回退规则路由。
3. **抽取式回答可能超出字数预算**（多出一整句），现在硬截断到预算内。

风险清单（按严重度，详见下文与 ADR）：

- **P0** 无鉴权与租户隔离；任务/模型调用无超时与重试，失败态可能永久停留；仓库无 git、无 CI；
  测试用 SQLite 而生产用 PostgreSQL；OCR 质量是精度上限（仍有 2 个节点无证据）。
- **P1** 成本与 token 无计量、无速率限制；上传件未接 MinIO/S3 且无保留策略；
  `knowledge_nodes` 缺 (document_id, path) 唯一约束，并发建树有竞态；大文档无页数/节点上限；
  前端关键交互（滚轮/拖拽/双击）无 E2E 覆盖。
- **P2** 依赖无自动更新（langgraph 0.x）；无 tesseract 的环境会静默跳过 OCR 用例；
  前端无错误上报；`documents.map_model` JSON 随树规模增长。

### 3.22 P0-2 任务超时 / 重试 / 僵尸回收（2026-09-13）

已按 QA 风险清单处理“失败态可能永久卡住”，改动如下：

1. **任务时间上限**：`documents.index` 与 `documents.build_knowledge_tree` 为 1800s 软 / 2100s 硬，
   `questions.answer` 为 120s / 180s，`maintenance.reap_stale_jobs` 为 60s / 120s（扫描件解析本来就慢，
   用 `OCR_MAX_PAGES` 约束单文档规模）。
2. **可靠投递**：Celery 开启 `task_acks_late`、`task_reject_on_worker_lost`、
   `worker_prefetch_multiplier=1`；worker 崩溃时任务回到队列而不是丢失。
3. **可重试分类**：新增 `app/workers/retry_policy.py`——超时/连接重置/限流/供应商 5xx 视为瞬时错误，
   按 `TASK_MAX_RETRIES` + 指数退避 + 抖动重试；schema 校验、错误 id、鉴权失败等永久错误不重试。
4. **模型超时**：四个 ChatOpenAI 工厂与 OpenAI Embeddings 都使用 `LLM_REQUEST_TIMEOUT_SECONDS` /
   `LLM_MAX_RETRIES`，避免一次调用挂死占满 worker 槽位。
5. **僵尸回收**：新增 `app/services/maintenance_service.py` 与 Celery beat 服务，
   每 `REAPER_INTERVAL_SECONDS`（默认 300s）把超过 `STALE_JOB_TIMEOUT_SECONDS`（默认 1800s）仍处于
   `indexing` / `building` / `running` 的文档与问题标记为 failed（`error_code=stale_job`），
   前端随即停止轮询。`questions.answer` 在最后一次重试后也会主动把问题标记为 failed。

运维方式：新增 `beat` 服务（`docker compose up -d beat`，写入 `/tmp/celerybeat-schedule`，不污染源码目录）；
手动回收：`docker compose exec -T worker python -c "from app.workers.tasks import reap_stale_jobs_task; print(reap_stale_jobs_task())"`。

验证：后端 **215** 个测试通过（新增 `tests/services/test_maintenance_service.py` 覆盖卡死文档/问题/新鲜任务/
幂等，`tests/workers/test_task_reliability.py` 覆盖时间上限、acks_late 配置、退避重试注解、beat 计划、
瞬时错误分类、最终重试标记）；`docker compose config` 通过；worker 任务清单已包含
`maintenance.reap_stale_jobs`；beat 已启动并按 300s 间隔调度；手动回收返回 `{'documents_failed': 0, 'questions_failed': 0}`。

风险清单更新：**P0-2 已关闭**。仍待处理：P0-1 鉴权与租户隔离、P0-3 git+CI、
P0-4 测试库与生产库不一致（SQLite vs PostgreSQL）、P0-5 OCR 精度上限。

## 4. 代码地图（关键文件职责）

### 后端

| 文件 | 职责 |
| --- | --- |
| `backend/app/main.py` | FastAPI 应用装配、CORS、`/health`、挂载 `/api/v1` 路由 |
| `backend/app/api/router.py` | API 路由聚合（uploads / documents / questions） |
| `backend/app/api/routes/uploads.py` | 上传接口薄层：校验 → 调 service → 返回 schema（同时写入 documents 行） |
| `backend/app/api/routes/documents.py` | 处理触发、状态查询、知识树触发与查询 |
| `backend/app/api/routes/questions.py` | 节点提问与问答结果查询（均不在请求内跑模型） |
| `backend/app/core/config.py` | Pydantic Settings，读取 `.env` |
| `backend/app/db/` | SQLAlchemy 引擎、会话边界（`get_session` / `session_scope`）与 Base |
| `backend/app/models/` | 六张表的 ORM 模型（documents / content_chunks / knowledge_nodes / knowledge_edges / evidence_links / questions） |
| `backend/app/repositories/` | 文档、内容块、知识树、证据、问题的数据访问层 |
| `backend/app/schemas/` | API 与模块边界的数据契约（uploads / documents / knowledge_tree / knowledge_tree_api / pipeline / answers） |
| `backend/app/services/upload_service.py` | 上传校验、大小限制、落盘、写入 documents 行、错误语义 |
| `backend/app/pipelines/document_processing/` | 文件 → 结构化文本的解析管线（契约、注册表、服务、错误、PDF/DOCX 解析器） |
| `backend/app/pipelines/chunking/` | 章节 → 内容块（窗口重叠、字符偏移、确定性 chunk id） |
| `backend/app/pipelines/document_processing/headings.py` | 标题识别（编号 + 字号）、目录页判断、标题去重 |
| `backend/app/embeddings/` | Embedding Provider（deterministic 默认 / OpenAI 兼容） |
| `backend/app/vectorstores/` | 向量库契约、ChromaDB 适配器、内存实现（测试用） |
| `backend/app/retrieval/` | 文档范围检索 + 节点证据加权 + 阈值过滤 |
| `backend/app/agents/knowledge_extraction/` | LangGraph 知识抽取（prompts / contracts / factory / agent） |
| `backend/app/agents/node_qa/` | 节点问答 LangGraph（prompts / contracts / agent / factory / 摘录降级） |
| `backend/app/services/indexing_service.py`、`knowledge_tree_service.py`、`question_service.py`、`document_service.py` | 编排：索引、知识树、问答、文档状态 |
| `backend/app/workers/celery_app.py`、`tasks.py`、`dispatch.py` | Celery 应用与三个任务，以及 HTTP 层入队封装 |
| `backend/alembic/`、`backend/alembic.ini` | 迁移环境与 `952757ab67fb` 初始迁移（六张表） |
| `backend/tests/` | pytest：health、uploads、document_processing、knowledge_extraction、chunking、embeddings、retrieval、node_qa、rag_pipeline |

### 前端

| 文件 | 职责 |
| --- | --- |
| `frontend/src/app/page.tsx` | 首页，渲染 `DocumentWorkspace` |
| `frontend/src/features/workspace/DocumentWorkspace.tsx` | 上传 → 索引 → 知识树的编排与轮询、右侧详情/问答栏布局 |
| `frontend/src/features/knowledge-map/layout.ts` | 思维导图布局（父节点居中于子节点），可单测 |
| `frontend/src/features/knowledge-map/KnowledgeMapDialog.tsx` | 全屏弹窗与「思维导图 / 知识地图」两种模式 |
| `frontend/src/features/knowledge-map/NodeSearch.tsx`、`search.ts` | 节点搜索、命中高亮与定位 |
| `frontend/src/features/uploads/UploadPanel.tsx` | 上传 UI 与状态反馈，成功回调交给 workspace |
| `frontend/src/features/knowledge-map/` | 知识地图（graph 转换、容器、节点、详情面板、节点问答、类型） |
| `frontend/src/lib/api/client.ts`、`uploads.ts`、`documents.ts`、`questions.ts` | API 客户端（上传、文档状态、知识树、问答） |
| `frontend/vitest.config.ts` | jsdom 环境、自动 JSX、`@` 别名 |

### 工程与运行

| 文件 | 职责 |
| --- | --- |
| `docker-compose.yml` | 7 服务编排（含 `frontend_node_modules`、`backend_upload_data` 等数据卷） |
| `scripts/start.ps1` / `stop.ps1` | 本地启动 / 停止 |
| `.env.example` | 环境变量完整模板（无敏感值） |
| `AGENTS.md` | 所有开发工作的长期约束 |

## 5. 尚未完成的工作（建议按此顺序推进）

### P0 · 打通核心闭环（已完成）

（已完成，保留记录）Worker 任务、知识抽取编排、对外接口、前端接线都已实现并通过真实链路验证。

### P0-2 · 配置真实模型并做质量验证（建议下一个任务）

1. 在 `.env` 填入 `OPENAI_API_KEY` / `OPENAI_MODEL`（可选 `OPENAI_BASE_URL`，DeepSeek 等 OpenAI 兼容端点可直接使用），`EMBEDDING_PROVIDER` 视情况切换为 `openai` 并设置 `OPENAI_EMBEDDING_MODEL`。
2. 重启 backend 与 worker，重新上传一份真实文档，验证 `tree_mode=llm`、`answer_mode=llm` 下的抽取质量与引用准确率。
3. 用脱敏样本文档建立评测集：检索命中率、引用正确率、拒答正确率。

### P1 · 持久化（部分完成）

- 已完成：六张表 + Alembic 迁移 + 仓储层；节点、边、回答都通过 `evidence_links` 关联到内容块。
- 未完成：上传文件仍写在本地磁盘 `UPLOAD_DIR`，尚未接入 MinIO/S3；缺少人工修订节点的接口与版本历史。

### P2 · 检索与问答（主体完成）

- 已完成：分块、Embedding、ChromaDB 索引、节点范围检索、引用、拒答。
- 未完成：引用跳转（点击引用在原文阅读器中定位）、多轮对话、跨文档/工作区检索、重排序模型。

### P3 · 工程化

- **项目目前没有 git 仓库**（`D:\X\codex项目` 下没有 `.git`），所有改动没有版本历史，建议尽快 `git init` + 首次提交，并按 `AGENTS.md` 使用功能分支。
- 补充 CI（lint、类型检查、测试）与脱敏样本文档评测集。

## 6. 硬性约束与已知的坑（务必遵守）

来源：`C:\Users\X\Desktop\Workspace\项目维护说明.docx` + 本次复核结果。

1. **禁止 `docker compose down -v`**：会删除 `frontend_node_modules`、`postgres_data`、`chroma_data`、`minio_data`、`backend_upload_data`，前端依赖与全部数据会一起丢失。
2. **禁止重建 `frontend/pnpm-workspace.yaml`**：该文件内容错误曾导致 `ERROR packages field missing or empty`，已删除；当前前端是独立 Next.js 项目。
3. **不要改动 `docker-compose.yml` 中 frontend 的 `command`**（`pnpm run dev --hostname 0.0.0.0` 已验证可用），也不要删除 `--hostname 0.0.0.0`。
4. **不要随意改 `frontend/Dockerfile`、`frontend/package.json`、`frontend/pnpm-lock.yaml`**，也不要动 `frontend_node_modules:/app/node_modules` 这行卷映射。
5. **不要为了修一个问题重写整个 compose 文件**：先 `docker compose ps` → `docker compose logs <service> --tail=100` → `docker compose config`，再做最小范围修改。
6. **每次改 compose 后先 `docker compose config` 验证 YAML**，再 `docker compose up -d`。
7. **跑后端测试时建议加 `-p no:cacheprovider`**，避免重新生成 `.pytest_cache`（历史问题：它曾导致 Docker 构建上下文读取失败）。
8. **前端依赖在 Docker 数据卷里**，Windows 主机目录下没有 `node_modules`；新增前端依赖请用 `docker compose run --rm frontend pnpm add <package>`，不要直接在宿主机装。
9. **运行时状态（2026-09-12 复核）**：Docker Desktop 当前**没有运行**；宿主机 Python 环境缺少后端依赖（`fastapi`、`pydantic`、`langgraph`、`fitz`、`python-docx` 等全部缺失），因此本地直接跑 `pytest` 会收集失败，需要先装依赖或在容器内跑。
10. **模型通道**：Codex 桌面端当前配置为 DeepSeek（`~/.codex/config.toml` 中 `model_provider = "deepseek"`）。7 月创建的那个旧对话仍把 provider 钉在 `openai`，而本机没有 OpenAI Key，因此续用旧对话会产生 `401 Missing bearer or basic authentication in header`；**新开对话即可正常使用**。
11. **数据库 schema 变更必须走 Alembic**：改完 `backend/app/models/` 后，用 `docker compose run --rm --no-deps backend alembic revision --autogenerate -m "<message>"` 生成迁移，再 `alembic upgrade head` 应用；不要用 `Base.metadata.create_all` 建表，也不要手改已应用的迁移。
12. **启动服务不会自动迁移**：compose 只负责拉起容器。换机器或新增表后，必须先跑一次 `alembic upgrade head`，否则接口会因为缺表报 500。
13. **保持降级可跑**：`.env` 没有模型 Key 时链路仍然要能跑（`tree_mode=structure_fallback` + `answer_mode=extractive_fallback`）。如果改动让无 Key 场景直接 500，视为回归。
14. **OCR 只改后端镜像即可**：Tesseract 装在 `backend/Dockerfile`。改 OCR 相关依赖后执行 `docker compose build backend worker` 再 `docker compose up -d backend worker`；前端镜像与 `frontend_node_modules` 卷不受影响。扫描件处理很慢（约 3 秒/页，全部在 Worker），不要把它挪进 HTTP 请求。
15. **Worker 不会热重载**：backend 用 `uvicorn --reload` 会自动加载代码改动，但 Celery worker 不会。改动 tasks、agents、services 等被 Worker 调用的代码后，必须 `docker compose restart worker`，否则 Worker 仍在跑旧代码（本次排查标题回退时就踩过这个坑）。
16. **PDF 根节点标题可能回退成文件名（已知限制，暂不实现，遇到同类问题先询问用户）**：`PdfDocumentParser._get_title` 只读 PDF 元数据标题，为空时直接用文件名。正文标题在首页常常折行（例如「欧盟-南方共同市场贸易协定的地缘经济博弈与 / 全球供应链重构效应」），照 DOCX 那样只取首行会得到一个被截断的标题，所以这里没有做首行回退。如果后续再遇到「PDF 上传后根节点显示文件名而不是正文标题」这类现象，**先询问用户是否需要解决**，再决定是否实现「按字号识别首页大标题并拼接折行」的方案。

## 7. 环境与常用命令

### 服务端口

| 服务 | 地址 / 端口 | 说明 |
| --- | --- | --- |
| frontend | http://localhost:3000 | Next.js 界面 |
| backend | http://localhost:8000 | FastAPI |
| Swagger | http://localhost:8000/docs | API 文档 |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| chromadb | 8001 | 向量库 |
| postgres | 5432 | `knowledge_agent` / `app` |
| redis | 6379 | 队列 |

### 启动与检查

```powershell
cd "D:\X\codex项目"
docker compose up -d          # 或 .\scripts\start.ps1（首次会自动从 .env.example 生成 .env）
docker compose ps             # 确认 7 个服务都是 Up
docker compose logs backend --tail=100
docker compose config         # 改过 compose 后必须先跑
```

### 测试

```powershell
# 数据库迁移（新增表或换机器后必须执行一次）
docker compose run --rm --no-deps backend alembic upgrade head

# 后端（镜像里默认没装 pytest/httpx，需临时装一次，不会写入宿主机）
docker compose run --rm --no-deps backend sh -c "pip install --no-cache-dir 'pytest>=8.3' 'httpx>=0.28' >/dev/null 2>&1; python -m pytest tests -q -p no:cacheprovider"

# 前端（若 pnpm 因安全策略拒绝执行构建脚本，直接跑二进制）
docker compose run --rm --no-deps frontend pnpm test
docker compose run --rm --no-deps frontend ./node_modules/.bin/vitest run
docker compose run --rm --no-deps frontend ./node_modules/.bin/tsc --noEmit

# 端到端冒烟：上传 → 索引 → 知识树 → 带引用回答
docker compose run --rm --no-deps -v "D:\X\codex项目\scripts:/scripts:ro" backend sh -c "pip install --no-cache-dir httpx >/dev/null 2>&1; python /scripts/smoke_rag_pipeline.py"
```

## 8. 新窗口起手提示词（直接复制使用）

```text
项目路径：D:\X\codex项目

请先阅读以下文件，理解现状后再动手，不要跳过：
1. AGENTS.md               —— 长期开发约束，最高优先级
2. README.md               —— 架构、目录、启动方式
3. docs/HANDOVER.md        —— 交接文档：已完成 / 未完成 / 硬性约束
4. C:\Users\X\Desktop\Workspace\项目维护说明.docx —— Docker 环境的维护规则

硬性约束（不要违反）：
- 不要执行 docker compose down -v
- 不要重建 frontend/pnpm-workspace.yaml
- 不要修改 docker-compose.yml 里 frontend 的 command 与 frontend_node_modules 卷映射
- 改过 compose 文件必须先 docker compose config，再 docker compose up -d
- 长耗时解析与模型调用只能放在 Worker，不能进 HTTP 请求
- 知识节点与回答必须能追溯到文档内容块
- 前端依赖只通过 docker compose run --rm frontend pnpm add 安装

当前进度：上传、文档解析、知识抽取三个后端模块和知识地图前端组件已完成，但闭环未打通
（上传后不会自动解析与抽取，页面还没有知识地图，Celery 无 task，数据库层为空）。

本次任务：<在这里写你要做的功能，例如“接通 上传 → 解析 → 知识树接口 → 页面地图 的完整链路”>

完成后请说明：改了哪些文件、如何验证、有哪些遗留问题。
```

## 9. 验证记录（时间线）

| 时间 | 事项 | 结果 |
| --- | --- | --- |
| 2026-07-30 | PRD + 8 周路线图文档 | 已生成到桌面 Workspace（当时缺渲染组件，只做了结构校验） |
| 2026-08-13 | 仓库骨架、AGENTS.md、compose、脚本 | 文件落盘完成；机器无 Docker CLI，未实际启动 |
| 2026-08-19 | 文件上传功能 | 后端 5 项测试通过；前端 Vitest 当时未跑成 |
| 2026-08-19 | 文档解析管线 | 模块 + 测试落盘，未接入 Worker |
| 2026-09-12 10:09 | 知识抽取模块 | 本地 pytest 全量通过（假模型，无 API Key） |
| 2026-09-12 10:30 | 知识地图 + 前端测试 | Vitest 通过（含上传测试） |
| 2026-09-12 10:46–19:25 | Docker 实际启动 | 7 服务全部 Up，修复 .pytest_cache 构建上下文与 pnpm-workspace.yaml 问题 |
| 2026-09-12 20:59 | 旧对话续用 | 401（provider 错配，非代码问题），本次未产生任何代码改动 |
| 2026-09-12 复核 | 现状检查 | Docker Desktop 未运行；宿主机 Python 缺后端依赖，未能复跑测试 |
| 2026-09-12 21:2x | 前端测试复跑 | Vitest 3 个文件 / 8 个测试通过，`tsc --noEmit` 无错误 |
| 2026-09-12 21:5x | RAG 检索问答链路 | 后端 35 个测试通过；前端 8 个测试通过；Docker 真实栈冒烟通过（上传→2 内容块→知识树→带 2 条引用回答）；新增 6 张表与 ADR 0001 |
| 2026-09-12 22:0x | 失败原因结构化 | `documents.error_code` 迁移 `569d1b72d580`；后端 37 / 前端 12 个测试通过 |
| 2026-09-12 22:1x | 扫描件 OCR 回落 | `documents.ocr_page_count` 迁移 `19373f9bd02a`；backend/worker 镜像重建（Tesseract + chi_sim/eng）；后端 38 个测试通过；用户那份 25 页扫描件实测 69.3s 识别 25/25 页、26 个内容块、带引用回答成功 |
| 2026-09-13 01:0x | 思维导图化改造 | 章节层级结构 + 目录页过滤 + 标题去重；前端思维导图弹窗、滚轮交互、节点搜索、双入口；后端 51 / 前端 22 个测试通过；扫描件结构实测「前言 → 五章 → 各章小节」 |
| 2026-09-14 | DOCX 标题识别修复 | 用户反馈「文字形式的文件生成的地图只有根节点 + 前言」。根因：DOCX 解析器只认英文 `Heading N` 样式，而这两份 Word 的章节标题挂在 `Title` 样式上，整篇被合并成一个「前言」章节。改为综合标题样式（含 `标题 1`）、`w:outlineLvl` 与编号（`第X章` / `一、` / `（一）`）识别，编号优先；文档标题按 `docProps` → 开头标题行 → 文件名回退。新增 6 个测试，后端 221 项通过；重建 `2025101236邱子豪.docx` 后结构为「论文写作课程的学习与反思 → 前言 + 一～七章」 |
| 2026-09-14 | PDF 前言层级对齐 | 摘要/关键词位于首个编号章节之前时，「前言」节点层级对齐到第一个标题，章节不再被挂到「前言」下面，与 DOCX 行为一致。新增 1 个测试，后端 222 项通过；真实 PDF（内嵌书签，4 个一级章节）复跑结构不变 |
| 2026-09-14 | 全屏导图 + 悬浮 AI 助手 | 左下角控件改为「放大 / 缩小 / 全屏 / 适应窗口」，全屏走浏览器 Fullscreen API（被浏览器拒绝时回退为铺满窗口）；全屏下地图占满窗口，AI 助手脱离侧栏成为悬浮面板，点击节点自动展开详情与四项助手能力，可「收起」为悬浮按钮；按 Esc 先退出全屏、不关闭弹窗；放大节点视图移到弹窗内部以便全屏下可见。前端 51 项测试通过（新增 3 项），`tsc --noEmit` 无错误 |
| 2026-09-14 | 悬浮助手拖拽 + 导图光标修复 | 悬浮 AI 助手标题栏与收起后的胶囊按钮都可拖拽，两者共用同一停靠位置；拖动结束位置保留，窗口缩放或展开面板时自动收敛回可视区（拖拽与点击用 4px 阈值区分，避免拖动误触展开）；导图空白区原来的手形光标（`grab` / `grabbing`）在部分 Windows 鼠标主题下会渲染成空白，改为标准箭头 + 平移时移动指针，并关闭节点拖拽以保持自动排版。前端 53 项测试通过（新增 2 项），`tsc --noEmit` 无错误 |
| 2026-09-15 | PDF 书签层级修复 | 用户拿论文终稿（23 页，带内嵌书签）测试时发现「1.优化包装策略」与名下三段正文变成了并列节点。根因：PDF 书签由 Word 按标题样式生成，作者把这三段正文也套用了标题样式，书签层级与编号项完全相同，解析器照搬书签层级。新增规则：编号项（同时补充支持 `1.` / `1、` 形式）之后，同层级、无编号且标题较长的条目判定为内容，下沉一级成为其子节点；短标题（如「参考文献」）不受影响。后端 223 项通过（新增 1 项）；这篇论文重建知识树后，三个节点已正确挂到「1.优化包装策略」下 |
| 2026-09-15 | 内容节点不再进图 + 导图编辑 | 用户确认思维导图只应表达文章结构，因此上面那条规则改为「直接并入」：被误设为标题样式的正文不再生成节点，文字仍保留在所属编号项的正文里（书签路径的章节正文本来就覆盖到下一个条目所在的页），短标题不受影响。同时给导图加了编辑能力：选中节点后回车新增子节点（卡片上也有「＋ 子节点」按钮）、双击卡片编辑标题与内容、Delete 删除选中节点及其子树；根节点不可删，输入框或按钮聚焦时快捷键不生效；新增节点用虚线边框和「本地」标记区分。编辑结果保存在页面会话内（关掉再打开地图仍在），暂未写回后端。后端 223 项、前端 61 项测试通过（前端新增 8 项），`tsc --noEmit` 无错误 |
| 2026-09-15 | 导图导出 XMind | 地图新增「下载 XMind」按钮，导出当前结构（含人工编辑的新增/修改）。格式采用 XMind 2020+ 的 `content.json`（sheet/topic，节点摘要写入 topic notes，根主题用 logic.right 结构），本机 XMind 26.4 可直接打开。ZIP 容器由前端自行实现（stored 条目 + CRC32），不引入新依赖。用 Python `zipfile` 交叉验证：`testzip()` 无损坏、三个条目齐全、中文内容正确。前端 67 项测试通过（新增 6 项），`tsc --noEmit` 无错误 |
| 2026-09-15 | 改为平衡图 | 用户要求参考经典导图形态（中心主题在中间、分支向左右两侧展开），网页端与导出文件一起改。网页端 `layoutTree` 增加平衡模式：按子树叶子数在根节点处把子分支切成左右两组（保持文档顺序），两侧各自做 tidy 布局后镜像左侧 x 坐标，并让每一侧都以根节点的 y 为垂直中心；节点按所在侧镜像连接点（左侧节点的入点在右、出点在左），根节点提供左右两个出点，边用 handle id 精确连接。导出改用 XMind 自身新建地图的默认结构 `org.xmind.ui.map.unbalanced`（平衡图）。前端 71 项测试通过（新增/调整 5 项），`tsc --noEmit` 无错误 |
| 2026-09-15 | 拖拽平移与拖拽节点分离 | 空白画布拖拽仍然平移视图；按住节点拖拽则可把该节点（连同子树）改挂到任意节点下：拖动时用 `getIntersectingNodes` 找落点并高亮（绿色虚线框），松手后写回树、重新布局并定位到新位置；落在空白处或自己的后代上会回弹到计算好的位置，根节点不可移动。因为导图是自动排版的，拖拽只改挂载关系、不保留自由坐标。光标沿用之前的处理（`grab`/`grabbing` 在部分 Windows 主题下不可见，统一改用 `move`）。前端 75 项测试通过（新增 4 项），`tsc --noEmit` 无错误 |
| 2026-09-15 | 编辑结果以 XMind 为保存方式 | 用户确认不需要后端持久化：前端编辑（新增、修改、移动、删除）后，用「下载 XMind」把编辑后的版本存到本地，XMind 文件即长期保存形式。下载一直使用的是对话内的 `draftTree`（编辑后的树），本次补测试把这条锁住（新增子节点 + 改名后再下载，断言导出的是编辑后的结构），并在标题栏提示「编辑结果请用『下载 XMind』保存」、按钮加悬停说明。页面刷新会丢失未下载的编辑，README 已注明。前端 76 项测试通过（新增 1 项），`tsc --noEmit` 无错误 |
| 2026-09-15 | 首屏 UI 美化（Instagram 配色） | 首页改为居中的单列布局（`max-w-xl`）：上传卡片居中，两个入口按钮从左右并排改为上下堆叠放在卡片下方，宽度与卡片对齐。配色换成 Instagram 风格：页面用紫 / 洋红 / 粉 / 暖橙的柔和径向渐变底（`globals.css` 的 body 背景），「文档上传」小标题用渐变文字，拖拽区为淡紫粉橙渐变 + 虚线边框 + 渐变圆形上传图标，两个按钮分别用 `#833AB4→#C13584→#E1306C` 与 `#E1306C→#F77737→#FCAF45` 渐变并带柔和投影和悬停上浮。前端 76 项测试通过，`tsc --noEmit` 无错误 |
| 2026-09-15 | 导图界面同步美化 | 弹窗与图谱沿用首屏配色：遮罩加毛玻璃，弹窗容器改圆角 3xl + 紫调柔和投影，标题栏为淡紫→白→暖橙渐变，「下载 XMind」改为渐变主按钮、「关闭」为描边胶囊；画布底色转淡紫、点阵点改为 `#E7D7F3`，左上角「展开/收起全部」与左下角控件改胶囊样式并加紫色悬停，底部操作提示改半透明胶囊；节点卡片改圆角 xl、紫调投影，选中态用 `#E1306C` 粉色描边，本地节点用 `#C13584` 虚线，卡片操作按钮改胶囊（「＋ 子节点」用紫粉渐变底），删除/编辑等按钮悬停转粉；右侧节点详情与 AI 助手改为白底卡片、关键词胶囊改紫粉渐变、提问按钮改渐变主按钮，搜索框改胶囊并带粉色聚焦环，节点放大视图与悬浮助手（面板标题栏、「节点 AI 助手」胶囊）同步换色。前端 76 项测试通过，`tsc --noEmit` 无错误 |
| 2026-09-15 | 连线改曲线 + 节点细节 | 用户反馈导图里线条重叠成一条。根因：连线用直角折线（`smoothstep`），同一父节点下所有子节点的竖直段都落在同一条 x 上，于是叠成一条粗线。改为贝塞尔曲线（`type: "bezier"`，描边 `#CFA8E4`、1.6px、圆头），既消除重叠，观感也贴近 XMind 的参考图。同时按真实卡片高度校正布局参数（`nodeHeight` 96→120、`verticalGap` 108→70），并在节点标题下加了一条紫粉渐变短下划线，强化层级感。前端 77 项测试通过（新增 1 项：断言连线为曲线），`tsc --noEmit` 无错误 |
| 2026-09-15 | 拖拽节点改为自由停留 | 用户反馈拖拽后卡片会弹回。两处原因：一是 `onNodeDragStop` 里显式把节点重置回计算位置；二是吸附高亮会触发 graph 重建，`useEffect` 随之用计算位置覆盖节点，拖拽过程中就回弹。现在改为两类行为——落在别的节点上仍改挂载（并清掉该子树的自由位移，让它在新分支里重新排版）；落在空白画布上则保留自由位置：以「拖动后坐标 − 当前计算坐标」得到相对布局的位移，记录到 `positionOffsets` 并同时应用于该节点及其整个子树，使分支整体移动、连线不断。`graph.buildKnowledgeGraph` 支持 `positionOffsets`，拖拽期间同步 effect 会保留被拖节点的实时坐标（`draggingNodeRef`），并且文档切换（`tree.id` 变化）时清空位移、恢复自动排版。前端 79 项测试通过（新增 2 项：子树 id 收集、位移应用到节点坐标），`tsc --noEmit` 无错误 |
| 2026-09-15 | 撤销 / 重做 | 新增编辑历史：`KnowledgeMapDialog` 用 `pastRef`/`futureRef` 保存最多 50 步快照，每个快照包含树与自由位移（`positionOffsets`），所有编辑统一走 `commit()` 入栈，因此新增、改名、删除、拖拽改挂载、拖拽自由停留都可以用 Ctrl+Z 撤销（Ctrl+Shift+Z 或 Ctrl+Y 重做），标题栏也加了「撤销 / 重做」按钮，无历史时置灰；输入框聚焦时 Ctrl+Z 仍归浏览器文本撤销。为把自由位移也纳入历史，`positionOffsets` 从 `KnowledgeMap` 内部状态提升为受控属性（`positionOffsets` + `onPositionOffsetsChange`），改挂载时由弹窗一次性清掉该子树位移并入栈，避免一次拖拽产生两条历史。切换文档（`tree.id` 变）会清空历史与位移。前端 81 项测试通过（新增 2 项：Ctrl+Z 还原改挂载、撤销/重做按钮状态与重做结果），`tsc --noEmit` 无错误 |
| 2026-09-15 | 五套配色主题 | 把界面颜色全部抽成 CSS 变量（`--brand-1..5`、`--brand-ink`、`--brand-soft`、`--brand-soft-2`、`--brand-line`、`--brand-ring`、`--brand-ring-soft`、`--brand-shadow`、`--brand-shadow-strong`、`--brand-dots`、`--brand-edge`、`--brand-page`），在 `features/workspace/themes.ts` 定义 5 套主题：紫粉（Instagram）、海盐蓝、薄荷绿、紫罗兰、落日橘；工作区顶部新增胶囊色卡选择器，`DocumentWorkspace` 持有主题状态并把变量内联挂在外层容器（同时用 `--brand-page` 作为整页渐变底），因此上传页与导图弹窗（页面底色、按钮、标题栏、节点卡片、选中描边、连线、点阵、关键词胶囊、AI 助手面板、悬浮胶囊、放大视图）会一起换色。所有硬编码色值已替换为变量引用，`:root` 保留默认值，组件在主题容器之外也能正常显示。前端 82 项测试通过（新增 1 项：五套主题齐全且切换后 `data-theme` 与变量生效），`tsc --noEmit` 无错误 |
| 2026-09-15 | 主题记忆 | 用户选择的配色写入 `localStorage`（键 `knowledge-agent-theme`），下次打开自动恢复。恢复放在挂载后的 effect 里，避免服务端预渲染与客户端首帧不一致（不产生 hydration 警告）；写入在恢复完成后才启用，避免默认值把已存主题覆盖掉。`readStoredTheme()` / `storeTheme()` 对 localStorage 抛错（隐私模式、存储被禁用）做了降级，读不到或写不进就用默认的紫粉。前端 84 项测试通过（新增 2 项：选择后写入存储、挂载时恢复已存主题），`tsc --noEmit` 无错误 |

## 10. 待改进清单（2026-09-15 评估）

完整版（含现状影响与建议做法，可直接拆任务）作为交接件放在桌面 Workspace：`项目现状与待改进清单.docx`。
下面只列条目，方便在仓库里检索：

- **P0 接口鉴权与租户隔离**：路由只有数据库会话依赖，没有认证，知道 `document_id` 即可读取文档、知识树与问答结果。
- **P0 版本控制与持续集成**：仓库尚未 `git init`，也没有 CI，改动无法回溯、测试不是合并门禁。
- **P0 测试库与生产库不一致**：测试用 SQLite、生产用 PostgreSQL，时区/JSON/约束差异被掩盖。
- **P1 编辑结果持久化**：导图编辑只在页面会话内，刷新即丢失，目前靠下载 XMind 保存。
- **P1 计量与限流**：无 token/成本记录，无速率限制。
- **P1 对象存储与数据生命周期**：`.env` 有 S3 配置但代码未使用，文件仍在本地卷，且无删除接口与保留策略。
- **P1 建树并发与唯一约束**：仅 `content_chunks` 有唯一约束，节点缺文档内路径唯一键。
- **P1 大文档规模上限**：只有 25MB 上传限制，没有页数/节点数上限。
- **P1 前端端到端测试**：未安装 Playwright，主链路只有单元测试。
- **P2 依赖与 OCR 环境**：依赖无自动更新（LangGraph 仍为 0.x）；缺 OCR 引擎时测试静默跳过。
- **P2 前端可观测性**：没有错误上报。
- **P2 数据模型**：知识地图模型以 JSON 存在文档行，超大文档会行膨胀。
- **P2 交互细节**：撤销历史仅限弹窗会话；自由位置重开地图后重置；键盘仅支持回车/删除；拖拽仅鼠标。

建议顺序：版本控制与持续集成 → 鉴权与租户隔离 → PostgreSQL 集成测试 → 编辑持久化（视需求） → 其余。

> 提醒：第 9 节中“测试通过”的结论来自当时会话的记录与维护文档，本次复核环境（Docker 未启动、本地依赖缺失）无法重新验证。新窗口在 Docker 启动后应重跑一次测试以确认基线。
