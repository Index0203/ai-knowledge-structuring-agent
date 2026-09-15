"use client";

import { KnowledgeTreeNode } from "./types";

type KnowledgeNodeDetailsProps = {
  node: KnowledgeTreeNode | null;
  onClose: () => void;
  variant?: "sidebar" | "floating";
};

export function KnowledgeNodeDetails({ node, onClose, variant = "sidebar" }: KnowledgeNodeDetailsProps) {
  // The fullscreen assistant floats over the map, so it must not draw the
  // sidebar divider that separates the panel from the canvas.
  const containerClass =
    variant === "floating"
      ? "rounded-2xl border border-[color:var(--brand-line)] bg-white/90 p-5 shadow-sm backdrop-blur"
      : "rounded-2xl border border-[color:var(--brand-line)] bg-white/85 p-5 shadow-sm backdrop-blur";

  if (!node) {
    return (
      <aside className={`${containerClass} text-sm text-slate-500`}>
        点击地图中的节点查看知识详情。
      </aside>
    );
  }

  return (
    <aside aria-label="节点详情" className={containerClass}>
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-lg font-semibold text-slate-900">{node.title}</h2>
        <button type="button" onClick={onClose} className="text-sm text-slate-500 hover:text-slate-900">关闭</button>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-700">{node.summary}</p>
      <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">关键词</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {node.keywords.length > 0 ? node.keywords.map((keyword) => <span key={keyword} className="rounded-full bg-gradient-to-r from-[var(--brand-soft)] to-[var(--brand-soft-2)] px-2.5 py-1 text-xs font-medium text-[var(--brand-ink)]">{keyword}</span>) : <span className="text-sm text-slate-500">无关键词</span>}
      </div>
      <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">来源章节</h3>
      <p className="mt-2 text-sm text-slate-700">{node.source_section_indexes.length > 0 ? node.source_section_indexes.map((index) => index + 1).join(", ") : "根节点汇总全部内容"}</p>
    </aside>
  );
}
