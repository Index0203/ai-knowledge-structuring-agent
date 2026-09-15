# ADR 0001 — Node-scoped RAG pipeline with evidence-bound answers

- Status: Accepted
- Date: 2026-09-12
- Scope: backend retrieval pipeline, evidence data model, worker tasks, node Q&A API

## 1. Problem

The product promise is evidence-bound knowledge work: a user opens a knowledge node and asks a
question, and the answer must be traceable to the uploaded document. The repository already ships
upload validation, the document parsing pipeline, and the LangGraph knowledge extraction agent, but
there is no content-block persistence, no vector index, no retrieval step, and no answer path. A
question cannot be answered today without inviting unverifiable model output, which `AGENTS.md`
explicitly forbids.

## 2. Decision

Add a node-scoped RAG pipeline that runs entirely in Celery workers and persists every artifact in
PostgreSQL, with ChromaDB used only as a derived retrieval index.

```text
upload -> parse -> chunk -> embed -> ChromaDB index
                                   |
knowledge extraction -> knowledge nodes + evidence links
                                   |
node question -> retrieve (node scope first, document scope second)
                                   |
              structured answer -> citation validation -> persisted answer + evidence
```

### 2.1 Stages

| Stage | Module | Output |
| --- | --- | --- |
| Chunking | `app/pipelines/chunking/` | `ContentChunk` records with section index, page/paragraph location and character offsets |
| Embedding | `app/embeddings/` | Deterministic local vectors by default, OpenAI-compatible vectors when configured |
| Vector store | `app/vectorstores/` | ChromaDB collection restricted by `document_id` metadata |
| Retrieval | `app/retrieval/` | Ranked chunks, node-evidence chunks boosted, below-threshold hits dropped |
| Answering | `app/agents/node_qa/` | Structured draft (answer, cited chunk ids, confidence) or extractive fallback |
| Persistence | `app/models/`, `app/repositories/` | Documents, chunks, nodes, edges, questions, evidence links |

### 2.2 Evidence data model

A single `evidence_links` table is the only sanctioned bridge between generated artifacts and
content blocks. Each row points at one `content_chunk` and at exactly one target
(`knowledge_node`, `knowledge_edge` or `answer`) and stores the original quote plus retrieval
relevance. This keeps the "every node, edge and answer resolves to source text" rule enforceable
with one query pattern, instead of three drifting join tables.

ChromaDB is a derived index. Chunk text, ordering and citation rendering always read from
PostgreSQL; deleting or rebuilding the collection never destroys the source of truth.

### 2.3 Scope control and refusal policy

1. Retrieval is filtered by `document_id` and re-ranked with a boost for the node's own evidence
   chunks, so a question about one node cannot silently answer from unrelated documents.
2. A candidate below `RETRIEVAL_MIN_SCORE` is dropped. If nothing survives, the question is stored
   as `insufficient_evidence` with no citations and the API returns a refusal.
3. Every model citation must be a chunk id that was actually retrieved for this question. A draft
   with zero valid citations is downgraded to a refusal instead of being shown.
4. Answers store model name, prompt version, latency and the exact cited chunk ids, satisfying the
   traceability rule.

### 2.4 Degraded modes

The deployment has no AI provider key by default, so two explicit degraded modes keep the pipeline
observable instead of failing silently:

1. `EMBEDDING_PROVIDER=deterministic` (default) uses a hashing bag-of-words embedding. Retrieval is
   lexical rather than semantic, and every answer records `embedding_model`.
2. Without a chat model, knowledge extraction and answering fall back to, respectively, the
   document's own heading structure and verbatim extractive quotes. Both modes are reported as
   `structure_fallback` / `extractive_fallback` in the API so the UI can label them honestly.

Neither fallback invents content: the structural tree copies headings, and the extractive answer
copies sentences from retrieved chunks.

## 3. Alternatives considered

| Alternative | Why rejected |
| --- | --- |
| Answer synchronously inside the HTTP request | Violates the "no long-running model calls in HTTP" rule and makes the gateway depend on provider latency |
| Store chunk text only in ChromaDB | Makes the vector store the source of truth and blocks citation rendering when the index is rebuilt |
| Keep knowledge trees in the Celery result backend | Nodes could not carry stable ids or evidence rows, breaking node-scoped questions and human correction |
| Return the model answer without citation validation | Violates evidence-first; an unverifiable answer can be displayed |
| Add a second vector database or a hosted RAG service | Unnecessary infrastructure change for MVP; ChromaDB is already part of the stack |

## 4. Impact

- New tables: `documents`, `content_chunks`, `knowledge_nodes`, `knowledge_edges`, `evidence_links`,
  `questions` (one Alembic migration).
- New worker tasks: `index_document`, `build_knowledge_tree`, `answer_question`.
- New API surface under `/api/v1/documents` and `/api/v1/questions`; uploads now persist a document
  row so processing has a stable id.
- New environment keys with safe defaults: `EMBEDDING_PROVIDER`, `EMBEDDING_DIMENSIONS`,
  `CHROMA_COLLECTION`, `CHUNK_MAX_CHARACTERS`, `CHUNK_OVERLAP_CHARACTERS`, `RETRIEVAL_TOP_K`,
  `RETRIEVAL_MIN_SCORE`, `NODE_EVIDENCE_BOOST`, `OPENAI_BASE_URL`, `OPENAI_EMBEDDING_MODEL`.

## 5. Compatibility, migration and rollback

- Existing endpoints and upload behaviour are unchanged apart from the extra `documents` row.
- Migration is additive (`alembic upgrade head`); no existing table is altered.
- Rollback: `alembic downgrade base` drops only the new tables, and the ChromaDB collection can be
  deleted and rebuilt by re-running the indexing task. No source document is lost because uploads
  live in object storage / `UPLOAD_DIR`.
- The frontend keeps working without the new endpoints; node Q&A is additive UI.

## 6. Observability and cost

- Each question row records model, prompt version, latency, status and cited chunk ids.
- Retrieval scores are stored per citation, so answer quality regressions are diagnosable without
  re-running the model.
- Cost is bounded per question by `RETRIEVAL_TOP_K`, `CHUNK_MAX_CHARACTERS` and answer max tokens.

## 7. Verification

Backend tests cover chunk boundaries and offsets, deterministic embeddings, retrieval filtering and
boosting, refusal when nothing clears the threshold, citation validation rejecting invented chunk
ids, the extractive fallback, and API status transitions. Frontend tests cover asking a question,
rendering citations, and the refusal state.

## 8. Amendment — OCR fallback for scanned PDFs (2026-09-12)

A 25-page scanned PDF produced zero characters of text, so indexing failed with a message no user could
act on. Two changes followed:

1. **Stable failure codes.** `documents.error_code` carries `no_text_layer`, `unsupported_format` or
   `processing_failed`, while `error_message` keeps the technical detail for logs. The frontend maps
   codes to actionable copy, so a scanned file now explains what to do.
2. **OCR fallback.** `PdfDocumentParser` rasterises any page whose text layer is shorter than
   `OCR_MIN_TEXT_CHARACTERS` and runs Tesseract (`OCR_LANGUAGES`, default `chi_sim+eng`). A page that
   fails OCR is logged and skipped; `documents.ocr_page_count` records how many pages were recognised.

New dependencies: `pytesseract` and `Pillow` (pip) plus `tesseract-ocr`, `tesseract-ocr-eng` and
`tesseract-ocr-chi-sim` (Debian packages in `backend/Dockerfile`). New configuration: `OCR_ENABLED`,
`OCR_LANGUAGES`, `OCR_DPI`, `OCR_MIN_TEXT_CHARACTERS`, `OCR_MAX_PAGES`.

Cost and rollback: OCR adds roughly three seconds per scanned page (25 pages ≈ 70 s, entirely inside the
worker) and about 110 MB to the backend image. `OCR_ENABLED=false` restores the previous behaviour where
such documents fail with `no_text_layer`. Known limitation: the knowledge-tree build re-parses the file,
so scanned documents are OCR'd twice; caching the parse result is the next optimisation.

## 9. Amendment — outline-first structure and the mind-map UI (2026-09-12)

Review feedback: the map looked like a flat list of pages, the wheel did nothing, and it rendered below the
upload panel. The tree now mirrors the document outline and the UI became a mind map.

1. **Outline detection.** DOCX heading styles, PDF bookmarks, and numbered headings (`第X章`, `一、`,
   `（一）`, `1.1`) with font size as a hint produce sections that carry a real level. Contents pages and
   duplicated headings are filtered out. Parsers report `structure_source`.
2. **Nested tree.** The structural tree builder nests sections by level instead of grouping pages
   (`MAX_NODE_CHILDREN` raised to 64, evidence indexes to 24). A chapter node's evidence covers its whole
   subtree, so questions asked at chapter level still retrieve child content.
3. **Mind-map layout.** `layout.ts` centres every parent on its children; the canvas supports wheel pan,
   Ctrl+wheel zoom, drag pan, expand/collapse all, and node search with highlight + zoom-to-node.
4. **Two entry points.** After upload the workspace offers 生成思维导图 (structure only) and 生成知识地图
   (structure + search + Q&A); both open in a full-screen dialog.

Cost: none beyond CPU during parsing. Rollback: the parser falls back to page sections whenever detection
finds fewer than two headings, and `structure_source` records which strategy was used.

## 10. Amendment — the Node Context mechanism (2026-09-13)

Every knowledge node now has an AI assistant with four capabilities: explain, give examples, study deeply,
and generate test questions. All four are answered from one artefact, the **Node Context**.

### 10.1 What a Node Context contains

`app/agents/node_qa/context.py` assembles a deterministic snapshot for exactly one node:

| Part | Why it is there |
| --- | --- |
| `document_title`, `breadcrumb` (root → node) | Places the node in the document outline so answers can say "第一章第三节" |
| `node_title`, `node_summary`, `keywords` | The node's own identity, taken from the persisted tree |
| `children` (title + summary, max 8) | Lets "study deeply" and "generate questions" walk into sub-points |
| `siblings` (max 6 titles) | Contrast: what this node is *not* |
| `evidence` (max 6 labelled blocks) | The only facts the model may use, each with a stable label (`c1`) and a chunk id |
| `truncated`, `dropped_evidence`, `dropped_children` | Honest bookkeeping: the prompt says so when context was dropped |

### 10.2 Invariants

1. **Evidence first.** A context without evidence is empty, and an empty context is an immediate refusal -
   the model is never called.
2. **Stable labels.** Evidence is labelled `c1…cN`; the model must cite those labels, and every label is
   resolved back to a chunk id before the answer is stored. Unknown labels invalidate the answer.
3. **Bounded.** `NODE_CONTEXT_MAX_CHARACTERS` (default 6000) caps the context; the builder drops evidence
   blocks rather than silently truncating text mid-quote, and records what it dropped.
4. **Deterministic.** The same node and the same retrieval result always produce the same context, so a
   stored answer can be re-explained later.
5. **Intent-aware.** The intent changes the retrieval query (an example request adds 案例/例如 hints, a deep
   dive adds child titles) and the instruction block, but never the grounding rules.

### 10.3 Execution path

```text
POST /knowledge-nodes/{id}/questions {intent, question?}
        -> questions row (intent + prompt_version)         # queued, worker only
worker  -> retriever (node evidence first, document scope)
        -> build_node_context(...)
        -> LangGraph: draft -> validate citations (+ validate quiz items)
        -> persist answer, quiz payload and evidence links
GET  /questions/{id} -> answer, citations, quiz items, refusal reason
```

The assistant therefore reuses the RAG pipeline's safety properties: node-scoped retrieval, citation
validation, refusal instead of invention, and full traceability (intent, prompt version, model, latency).

### 10.4 Degraded mode

Without a chat model the assistant still answers: explain/ask return verbatim quotes from the evidence
(`extractive_fallback`), and quiz returns questions derived from the node's own child nodes, each carrying
the evidence it came from. Both label themselves in the API.

### 10.5 Alternatives considered

| Alternative | Why rejected |
| --- | --- |
| Send the whole document to the model per request | Unbounded cost, loses node scope, invites answers from unrelated sections |
| Send only the node summary | Nothing to cite; the summary is already a model output |
| Let the model call retrieval tools itself | Removes the deterministic scope control and makes refusals untestable |
| Separate endpoint per capability | Four code paths with four prompt/validation rules; one intent parameter keeps one pipeline |
