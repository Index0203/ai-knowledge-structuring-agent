"use client";

import type { KeyboardEvent, MouseEvent } from "react";
import { useEffect, useState } from "react";
import { Handle, type NodeProps, Position } from "@xyflow/react";

import { NEW_NODE_TITLE } from "./editing";
import {
  KnowledgeFlowNode,
  NODE_SOURCE_HANDLE,
  NODE_TARGET_HANDLE,
  ROOT_SOURCE_HANDLES,
} from "./graph";
import type { BranchSide } from "./layout";

export function KnowledgeMapNode({ id, data, selected }: NodeProps<KnowledgeFlowNode>) {
  const {
    knowledgeNode,
    isExpanded,
    isMatch,
    isEditing,
    isDropTarget,
    branchSide,
    onToggle,
    onZoomRequest,
    onAddChildRequest,
    onEditRequest,
    onDeleteRequest,
    onSaveEdit,
    onCancelEdit,
  } = data;
  const hasChildren = knowledgeNode.children.length > 0;
  const borderClass = isDropTarget
    ? "border-emerald-500 border-dashed ring-2 ring-emerald-100"
    : selected
      ? "border-[color:var(--brand-3)] ring-2 ring-[color:var(--brand-ring)]"
      : isMatch
        ? "border-amber-400 ring-2 ring-amber-100"
        : knowledgeNode.local
          ? "border-dashed border-[color:var(--brand-2)]"
          : "border-[color:var(--brand-line)]";

  const cardClass = `min-w-56 max-w-72 rounded-xl border bg-white/95 p-3 shadow-[0_12px_26px_-20px_var(--brand-shadow)] backdrop-blur transition hover:shadow-[0_16px_32px_-20px_var(--brand-shadow-strong)] ${borderClass}`;

  const [draftTitle, setDraftTitle] = useState(knowledgeNode.title);
  const [draftSummary, setDraftSummary] = useState(knowledgeNode.summary);

  useEffect(() => {
    setDraftTitle(knowledgeNode.title);
    setDraftSummary(knowledgeNode.summary);
  }, [knowledgeNode.title, knowledgeNode.summary, isEditing]);

  function handleToggle(event: MouseEvent<HTMLButtonElement>): void {
    event.stopPropagation();
    onToggle(id);
  }

  function handleDoubleClick(event: MouseEvent<HTMLElement>): void {
    event.stopPropagation();
    onEditRequest();
  }

  function handleAction(event: MouseEvent<HTMLButtonElement>, action: () => void): void {
    event.stopPropagation();
    action();
  }

  function saveEdit(): void {
    onSaveEdit({ title: draftTitle, summary: draftSummary });
  }

  function handleEditorKeyDown(event: KeyboardEvent<HTMLElement>): void {
    // Keep Enter and Delete inside the editor instead of firing the map shortcuts.
    event.stopPropagation();
    if (event.key === "Escape") {
      event.preventDefault();
      onCancelEdit();
      return;
    }
    if (event.key === "Enter" && event.currentTarget instanceof HTMLInputElement) {
      event.preventDefault();
      saveEdit();
    }
  }

  if (isEditing) {
    return (
      <article
        className={cardClass}
        onClick={(event) => event.stopPropagation()}
      >
        <NodeHandles branchSide={branchSide} />
        <input
          aria-label="节点标题"
          autoFocus
          className="w-full rounded border border-slate-300 px-2 py-1 text-sm font-semibold text-slate-900 outline-none focus:border-indigo-400"
          value={draftTitle}
          onChange={(event) => setDraftTitle(event.target.value)}
          onKeyDown={handleEditorKeyDown}
        />
        <textarea
          aria-label="节点内容"
          className="mt-2 h-20 w-full resize-none rounded border border-slate-300 px-2 py-1 text-xs leading-5 text-slate-700 outline-none focus:border-indigo-400"
          placeholder="填写该节点的内容…"
          value={draftSummary}
          onChange={(event) => setDraftSummary(event.target.value)}
          onKeyDown={handleEditorKeyDown}
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            className="rounded bg-indigo-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-indigo-500"
            onClick={(event) => handleAction(event, saveEdit)}
          >
            保存
          </button>
          <button
            type="button"
            className="rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-50"
            onClick={(event) => handleAction(event, onCancelEdit)}
          >
            取消
          </button>
          <span className="text-[10px] text-slate-400">Esc 取消</span>
        </div>
      </article>
    );
  }

  return (
    <article
      className={cardClass}
      title="双击编辑内容"
      onDoubleClick={handleDoubleClick}
    >
      <NodeHandles branchSide={branchSide} />
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">
          {isMatch ? <span aria-label="搜索命中">🔍 </span> : null}
          {knowledgeNode.title || NEW_NODE_TITLE}
        </h3>
        {hasChildren ? (
          <button
            type="button"
            aria-label={`${isExpanded ? "收缩" : "展开"} ${knowledgeNode.title}`}
            onClick={handleToggle}
            className="rounded px-1.5 py-0.5 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
          >
            {isExpanded ? "−" : "+"}
          </button>
        ) : null}
      </div>
      <span
        aria-hidden="true"
        className="mt-2 block h-[3px] w-10 rounded-full bg-gradient-to-r from-[var(--brand-1)] via-[var(--brand-2)] to-[var(--brand-3)]"
      />
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
        {knowledgeNode.summary || "（暂无内容，双击编辑）"}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-1">
        <NodeAction label="＋ 子节点" onClick={(event) => handleAction(event, onAddChildRequest)} />
        <NodeAction label="编辑" onClick={(event) => handleAction(event, onEditRequest)} />
        <NodeAction label="放大" onClick={(event) => handleAction(event, onZoomRequest)} />
        <NodeAction label="删除" onClick={(event) => handleAction(event, onDeleteRequest)} />
        {knowledgeNode.local ? <span className="text-[10px] text-slate-400">本地</span> : null}
      </div>
    </article>
  );
}

/** The root feeds both sides of a balanced map, every other node has one in and one out. */
function NodeHandles({ branchSide }: { branchSide: BranchSide }) {
  if (branchSide === "root") {
    return (
      <>
        <Handle
          type="source"
          id={ROOT_SOURCE_HANDLES.left}
          position={Position.Left}
          className="!bg-slate-400"
        />
        <Handle
          type="source"
          id={ROOT_SOURCE_HANDLES.right}
          position={Position.Right}
          className="!bg-slate-400"
        />
      </>
    );
  }
  return (
    <>
      <Handle
        type="target"
        id={NODE_TARGET_HANDLE}
        position={branchSide === "left" ? Position.Right : Position.Left}
        className="!bg-slate-400"
      />
      <Handle
        type="source"
        id={NODE_SOURCE_HANDLE}
        position={branchSide === "left" ? Position.Left : Position.Right}
        className="!bg-slate-400"
      />
    </>
  );
}

function NodeAction({
  label,
  onClick,
}: {
  label: string;
  onClick: (event: MouseEvent<HTMLButtonElement>) => void;
}) {
  const isPrimary = label.startsWith("＋");
  return (
    <button
      type="button"
      className={`rounded-full border px-2 py-0.5 text-[10px] transition ${
        isPrimary
          ? "border-[color:var(--brand-line)] bg-gradient-to-r from-[var(--brand-soft)] to-[var(--brand-soft-2)] text-[var(--brand-ink)] hover:border-[color:var(--brand-ring-soft)]"
          : "border-slate-200 text-slate-600 hover:border-[color:var(--brand-ring-soft)] hover:bg-[var(--brand-soft)] hover:text-slate-900"
      }`}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
