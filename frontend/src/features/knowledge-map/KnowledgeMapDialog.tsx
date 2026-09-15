"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";

import {
  NodeContentPatch,
  addChildNode,
  collectSubtreeIds,
  deleteNode,
  findNode,
  findParentId,
  moveNode,
  updateNodeContent,
} from "./editing";
import { KnowledgeMap } from "./KnowledgeMap";
import { KnowledgeNodeDialog } from "./KnowledgeNodeDialog";
import { KnowledgeNodeDetails } from "./KnowledgeNodeDetails";
import { KnowledgeNodeQa } from "./KnowledgeNodeQa";
import { NodeSearch } from "./NodeSearch";
import { KnowledgeMapMode, KnowledgeTree, KnowledgeTreeNode } from "./types";
import { downloadXmindFile } from "./xmind";

export type { KnowledgeMapMode } from "./types";

type KnowledgeMapDialogProps = {
  tree: KnowledgeTree;
  mode: KnowledgeMapMode;
  onClose: () => void;
  onTreeChange?: (tree: KnowledgeTree) => void;
};

type MapSnapshot = {
  tree: KnowledgeTree;
  offsets: ReadonlyMap<string, { dx: number; dy: number }>;
};

const HISTORY_LIMIT = 50;

export function KnowledgeMapDialog({ tree, mode, onClose, onTreeChange }: KnowledgeMapDialogProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  // The map is editable, so the dialog works on its own copy of the tree.
  const [draftTree, setDraftTree] = useState<KnowledgeTree>(tree);
  const [offsets, setOffsets] = useState<ReadonlyMap<string, { dx: number; dy: number }>>(new Map());
  const pastRef = useRef<MapSnapshot[]>([]);
  const futureRef = useRef<MapSnapshot[]>([]);
  const [, setHistoryTick] = useState(0);
  const [selectedNode, setSelectedNode] = useState<KnowledgeTreeNode | null>(null);
  const [enlargedNode, setEnlargedNode] = useState<KnowledgeTreeNode | null>(null);
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ nodeId: string; nonce: number } | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const highlightedNodeIds = useMemo(
    () => (focus ? new Set([focus.nodeId]) : new Set<string>()),
    [focus],
  );
  const isKnowledgeMode = mode === "knowledge";

  useEffect(() => {
    setDraftTree(tree);
    setOffsets(new Map());
    pastRef.current = [];
    futureRef.current = [];
    setHistoryTick((tick) => tick + 1);
  }, [tree.id]);

  useEffect(() => {
    function handleFullscreenChange(): void {
      const active = document.fullscreenElement === containerRef.current;
      setIsFullscreen(active);
      if (active) setAssistantOpen(false);
    }
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  useEffect(
    () => () => {
      // Closing the dialog must not leave the browser in fullscreen.
      if (document.fullscreenElement && typeof document.exitFullscreen === "function") {
        void document.exitFullscreen().catch(() => undefined);
      }
    },
    [],
  );

  const toggleFullscreen = useCallback((): void => {
    const element = containerRef.current;
    if (isFullscreen) {
      if (document.fullscreenElement && typeof document.exitFullscreen === "function") {
        void document.exitFullscreen().catch(() => undefined);
      }
      setIsFullscreen(false);
      return;
    }
    setAssistantOpen(false);
    if (element && typeof element.requestFullscreen === "function") {
      // A blocked or unavailable Fullscreen API still fills the window.
      void element.requestFullscreen().catch(() => setIsFullscreen(true));
      return;
    }
    setIsFullscreen(true);
  }, [isFullscreen]);

  const handleNodeSelection = useCallback((node: KnowledgeTreeNode): void => {
    setSelectedNode(node);
    setAssistantOpen(true);
  }, []);

  const pushHistory = useCallback((): void => {
    pastRef.current = [...pastRef.current, { tree: draftTree, offsets }].slice(-HISTORY_LIMIT);
    futureRef.current = [];
    setHistoryTick((tick) => tick + 1);
  }, [draftTree, offsets]);

  /** Every edit goes through here, so Ctrl+Z can always step one operation back. */
  const commit = useCallback(
    (nextTree: KnowledgeTree, nextOffsets: ReadonlyMap<string, { dx: number; dy: number }> = offsets): void => {
      pushHistory();
      setDraftTree(nextTree);
      setOffsets(nextOffsets);
      onTreeChange?.(nextTree);
    },
    [offsets, onTreeChange, pushHistory],
  );

  const restore = useCallback(
    (snapshot: MapSnapshot): void => {
      setDraftTree(snapshot.tree);
      setOffsets(snapshot.offsets);
      onTreeChange?.(snapshot.tree);
      setEditingNodeId(null);
      setSelectedNode((current) => (current ? findNode(snapshot.tree, current.id) : null));
    },
    [onTreeChange],
  );

  const undo = useCallback((): void => {
    const previous = pastRef.current.at(-1);
    if (!previous) return;
    pastRef.current = pastRef.current.slice(0, -1);
    futureRef.current = [...futureRef.current, { tree: draftTree, offsets }];
    setHistoryTick((tick) => tick + 1);
    restore(previous);
  }, [draftTree, offsets, restore]);

  const redo = useCallback((): void => {
    const next = futureRef.current.at(-1);
    if (!next) return;
    futureRef.current = futureRef.current.slice(0, -1);
    pastRef.current = [...pastRef.current, { tree: draftTree, offsets }];
    setHistoryTick((tick) => tick + 1);
    restore(next);
  }, [draftTree, offsets, restore]);

  const handleAddChild = useCallback(
    (node: KnowledgeTreeNode): void => {
      const result = addChildNode(draftTree, node.id);
      if (!result) return;
      commit(result.tree);
      const created = findNode(result.tree, result.nodeId);
      if (!created) return;
      setSelectedNode(created);
      setEditingNodeId(created.id);
      // Make sure the new node's branch is open and in view.
      setFocus((current) => ({ nodeId: created.id, nonce: (current?.nonce ?? 0) + 1 }));
    },
    [commit, draftTree],
  );

  const handleDeleteNode = useCallback(
    (node: KnowledgeTreeNode): void => {
      const parentId = findParentId(draftTree, node.id);
      const nextTree = deleteNode(draftTree, node.id);
      if (!nextTree) return; // The root node stays.
      commit(nextTree);
      setEditingNodeId(null);
      setEnlargedNode(null);
      setSelectedNode(parentId ? findNode(nextTree, parentId) : nextTree);
    },
    [commit, draftTree],
  );

  const handleSaveEdit = useCallback(
    (node: KnowledgeTreeNode, patch: NodeContentPatch): void => {
      commit(updateNodeContent(draftTree, node.id, patch));
      setEditingNodeId(null);
    },
    [commit, draftTree],
  );

  const handleEditRequest = useCallback((node: KnowledgeTreeNode): void => {
    setSelectedNode(node);
    setEditingNodeId(node.id);
  }, []);

  const handleMoveNode = useCallback(
    (node: KnowledgeTreeNode, target: KnowledgeTreeNode): void => {
      const nextTree = moveNode(draftTree, node.id, target.id);
      if (!nextTree) return;
      const nextOffsets = new Map(offsets);
      for (const id of collectSubtreeIds(node)) nextOffsets.delete(id);
      commit(nextTree, nextOffsets);
      const moved = findNode(nextTree, node.id);
      if (!moved) return;
      setSelectedNode(moved);
      setEditingNodeId(null);
      // Open the new branch and bring the moved node back into view.
      setFocus((current) => ({ nodeId: moved.id, nonce: (current?.nonce ?? 0) + 1 }));
    },
    [commit, draftTree, offsets],
  );

  const handleOffsetsChange = useCallback(
    (next: ReadonlyMap<string, { dx: number; dy: number }>): void => {
      commit(draftTree, next);
    },
    [commit, draftTree],
  );

  const handleCancelEdit = useCallback((): void => {
    setEditingNodeId(null);
  }, []);

  const handleSearchSelection = useCallback((node: KnowledgeTreeNode): void => {
    setSelectedNode(node);
    setAssistantOpen(true);
    setFocus((current) => ({ nodeId: node.id, nonce: (current?.nonce ?? 0) + 1 }));
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        // The enlarged node window handles Escape on its own while it is open.
        if (enlargedNode) return;
        // In fullscreen the first Escape leaves fullscreen; the dialog stays open.
        if (document.fullscreenElement) return;
        if (isFullscreen) {
          setIsFullscreen(false);
          return;
        }
        onClose();
        return;
      }
      if (isTypingTarget(event.target)) return;
      if (event.ctrlKey || event.metaKey) {
        const key = event.key.toLowerCase();
        if (key === "z") {
          event.preventDefault();
          if (event.shiftKey) redo();
          else undo();
          return;
        }
        if (key === "y") {
          event.preventDefault();
          redo();
          return;
        }
      }
      if (!selectedNode) return;
      if (event.key === "Enter") {
        event.preventDefault();
        handleAddChild(selectedNode);
        return;
      }
      if (event.key === "Delete") {
        event.preventDefault();
        handleDeleteNode(selectedNode);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    enlargedNode,
    handleAddChild,
    handleDeleteNode,
    isFullscreen,
    onClose,
    redo,
    selectedNode,
    undo,
  ]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={isKnowledgeMode ? "知识地图" : "思维导图"}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
    >
      <div
        ref={containerRef}
        className={
          isFullscreen
            ? "flex h-full w-full flex-col overflow-hidden bg-white"
            : "flex h-[92vh] w-[96vw] max-w-[1500px] flex-col overflow-hidden rounded-3xl border border-white/70 bg-white/95 shadow-[0_30px_80px_-40px_var(--brand-shadow)] backdrop-blur"
        }
      >
        <header className="flex flex-wrap items-center gap-3 border-b border-[color:var(--brand-line)] bg-gradient-to-r from-[var(--brand-soft)] via-white to-[var(--brand-soft-2)] px-5 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-slate-900">{draftTree.title}</h2>
            <p className="text-xs text-slate-500">
              {isKnowledgeMode
                ? "知识地图 · 回车新增子节点、双击编辑、Delete 删除 · 编辑结果请用「下载 XMind」保存"
                : "思维导图 · 回车新增子节点、双击编辑、Delete 删除 · 编辑结果请用「下载 XMind」保存"}
            </p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {isKnowledgeMode ? (
              <NodeSearch tree={draftTree} onSelectNode={handleSearchSelection} />
            ) : null}
            <button
              type="button"
              className="rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 text-sm text-slate-600 transition hover:border-pink-200 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-200"
              disabled={pastRef.current.length === 0}
              title="撤销上一步（Ctrl + Z）"
              onClick={undo}
            >
              撤销
            </button>
            <button
              type="button"
              className="rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 text-sm text-slate-600 transition hover:border-pink-200 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-200"
              disabled={futureRef.current.length === 0}
              title="重做（Ctrl + Shift + Z）"
              onClick={redo}
            >
              重做
            </button>
            <button
              type="button"
              className="rounded-full bg-gradient-to-r from-[var(--brand-1)] via-[var(--brand-2)] to-[var(--brand-3)] px-4 py-1.5 text-sm font-medium text-white shadow-[0_12px_26px_-14px_var(--brand-shadow-strong)] transition hover:-translate-y-0.5"
              title="把当前（含你新增、修改、移动、删除的）导图下载为 .xmind 文件"
              onClick={() => downloadXmindFile(draftTree)}
            >
              下载 XMind
            </button>
            <button
              type="button"
              className="rounded-full border border-slate-200 bg-white/80 px-4 py-1.5 text-sm text-slate-600 transition hover:border-pink-200 hover:text-slate-900"
              onClick={onClose}
            >
              关闭 (Esc)
            </button>
          </div>
        </header>
        <div className="relative flex min-h-0 flex-1 gap-3 bg-gradient-to-b from-white to-[var(--brand-soft)] p-3">
          <div className="min-w-0 flex-1">
            <KnowledgeMap
              tree={draftTree}
              selectedNodeId={selectedNode?.id ?? null}
              onSelectNode={handleNodeSelection}
              focusNodeId={focus?.nodeId ?? null}
              focusNonce={focus?.nonce ?? 0}
              highlightedNodeIds={highlightedNodeIds}
              editingNodeId={editingNodeId}
              positionOffsets={offsets}
              onPositionOffsetsChange={handleOffsetsChange}
              onNodeExpandRequest={setEnlargedNode}
              onAddChildRequest={handleAddChild}
              onEditRequest={handleEditRequest}
              onDeleteRequest={handleDeleteNode}
              onMoveNode={handleMoveNode}
              onSaveEdit={handleSaveEdit}
              onCancelEdit={handleCancelEdit}
              isFullscreen={isFullscreen}
              onToggleFullscreen={toggleFullscreen}
            />
          </div>
          {isKnowledgeMode && !isFullscreen ? (
            <aside className="w-[22rem] shrink-0 space-y-3 overflow-y-auto pr-1">
              <KnowledgeNodeDetails node={selectedNode} onClose={() => setSelectedNode(null)} />
              {selectedNode ? <KnowledgeNodeQa node={selectedNode} /> : null}
            </aside>
          ) : null}
          {isKnowledgeMode && isFullscreen ? (
            <FloatingNodeAssistant
              open={assistantOpen}
              node={selectedNode}
              onOpen={() => setAssistantOpen(true)}
              onCollapse={() => setAssistantOpen(false)}
              onClearNode={() => setSelectedNode(null)}
            />
          ) : null}
        </div>
        {/* Rendered inside the dialog so the enlarged node view also shows in fullscreen. */}
        {enlargedNode ? (
          <KnowledgeNodeDialog node={enlargedNode} mode={mode} onClose={() => setEnlargedNode(null)} />
        ) : null}
      </div>
    </div>
  );
}

type FloatingNodeAssistantProps = {
  open: boolean;
  node: KnowledgeTreeNode | null;
  onOpen: () => void;
  onCollapse: () => void;
  onClearNode: () => void;
};

const PANEL_MARGIN = 12;
const PANEL_WIDTH = 384;
const DRAG_THRESHOLD = 4;

type PanelPosition = { x: number; y: number };

function clampToViewport(x: number, y: number, width: number, height: number): PanelPosition {
  const maxX = Math.max(PANEL_MARGIN, window.innerWidth - width - PANEL_MARGIN);
  const maxY = Math.max(PANEL_MARGIN, window.innerHeight - height - PANEL_MARGIN);
  return {
    x: Math.min(Math.max(x, PANEL_MARGIN), maxX),
    y: Math.min(Math.max(y, PANEL_MARGIN), maxY),
  };
}

/**
 * Fullscreen assistant: the map takes the whole window, so the node services
 * float beside it and only expand once the reader picks a node. Dragging the
 * header parks the panel anywhere on screen, and it stays where it was dropped.
 */
function FloatingNodeAssistant({
  open,
  node,
  onOpen,
  onCollapse,
  onClearNode,
}: FloatingNodeAssistantProps) {
  const panelRef = useRef<HTMLElement | null>(null);
  const pillRef = useRef<HTMLButtonElement | null>(null);
  const gesture = useRef<{
    pointerId: number;
    offsetX: number;
    offsetY: number;
    width: number;
    height: number;
    startX: number;
    startY: number;
    moved: boolean;
  } | null>(null);
  const dragMovedRef = useRef(false);
  const [position, setPosition] = useState<PanelPosition | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    function handleResize(): void {
      const element = panelRef.current ?? pillRef.current;
      if (!element) return;
      const rect = element.getBoundingClientRect();
      setPosition((current) =>
        current ? clampToViewport(current.x, current.y, rect.width, rect.height) : current,
      );
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Re-clamp once the panel is shown, so a pill parked near an edge still fits.
  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    setPosition((current) =>
      current ? clampToViewport(current.x, current.y, rect.width, rect.height) : current,
    );
  }, [open]);

  const startDrag = useCallback(
    (event: ReactPointerEvent<HTMLElement>, element: HTMLElement | null): void => {
      if (!element || event.button !== 0) return;
      const rect = element.getBoundingClientRect();
      gesture.current = {
        pointerId: event.pointerId,
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top,
        width: rect.width,
        height: rect.height,
        startX: event.clientX,
        startY: event.clientY,
        moved: false,
      };
      dragMovedRef.current = false;
      event.currentTarget.setPointerCapture?.(event.pointerId);
    },
    [],
  );

  const moveDrag = useCallback((event: ReactPointerEvent<HTMLElement>): void => {
    const current = gesture.current;
    if (!current) return;
    if (!current.moved) {
      const travelled = Math.hypot(event.clientX - current.startX, event.clientY - current.startY);
      if (travelled < DRAG_THRESHOLD) return;
      current.moved = true;
      dragMovedRef.current = true;
      setIsDragging(true);
    }
    event.preventDefault();
    setPosition(
      clampToViewport(
        event.clientX - current.offsetX,
        event.clientY - current.offsetY,
        current.width,
        current.height,
      ),
    );
  }, []);

  const endDrag = useCallback((event: ReactPointerEvent<HTMLElement>): void => {
    const current = gesture.current;
    if (!current) return;
    gesture.current = null;
    setIsDragging(false);
    if (event.currentTarget.hasPointerCapture?.(current.pointerId)) {
      event.currentTarget.releasePointerCapture(current.pointerId);
    }
  }, []);

  if (!open) {
    return (
      <button
        ref={pillRef}
        type="button"
        style={position ? { left: position.x, top: position.y } : undefined}
        className={`z-30 cursor-move touch-none rounded-full bg-gradient-to-r from-[var(--brand-1)] via-[var(--brand-2)] to-[var(--brand-3)] px-4 py-2 text-sm font-medium text-white shadow-[0_14px_30px_-16px_var(--brand-shadow-strong)] transition hover:-translate-y-0.5 ${
          position ? "fixed" : "absolute right-3 top-3"
        }`}
        onPointerDown={(event) => startDrag(event, pillRef.current)}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onClick={() => {
          // A drag ends with a click event; that gesture should not open the panel.
          if (dragMovedRef.current) {
            dragMovedRef.current = false;
            return;
          }
          onOpen();
        }}
      >
        节点 AI 助手
      </button>
    );
  }

  const panelStyle: CSSProperties = position
    ? { left: position.x, top: position.y, width: PANEL_WIDTH }
    : { width: PANEL_WIDTH };

  return (
    <aside
      ref={panelRef}
      aria-label="节点 AI 助手面板"
      style={panelStyle}
      className={`z-30 flex max-h-[calc(100%-1.5rem)] flex-col overflow-hidden rounded-2xl border border-[color:var(--brand-line)] bg-white/95 shadow-[0_30px_70px_-40px_var(--brand-shadow)] backdrop-blur ${
        position ? "fixed" : "absolute right-3 top-3"
      } ${isDragging ? "select-none" : ""}`}
    >
      <header
        aria-label="拖动移动面板"
        title="按住拖动，可把面板停在任意位置"
        className="flex cursor-move touch-none items-center justify-between gap-3 border-b border-[color:var(--brand-line)] bg-gradient-to-r from-[var(--brand-soft)] via-white to-[var(--brand-soft-2)] px-4 py-2.5"
        onPointerDown={(event) => startDrag(event, panelRef.current)}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          <DragHandleIcon />
          节点 AI 助手
        </span>
        <button
          type="button"
          onPointerDown={(event) => event.stopPropagation()}
          className="rounded-full px-2.5 py-1 text-xs text-slate-500 transition hover:bg-[var(--brand-soft-2)] hover:text-[var(--brand-ink)]"
          onClick={onCollapse}
        >
          收起
        </button>
      </header>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        <KnowledgeNodeDetails node={node} onClose={onClearNode} variant="floating" />
        {node ? <KnowledgeNodeQa node={node} /> : null}
      </div>
    </aside>
  );
}

/** Enter and Delete belong to the focused control, not to the map shortcuts. */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(target.tagName);
}

function DragHandleIcon() {
  return (
    <svg
      aria-hidden="true"
      width="10"
      height="14"
      viewBox="0 0 10 14"
      fill="currentColor"
      className="text-slate-400"
    >
      <circle cx="2.5" cy="3" r="1.1" />
      <circle cx="7.5" cy="3" r="1.1" />
      <circle cx="2.5" cy="7" r="1.1" />
      <circle cx="7.5" cy="7" r="1.1" />
      <circle cx="2.5" cy="11" r="1.1" />
      <circle cx="7.5" cy="11" r="1.1" />
    </svg>
  );
}
