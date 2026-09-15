import { KnowledgeTree, KnowledgeTreeNode } from "./types";

export const MAX_SEARCH_RESULTS = 20;

/** Depth-first list of every node in the tree, root first. */
export function flattenKnowledgeNodes(tree: KnowledgeTree): KnowledgeTreeNode[] {
  const nodes: KnowledgeTreeNode[] = [];
  function visit(node: KnowledgeTreeNode): void {
    nodes.push(node);
    node.children.forEach(visit);
  }
  visit(tree);
  return nodes;
}

export function filterKnowledgeNodes(
  tree: KnowledgeTree,
  query: string,
  limit: number = MAX_SEARCH_RESULTS,
): KnowledgeTreeNode[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return [];
  return flattenKnowledgeNodes(tree)
    .filter((node) =>
      [node.title, node.summary, ...node.keywords].some((field) => field.toLowerCase().includes(needle)),
    )
    .slice(0, limit);
}
