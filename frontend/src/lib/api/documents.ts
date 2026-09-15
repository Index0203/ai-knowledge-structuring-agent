import { apiBaseUrl } from "./client";

export type DocumentStatusValue = "uploaded" | "indexing" | "indexed" | "failed";
export type KnowledgeTreeStatusValue = "none" | "building" | "ready" | "failed";

export type DocumentStatus = {
  document_id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  status: DocumentStatusValue;
  error_message: string | null;
  error_code: string | null;
  page_count: number | null;
  paragraph_count: number | null;
  ocr_page_count: number | null;
  chunk_count: number;
  embedding_model: string | null;
  tree_status: KnowledgeTreeStatusValue;
  tree_error: string | null;
  tree_mode: string | null;
  created_at: string;
  indexed_at: string | null;
  tree_built_at: string | null;
};

export type KnowledgeTreeNode = {
  id: string;
  title: string;
  summary: string;
  keywords: string[];
  source_section_indexes: number[];
  depth: number;
  children: KnowledgeTreeNode[];
};

export type KnowledgeTree = KnowledgeTreeNode;

export type KnowledgeTreeResponse = {
  document_id: string;
  status: KnowledgeTreeStatusValue;
  mode: string | null;
  error_message: string | null;
  tree: KnowledgeTree | null;
};

export type ProcessingAccepted = {
  document_id: string;
  status: string;
};

type ErrorPayload = { detail?: unknown };

async function readError(response: Response, fallback: string): Promise<Error> {
  const payload: ErrorPayload = await response.json().catch(() => ({}));
  return new Error(typeof payload.detail === "string" ? payload.detail : fallback);
}

export async function getDocumentStatus(documentId: string): Promise<DocumentStatus> {
  const response = await fetch(`${apiBaseUrl}/api/v1/documents/${documentId}`);
  if (!response.ok) {
    throw await readError(response, "无法读取文档状态。");
  }
  return response.json() as Promise<DocumentStatus>;
}

export async function startProcessing(documentId: string): Promise<ProcessingAccepted> {
  const response = await fetch(`${apiBaseUrl}/api/v1/documents/${documentId}/processing`, { method: "POST" });
  if (!response.ok) {
    throw await readError(response, "无法启动文档处理。");
  }
  return response.json() as Promise<ProcessingAccepted>;
}

export async function startKnowledgeTree(documentId: string): Promise<ProcessingAccepted> {
  const response = await fetch(`${apiBaseUrl}/api/v1/documents/${documentId}/knowledge-tree`, { method: "POST" });
  if (!response.ok) {
    throw await readError(response, "无法启动知识结构生成。");
  }
  return response.json() as Promise<ProcessingAccepted>;
}

export async function getKnowledgeTree(documentId: string): Promise<KnowledgeTreeResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/documents/${documentId}/knowledge-tree`);
  if (!response.ok) {
    throw await readError(response, "无法读取知识结构。");
  }
  return response.json() as Promise<KnowledgeTreeResponse>;
}
