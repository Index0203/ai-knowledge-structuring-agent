import { Edge, Node } from "@xyflow/react";

import { NodeContentPatch } from "./editing";
import { BranchSide, layoutTree } from "./layout";
import { KnowledgeTree, KnowledgeTreeNode } from "./types";

export type KnowledgeFlowNodeData = {
  knowledgeNode: KnowledgeTreeNode;
  isExpanded: boolean;
  hasChildren: boolean;
  isMatch: boolean;
  isEditing: boolean;
  isDropTarget: boolean;
  branchSide: BranchSide;
  onToggle: (nodeId: string) => void;
  onZoomRequest: () => void;
  onAddChildRequest: () => void;
  onEditRequest: () => void;
  onDeleteRequest: () => void;
  onSaveEdit: (patch: NodeContentPatch) => void;
  onCancelEdit: () => void;
};

export type KnowledgeFlowNode = Node<KnowledgeFlowNodeData, "knowledge">;

export type KnowledgeGraph = {
  nodes: KnowledgeFlowNode[];
  edges: Edge[];
};

/** Handle ids, so edges can leave the root on the correct side of a balanced map. */
export const ROOT_SOURCE_HANDLES: Record<Exclude<BranchSide, "root">, string> = {
  left: "source-left",
  right: "source-right",
};
export const NODE_SOURCE_HANDLE = "source";
export const NODE_TARGET_HANDLE = "target";
/** Curved branches, so siblings of one parent never stack on the same vertical line. */
export const BRANCH_EDGE_TYPE = "bezier";
export const BRANCH_EDGE_STYLE = {
  stroke: "var(--brand-edge)",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
};

export type BuildGraphOptions = {
  selectedNodeId?: string | null;
  highlightedNodeIds?: ReadonlySet<string>;
  editingNodeId?: string | null;
  dropTargetNodeId?: string | null;
  /** Freed positions the reader dragged nodes to, keyed by backend node id. */
  positionOffsets?: ReadonlyMap<string, { dx: number; dy: number }>;
  onRequestZoom?: (node: KnowledgeTreeNode) => void;
  onRequestAddChild?: (node: KnowledgeTreeNode) => void;
  onRequestEdit?: (node: KnowledgeTreeNode) => void;
  onRequestDelete?: (node: KnowledgeTreeNode) => void;
  onSaveEdit?: (node: KnowledgeTreeNode, patch: NodeContentPatch) => void;
  onCancelEdit?: (node: KnowledgeTreeNode) => void;
};

type VisibleNode = {
  id: string;
  node: KnowledgeTreeNode;
  isExpanded: boolean;
  children: VisibleNode[];
};

export function buildKnowledgeGraph(
  tree: KnowledgeTree,
  expandedNodeIds: ReadonlySet<string>,
  onToggle: (nodeId: string) => void,
  options: BuildGraphOptions = {},
): KnowledgeGraph {
  const highlighted = options.highlightedNodeIds ?? new Set<string>();
  const root = buildVisibleTree(tree, "root", expandedNodeIds);
  const offsets = layoutTree(root);

  const nodes: KnowledgeFlowNode[] = [];
  const edges: Edge[] = [];

  function visit(visible: VisibleNode, parentId?: string): void {
    const offset = offsets.get(visible.id) ?? { x: 0, y: 0, side: "root" as BranchSide };
    const shift = options.positionOffsets?.get(visible.node.id);
    nodes.push({
      id: visible.id,
      type: "knowledge",
      position: { x: offset.x + (shift?.dx ?? 0), y: offset.y + (shift?.dy ?? 0) },
      selected: options.selectedNodeId != null && visible.node.id === options.selectedNodeId,
      data: {
        knowledgeNode: visible.node,
        isExpanded: visible.isExpanded,
        hasChildren: visible.node.children.length > 0,
        isMatch: highlighted.has(visible.node.id),
        isEditing: options.editingNodeId != null && visible.node.id === options.editingNodeId,
        isDropTarget: options.dropTargetNodeId != null && visible.node.id === options.dropTargetNodeId,
        branchSide: offset.side,
        onToggle,
        onZoomRequest: () => options.onRequestZoom?.(visible.node),
        onAddChildRequest: () => options.onRequestAddChild?.(visible.node),
        onEditRequest: () => options.onRequestEdit?.(visible.node),
        onDeleteRequest: () => options.onRequestDelete?.(visible.node),
        onSaveEdit: (patch) => options.onSaveEdit?.(visible.node, patch),
        onCancelEdit: () => options.onCancelEdit?.(visible.node),
      },
    });
    if (parentId) {
      const fromRoot = parentId === "root";
      edges.push({
        id: `${parentId}-${visible.id}`,
        source: parentId,
        target: visible.id,
        sourceHandle: fromRoot
          ? ROOT_SOURCE_HANDLES[offset.side === "left" ? "left" : "right"]
          : NODE_SOURCE_HANDLE,
        targetHandle: NODE_TARGET_HANDLE,
        type: BRANCH_EDGE_TYPE,
        style: BRANCH_EDGE_STYLE,
      });
    }
    visible.children.forEach((child) => visit(child, visible.id));
  }

  visit(root);
  return { nodes, edges };
}

function buildVisibleTree(
  node: KnowledgeTreeNode,
  id: string,
  expandedNodeIds: ReadonlySet<string>,
): VisibleNode {
  const isExpanded = expandedNodeIds.has(id);
  return {
    id,
    node,
    isExpanded,
    children: isExpanded
      ? node.children.map((child, index) => buildVisibleTree(child, `${id}.${index}`, expandedNodeIds))
      : [],
  };
}

/** React Flow id ("root.0.1") for a backend node id, if the node is in the tree. */
export function flowPathForNodeId(tree: KnowledgeTree, nodeId: string): string | null {
  function search(node: KnowledgeTreeNode, id: string): string | null {
    if (node.id === nodeId) return id;
    for (const [index, child] of node.children.entries()) {
      const found = search(child, `${id}.${index}`);
      if (found) return found;
    }
    return null;
  }
  return search(tree, "root");
}

/** Every ancestor path that must be expanded before a node becomes visible. */
export function ancestorPathIds(path: string): string[] {
  const segments = path.split(".");
  const ancestors: string[] = [];
  for (let index = 1; index < segments.length; index += 1) {
    ancestors.push(segments.slice(0, index).join("."));
  }
  return ancestors;
}

export function collectExpandablePathIds(tree: KnowledgeTree): string[] {
  const ids: string[] = [];
  function visit(node: KnowledgeTreeNode, id: string): void {
    if (node.children.length > 0) {
      ids.push(id);
      node.children.forEach((child, index) => visit(child, `${id}.${index}`));
    }
  }
  visit(tree, "root");
  return ids;
}
