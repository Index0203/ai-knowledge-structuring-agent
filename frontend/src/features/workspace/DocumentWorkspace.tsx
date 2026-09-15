"use client";

import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";

import { KnowledgeMapDialog, KnowledgeMapMode } from "@/features/knowledge-map/KnowledgeMapDialog";
import { KnowledgeTree, KnowledgeTreeNode } from "@/features/knowledge-map/types";
import { UploadPanel } from "@/features/uploads/UploadPanel";
import {
  DocumentStatus,
  KnowledgeTreeResponse,
  getDocumentStatus,
  getKnowledgeTree,
  startKnowledgeTree,
  startProcessing,
} from "@/lib/api/documents";
import { UploadedDocument } from "@/lib/api/uploads";
import { describeDocumentError } from "./documentErrors";
import { DEFAULT_THEME, THEMES, ThemeId, readStoredTheme, storeTheme, themeVars } from "./themes";

type Phase = "idle" | "choice" | "processing" | "structuring" | "ready" | "error";

const DEFAULT_POLL_INTERVAL_MS = 1500;
const MAX_POLLS = 160;

type DocumentWorkspaceProps = {
  pollIntervalMs?: number;
};

export function DocumentWorkspace({ pollIntervalMs = DEFAULT_POLL_INTERVAL_MS }: DocumentWorkspaceProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState("");
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [tree, setTree] = useState<KnowledgeTree | null>(null);
  const [treeMode, setTreeMode] = useState<string | null>(null);
  const [openMode, setOpenMode] = useState<KnowledgeMapMode | null>(null);
  const [theme, setTheme] = useState<ThemeId>(DEFAULT_THEME);
  const [themeRestored, setThemeRestored] = useState(false);

  // Read the stored palette after mount so server and client markup match.
  useEffect(() => {
    const stored = readStoredTheme();
    if (stored) setTheme(stored);
    setThemeRestored(true);
  }, []);

  useEffect(() => {
    if (themeRestored) storeTheme(theme);
  }, [theme, themeRestored]);

  const isBusy = phase === "processing" || phase === "structuring";

  const handleUploaded = useCallback((document: UploadedDocument): void => {
    setDocumentId(document.document_id);
    setTree(null);
    setTreeMode(null);
    setOpenMode(null);
    setPhase("choice");
    setMessage("文件已通过类型校验。请选择生成思维导图，或生成带搜索与问答的知识地图。");
  }, []);

  const generate = useCallback(
    async (mode: KnowledgeMapMode): Promise<void> => {
      if (!documentId) return;
      if (tree) {
        setOpenMode(mode);
        return;
      }
      setPhase("processing");
      setMessage("正在解析文档、切分内容块并建立向量索引…");
      try {
        await startProcessing(documentId);
        const status = await waitForDocument(documentId, pollIntervalMs);
        setPhase("structuring");
        setMessage("正在依据原文生成知识结构…");
        await startKnowledgeTree(documentId);
        const response = await waitForKnowledgeTree(documentId, pollIntervalMs);
        if (!response.tree) {
          throw new Error(response.error_message ?? "知识结构生成失败。");
        }
        const ocrPages = status.ocr_page_count ?? 0;
        const ocrNote = ocrPages > 0 ? `（该文件是扫描件，其中 ${ocrPages} 页已通过 OCR 识别）` : "";
        setTree(response.tree);
        setTreeMode(response.mode);
        setPhase("ready");
        setOpenMode(mode);
        setMessage(`知识结构已就绪，共 ${countNodes(response.tree)} 个节点${ocrNote}。`);
      } catch (error: unknown) {
        setPhase("error");
        setMessage(error instanceof Error ? error.message : "文档处理失败，请稍后重试。");
      }
    },
    [documentId, pollIntervalMs, tree],
  );

  return (
    <div
      data-theme={theme}
      style={
        {
          ...themeVars(theme),
          backgroundImage: "var(--brand-page)",
          backgroundAttachment: "fixed",
        } as CSSProperties
      }
      className="flex min-h-screen w-full flex-col items-center justify-center px-6 py-12"
    >
      <div className="flex w-full max-w-xl flex-col gap-4">
      <ThemePicker theme={theme} onChange={setTheme} />
      <UploadPanel onUploaded={handleUploaded} />

      {message ? (
        <p
          role="status"
          className={`rounded-xl bg-white/70 px-4 py-3 text-sm shadow-sm backdrop-blur ${
            phase === "error" ? "text-rose-600" : "text-slate-600"
          }`}
        >
          {message}
        </p>
      ) : null}

      {phase === "choice" || tree ? (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            className="group rounded-2xl bg-gradient-to-r from-[var(--brand-1)] via-[var(--brand-2)] to-[var(--brand-3)] p-4 text-left text-white shadow-[0_18px_38px_-20px_var(--brand-shadow)] transition hover:-translate-y-0.5 hover:shadow-[0_22px_44px_-20px_var(--brand-shadow-strong)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
            disabled={isBusy}
            onClick={() => void generate("mindmap")}
          >
            <span className="block text-base font-semibold">生成思维导图</span>
            <span className="mt-1 block text-xs text-white/85">按文档章节层级展开，只看结构，不提问。</span>
          </button>
          <button
            type="button"
            className="group rounded-2xl bg-gradient-to-r from-[var(--brand-3)] via-[var(--brand-4)] to-[var(--brand-5)] p-4 text-left text-white shadow-[0_18px_38px_-20px_var(--brand-shadow)] transition hover:-translate-y-0.5 hover:shadow-[0_22px_44px_-20px_var(--brand-shadow-strong)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
            disabled={isBusy}
            onClick={() => void generate("knowledge")}
          >
            <span className="block text-base font-semibold">生成知识地图</span>
            <span className="mt-1 block text-xs text-white/85">思维导图结构 + 节点搜索 + 基于原文的问答与引用。</span>
          </button>
        </div>
      ) : null}

      {treeMode === "structure_fallback" && phase === "ready" ? (
        <p className="rounded-xl bg-white/70 px-4 py-3 text-xs text-slate-600 shadow-sm backdrop-blur">
          未配置大模型，当前知识结构直接取自文档自身的章节层级（未做语义归纳）。
        </p>
      ) : null}

      {tree && openMode ? (
        <KnowledgeMapDialog
          tree={tree}
          mode={openMode}
          onClose={() => setOpenMode(null)}
          onTreeChange={setTree}
        />
      ) : null}
      </div>
    </div>
  );
}

function ThemePicker({
  theme,
  onChange,
}: {
  theme: ThemeId;
  onChange: (theme: ThemeId) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 self-center rounded-full border border-white/70 bg-white/70 px-3 py-2 text-xs shadow-sm backdrop-blur">
      <span className="text-slate-500">配色</span>
      {THEMES.map((item) => {
        const active = item.id === theme;
        return (
          <button
            key={item.id}
            type="button"
            aria-pressed={active}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 transition ${
              active
                ? "border-[color:var(--brand-3)] bg-white text-slate-900 shadow-sm"
                : "border-transparent text-slate-500 hover:bg-white/70 hover:text-slate-700"
            }`}
            onClick={() => onChange(item.id)}
          >
            <span
              aria-hidden="true"
              className="h-3.5 w-3.5 rounded-full"
              style={{ backgroundImage: `linear-gradient(135deg, ${item.swatch.join(", ")})` }}
            />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

async function waitForDocument(documentId: string, pollIntervalMs: number): Promise<DocumentStatus> {
  for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
    const status = await getDocumentStatus(documentId);
    if (status.status === "indexed") return status;
    if (status.status === "failed") {
      throw new Error(describeDocumentError(status));
    }
    await sleep(pollIntervalMs);
  }
  throw new Error("文档处理超时，请稍后重试。");
}

async function waitForKnowledgeTree(documentId: string, pollIntervalMs: number): Promise<KnowledgeTreeResponse> {
  for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
    const response = await getKnowledgeTree(documentId);
    if (response.status === "ready") return response;
    if (response.status === "failed") {
      throw new Error(response.error_message ?? "知识结构生成失败。");
    }
    await sleep(pollIntervalMs);
  }
  throw new Error("知识结构生成超时，请稍后重试。");
}

function countNodes(node: KnowledgeTreeNode): number {
  return 1 + node.children.reduce((total, child) => total + countNodes(child), 0);
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
