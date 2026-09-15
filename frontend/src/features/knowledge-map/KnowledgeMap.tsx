"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Edge,
  NodeMouseHandler,
  ReactFlow,
  ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ReactNode } from "react";

import {
  KnowledgeFlowNode,
  ancestorPathIds,
  buildKnowledgeGraph,
  collectExpandablePathIds,
  flowPathForNodeId,
} from "./graph";
import { collectSubtreeIds } from "./editing";
import type { NodeContentPatch } from "./editing";
import { KnowledgeMapNode } from "./KnowledgeMapNode";
import { KnowledgeTree, KnowledgeTreeNode } from "./types";

type KnowledgeMapProps = {
  tree: KnowledgeTree;
  selectedNodeId?: string | null;
  onSelectNode?: (node: KnowledgeTreeNode) => void;
  focusNodeId?: string | null;
  focusNonce?: number;
  highlightedNodeIds?: ReadonlySet<string>;
  editingNodeId?: string | null;
  positionOffsets?: ReadonlyMap<string, { dx: number; dy: number }>;
  onPositionOffsetsChange?: (next: ReadonlyMap<string, { dx: number; dy: number }>) => void;
  onMoveNode?: (node: KnowledgeTreeNode, target: KnowledgeTreeNode) => void;
  onNodeExpandRequest?: (node: KnowledgeTreeNode) => void;
  onAddChildRequest?: (node: KnowledgeTreeNode) => void;
  onEditRequest?: (node: KnowledgeTreeNode) => void;
  onDeleteRequest?: (node: KnowledgeTreeNode) => void;
  onSaveEdit?: (node: KnowledgeTreeNode, patch: NodeContentPatch) => void;
  onCancelEdit?: (node: KnowledgeTreeNode) => void;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
};

const nodeTypes = { knowledge: KnowledgeMapNode };
const EMPTY_OFFSETS: ReadonlyMap<string, { dx: number; dy: number }> = new Map();

export function KnowledgeMap({
  tree,
  selectedNodeId = null,
  onSelectNode,
  focusNodeId = null,
  focusNonce = 0,
  highlightedNodeIds,
  editingNodeId = null,
  positionOffsets,
  onPositionOffsetsChange,
  onMoveNode,
  onNodeExpandRequest,
  onAddChildRequest,
  onEditRequest,
  onDeleteRequest,
  onSaveEdit,
  onCancelEdit,
  isFullscreen = false,
  onToggleFullscreen,
}: KnowledgeMapProps) {
  const [expandedNodeIds, setExpandedNodeIds] = useState<ReadonlySet<string>>(() => new Set(["root"]));
  const [nodes, setNodes, onNodesChange] = useNodesState<KnowledgeFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [focusTarget, setFocusTarget] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);
  const flowRef = useRef<ReactFlowInstance<KnowledgeFlowNode, Edge> | null>(null);
  const draggingNodeRef = useRef<string | null>(null);
  const offsets = positionOffsets ?? EMPTY_OFFSETS;

  const toggleNode = useCallback((nodeId: string): void => {
    setExpandedNodeIds((currentNodeIds) => {
      const nextNodeIds = new Set(currentNodeIds);
      if (nextNodeIds.has(nodeId)) nextNodeIds.delete(nodeId);
      else nextNodeIds.add(nodeId);
      return nextNodeIds;
    });
  }, []);

  const graph = useMemo(
    () =>
      buildKnowledgeGraph(tree, expandedNodeIds, toggleNode, {
        selectedNodeId,
        highlightedNodeIds,
        editingNodeId,
        dropTargetNodeId: dropTargetId,
        positionOffsets: offsets,
        onRequestZoom: onNodeExpandRequest,
        onRequestAddChild: onAddChildRequest,
        onRequestEdit: onEditRequest,
        onRequestDelete: onDeleteRequest,
        onSaveEdit,
        onCancelEdit,
      }),
    [
      editingNodeId,
      dropTargetId,
      offsets,
      expandedNodeIds,
      highlightedNodeIds,
      onAddChildRequest,
      onCancelEdit,
      onDeleteRequest,
      onEditRequest,
      onNodeExpandRequest,
      onSaveEdit,
      selectedNodeId,
      toggleNode,
      tree,
    ],
  );

  useEffect(() => {
    const draggingId = draggingNodeRef.current;
    setNodes((current) => {
      if (!draggingId) return graph.nodes;
      // Keep the card under the pointer while the rest of the graph re-renders.
      const livePositions = new Map(current.map((node) => [node.id, node.position]));
      return graph.nodes.map((node) =>
        node.id === draggingId && livePositions.has(node.id)
          ? { ...node, position: livePositions.get(node.id) ?? node.position }
          : node,
      );
    });
    setEdges(graph.edges);
  }, [graph, setEdges, setNodes]);

  // A new document starts collapsed so the mind map stays readable.
  useEffect(() => {
    setExpandedNodeIds(new Set(["root"]));
  }, [tree.id]);

  useEffect(() => {
    if (!focusNodeId) return;
    const path = flowPathForNodeId(tree, focusNodeId);
    if (!path) return;
    setExpandedNodeIds((current) => new Set([...current, ...ancestorPathIds(path)]));
    setFocusTarget(path);
  }, [focusNodeId, focusNonce, tree]);

  useEffect(() => {
    if (!focusTarget || !nodes.some((node) => node.id === focusTarget)) return;
    flowRef.current?.fitView({ nodes: [{ id: focusTarget }], duration: 500, maxZoom: 1.2, padding: 0.6 });
    setFocusTarget(null);
  }, [focusTarget, nodes]);

  const handleNodeClick: NodeMouseHandler<KnowledgeFlowNode> = useCallback(
    (_, node) => {
      onSelectNode?.(node.data.knowledgeNode);
    },
    [onSelectNode],
  );

  // A node dropped on another node becomes its child; the tree decides the new slot.
  const findDropTarget = useCallback((node: KnowledgeFlowNode): KnowledgeFlowNode | null => {
    const instance = flowRef.current;
    if (!instance) return null;
    const candidate = instance
      .getIntersectingNodes(node)
      .find((other) => other.id !== node.id && !other.id.startsWith(`${node.id}.`));
    return candidate ?? null;
  }, []);

  const handleNodeDrag: NodeMouseHandler<KnowledgeFlowNode> = useCallback(
    (_, node) => {
      draggingNodeRef.current = node.id;
      setDropTargetId(findDropTarget(node)?.data.knowledgeNode.id ?? null);
    },
    [findDropTarget],
  );

  const handleNodeDragStart: NodeMouseHandler<KnowledgeFlowNode> = useCallback((_, node) => {
    draggingNodeRef.current = node.id;
  }, []);

  const handleNodeDragStop: NodeMouseHandler<KnowledgeFlowNode> = useCallback(
    (_, node) => {
      const target = findDropTarget(node);
      setDropTargetId(null);
      draggingNodeRef.current = null;
      const draggedKnowledge = node.data.knowledgeNode;
      if (target) {
        // Dropped on a branch: re-parent, and let the new branch lay the node out.
        onMoveNode?.(draggedKnowledge, target.data.knowledgeNode);
        return;
      }
      // Dropped on empty canvas: the reader placed it there, so keep it there.
      const layoutPosition = graph.nodes.find((item) => item.id === node.id)?.position;
      if (!layoutPosition) return;
      const previous = offsets.get(draggedKnowledge.id) ?? { dx: 0, dy: 0 };
      const delta = {
        dx: previous.dx + (node.position.x - layoutPosition.x),
        dy: previous.dy + (node.position.y - layoutPosition.y),
      };
      const next = new Map(offsets);
      for (const id of collectSubtreeIds(draggedKnowledge)) next.set(id, delta);
      onPositionOffsetsChange?.(next);
    },
    [findDropTarget, graph.nodes, offsets, onMoveNode, onPositionOffsetsChange],
  );

  return (
    <section
      aria-label="知识地图"
      className="knowledge-map relative h-full min-h-[420px] w-full overflow-hidden rounded-2xl border border-[color:var(--brand-line)] bg-white shadow-[0_18px_40px_-32px_var(--brand-shadow)]"
    >
      <div className="absolute right-3 top-3 z-10 flex gap-2">
        <button
          type="button"
          className="rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-xs text-slate-600 shadow-sm backdrop-blur transition hover:border-pink-200 hover:text-slate-900"
          onClick={() => setExpandedNodeIds(new Set(collectExpandablePathIds(tree)))}
        >
          展开全部
        </button>
        <button
          type="button"
          className="rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-xs text-slate-600 shadow-sm backdrop-blur transition hover:border-pink-200 hover:text-slate-900"
          onClick={() => setExpandedNodeIds(new Set(["root"]))}
        >
          收起全部
        </button>
      </div>
      <div className="absolute bottom-3 left-3 z-10 flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white/90 shadow-md backdrop-blur">
        <MapControl label="放大" onClick={() => flowRef.current?.zoomIn()}>
          <span className="text-base leading-none">+</span>
        </MapControl>
        <MapControl label="缩小" onClick={() => flowRef.current?.zoomOut()}>
          <span className="text-base leading-none">−</span>
        </MapControl>
        {onToggleFullscreen ? (
          <MapControl
            label={isFullscreen ? "退出全屏" : "全屏"}
            title={isFullscreen ? "退出全屏（Esc）" : "全屏展示导图"}
            onClick={onToggleFullscreen}
          >
            {isFullscreen ? <CollapseIcon /> : <ExpandIcon />}
          </MapControl>
        ) : null}
        <MapControl
          label="适应窗口"
          onClick={() => flowRef.current?.fitView({ padding: 0.25, duration: 400 })}
        >
          <FitIcon />
        </MapControl>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onNodeDragStart={handleNodeDragStart}
        onNodeDrag={handleNodeDrag}
        onNodeDragStop={handleNodeDragStop}
        onInit={(instance) => {
          flowRef.current = instance;
        }}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.2}
        maxZoom={2}
        nodesConnectable={false}
        deleteKeyCode={null}
        zoomOnDoubleClick={false}
        panOnScroll
        panOnScrollSpeed={0.8}
        zoomOnScroll
        zoomActivationKeyCode="Control"
      >
        <Background gap={20} size={1} color="var(--brand-dots)" />
      </ReactFlow>
      <p className="pointer-events-none absolute bottom-3 left-14 rounded-full bg-white/85 px-3 py-1 text-xs text-slate-500 shadow-sm backdrop-blur">
        空白处拖拽平移 · 拖动节点可改挂到别的分支 · 滚轮上下移动 · Ctrl + 滚轮缩放 · 点击选中 · 回车新增子节点 · 双击编辑 · Delete 删除
      </p>
    </section>
  );
}

type MapControlProps = {
  label: string;
  title?: string;
  onClick: () => void;
  children: ReactNode;
};

function MapControl({ label, title, onClick, children }: MapControlProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={title ?? label}
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center border-b border-slate-200 text-slate-600 transition last:border-b-0 hover:bg-[var(--brand-soft)] hover:text-[var(--brand-ink)]"
    >
      {children}
    </button>
  );
}

function ExpandIcon() {
  return (
    <svg
      aria-hidden="true"
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 2H2v4" />
      <path d="M10 2h4v4" />
      <path d="M10 14h4v-4" />
      <path d="M6 14H2v-4" />
    </svg>
  );
}

function CollapseIcon() {
  return (
    <svg
      aria-hidden="true"
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 6h4V2" />
      <path d="M14 6h-4V2" />
      <path d="M14 10h-4v4" />
      <path d="M2 10h4v4" />
    </svg>
  );
}

function FitIcon() {
  return (
    <svg
      aria-hidden="true"
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 6V2h4" />
      <path d="M14 6V2h-4" />
      <path d="M14 10v4h-4" />
      <path d="M2 10v4h4" />
      <rect x="5.5" y="5.5" width="5" height="5" rx="1" />
    </svg>
  );
}
