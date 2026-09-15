"use client";

import { useEffect } from "react";

import { KnowledgeNodeQa } from "./KnowledgeNodeQa";
import { KnowledgeMapMode, KnowledgeTreeNode } from "./types";

type KnowledgeNodeDialogProps = {
  node: KnowledgeTreeNode;
  mode: KnowledgeMapMode;
  onClose: () => void;
};

/**
 * Enlarged view of one node. The map card clamps long summaries, so this window
 * shows the complete text plus keywords and evidence sections.
 */
export function KnowledgeNodeDialog({ node, mode, onClose }: KnowledgeNodeDialogProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="节点放大视图"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/50 p-6 backdrop-blur-sm"
    >
      <div className="flex max-h-[86vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl border border-white/70 bg-white/95 shadow-[0_30px_80px_-40px_var(--brand-shadow)] backdrop-blur">
        <header className="flex items-start gap-4 border-b border-[color:var(--brand-line)] bg-gradient-to-r from-[var(--brand-soft)] via-white to-[var(--brand-soft-2)] px-6 py-4">
          <div className="min-w-0">
            <p className="text-xs text-slate-400">节点放大视图</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-900">{node.title}</h2>
          </div>
          <button
            type="button"
            className="ml-auto shrink-0 rounded-full border border-slate-200 bg-white/80 px-4 py-1.5 text-sm text-slate-600 transition hover:border-[color:var(--brand-ring-soft)] hover:text-slate-900"
            onClick={onClose}
          >
            关闭 (Esc)
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">内容</h3>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-800">{node.summary}</p>

          <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">关键词</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {node.keywords.length > 0 ? (
              node.keywords.map((keyword) => (
                <span key={keyword} className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs text-indigo-700">
                  {keyword}
                </span>
              ))
            ) : (
              <span className="text-sm text-slate-500">暂无关键词</span>
            )}
          </div>

          <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">来源章节</h3>
          <p className="mt-2 text-sm text-slate-700">
            {node.source_section_indexes.length > 0
              ? node.source_section_indexes.map((index) => `第 ${index + 1} 节`).join("、")
              : "根节点汇总全部内容"}
          </p>

          {mode === "knowledge" ? <KnowledgeNodeQa node={node} /> : null}
        </div>
      </div>
    </div>
  );
}
