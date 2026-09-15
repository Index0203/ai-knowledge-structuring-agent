import type { KnowledgeTreeNode as ApiKnowledgeTreeNode } from "@/lib/api/documents";

export type KnowledgeMapMode = "mindmap" | "knowledge";

/** Map node: the API shape plus the flag for nodes the reader added locally. */
export type KnowledgeTreeNode = Omit<ApiKnowledgeTreeNode, "children"> & {
  local?: boolean;
  children: KnowledgeTreeNode[];
};

export type KnowledgeTree = KnowledgeTreeNode;
