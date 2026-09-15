"use client";

import { useMemo, useState } from "react";

import { filterKnowledgeNodes } from "./search";
import { KnowledgeTree, KnowledgeTreeNode } from "./types";

type NodeSearchProps = {
  tree: KnowledgeTree;
  onSelectNode: (node: KnowledgeTreeNode) => void;
};

export function NodeSearch({ tree, onSelectNode }: NodeSearchProps) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => filterKnowledgeNodes(tree, query), [tree, query]);
  const isOpen = query.trim().length > 0;

  return (
    <div className="relative w-full sm:w-80">
      <input
        aria-label="搜索节点"
        className="w-full rounded-full border border-slate-200 bg-white/90 px-4 py-2 text-sm shadow-sm outline-none transition focus:border-[color:var(--brand-3)] focus:ring-2 focus:ring-[color:var(--brand-ring)]"
        placeholder="搜索节点标题、摘要或关键词…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {isOpen ? (
        <ul className="absolute z-20 mt-2 max-h-72 w-full overflow-auto rounded-2xl border border-[color:var(--brand-line)] bg-white/95 shadow-[0_20px_45px_-25px_var(--brand-shadow)] backdrop-blur">
          {results.length === 0 ? (
            <li className="px-3 py-2 text-sm text-slate-500">没有匹配的节点</li>
          ) : (
            results.map((node) => (
              <li key={node.id}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left transition hover:bg-[var(--brand-soft)]"
                  onClick={() => {
                    onSelectNode(node);
                    setQuery("");
                  }}
                >
                  <span className="block text-sm text-slate-800">{node.title}</span>
                  <span className="mt-0.5 block truncate text-xs text-slate-500">{node.summary}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
