import { KnowledgeTree, KnowledgeTreeNode } from "./types";

export type NodeContentPatch = {
  title: string;
  summary: string;
};

export type AddChildResult = {
  tree: KnowledgeTree;
  nodeId: string;
};

export const NEW_NODE_TITLE = "新节点";

let localNodeCounter = 0;

/** Ids for reader-created nodes never collide with backend uuids. */
export function createLocalNodeId(): string {
  localNodeCounter += 1;
  return `local-${localNodeCounter}`;
}

export function findNode(node: KnowledgeTreeNode, nodeId: string): KnowledgeTreeNode | null {
  if (node.id === nodeId) return node;
  for (const child of node.children) {
    const found = findNode(child, nodeId);
    if (found) return found;
  }
  return null;
}

export function findParentId(tree: KnowledgeTree, nodeId: string): string | null {
  for (const child of tree.children) {
    if (child.id === nodeId) return tree.id;
    const found = findParentId(child, nodeId);
    if (found) return found;
  }
  return null;
}

export function countTreeNodes(node: KnowledgeTreeNode): number {
  return 1 + node.children.reduce((total, child) => total + countTreeNodes(child), 0);
}

/** The node itself plus every descendant, used when a branch moves as one block. */
export function collectSubtreeIds(node: KnowledgeTreeNode): string[] {
  return [node.id, ...node.children.flatMap((child) => collectSubtreeIds(child))];
}

/** Append an empty child under `parentId` and return its generated id. */
export function addChildNode(tree: KnowledgeTree, parentId: string): AddChildResult | null {
  const parent = findNode(tree, parentId);
  if (!parent) return null;
  const nodeId = createLocalNodeId();
  const child: KnowledgeTreeNode = {
    id: nodeId,
    title: NEW_NODE_TITLE,
    summary: "",
    keywords: [],
    source_section_indexes: [],
    depth: parent.depth + 1,
    children: [],
    local: true,
  };
  return {
    tree: mapNode(tree, (node) =>
      node.id === parentId ? { ...node, children: [...node.children, child] } : node,
    ),
    nodeId,
  };
}

export function updateNodeContent(
  tree: KnowledgeTree,
  nodeId: string,
  patch: NodeContentPatch,
): KnowledgeTree {
  const title = patch.title.trim() || NEW_NODE_TITLE;
  return mapNode(tree, (node) => (node.id === nodeId ? { ...node, title, summary: patch.summary } : node));
}

/** Remove a node together with its subtree. The root cannot be removed. */
export function deleteNode(tree: KnowledgeTree, nodeId: string): KnowledgeTree | null {
  if (tree.id === nodeId) return null;
  return mapNode(tree, (node) => ({
    ...node,
    children: node.children.filter((child) => child.id !== nodeId),
  }));
}

export function isDescendantOf(tree: KnowledgeTree, ancestorId: string, nodeId: string): boolean {
  const ancestor = findNode(tree, ancestorId);
  return ancestor ? containsNode(ancestor, nodeId) : false;
}

/**
 * Move a node (with its subtree) under another node, like dragging a branch in
 * a mind map. Returns null when the move would break the tree: the root cannot
 * move, a node cannot become its own parent or child.
 */
export function moveNode(
  tree: KnowledgeTree,
  nodeId: string,
  newParentId: string,
): KnowledgeTree | null {
  if (nodeId === tree.id || nodeId === newParentId) return null;
  const node = findNode(tree, nodeId);
  const newParent = findNode(tree, newParentId);
  if (!node || !newParent || containsNode(node, newParentId)) return null;

  const detached = deleteNode(tree, nodeId);
  if (!detached) return null;
  return appendChild(detached, newParentId, withDepth(node, newParent.depth + 1));
}

function appendChild(
  tree: KnowledgeTree,
  parentId: string,
  child: KnowledgeTreeNode,
): KnowledgeTree {
  return mapNode(tree, (node) =>
    node.id === parentId ? { ...node, children: [...node.children, child] } : node,
  );
}

function withDepth(node: KnowledgeTreeNode, depth: number): KnowledgeTreeNode {
  return {
    ...node,
    depth,
    children: node.children.map((child) => withDepth(child, depth + 1)),
  };
}

function containsNode(node: KnowledgeTreeNode, nodeId: string): boolean {
  return node.children.some((child) => child.id === nodeId || containsNode(child, nodeId));
}

function mapNode(
  node: KnowledgeTreeNode,
  transform: (node: KnowledgeTreeNode) => KnowledgeTreeNode,
): KnowledgeTreeNode {
  const mapped = transform(node);
  return { ...mapped, children: mapped.children.map((child) => mapNode(child, transform)) };
}
