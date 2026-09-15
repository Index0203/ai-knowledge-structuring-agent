import { describe, expect, it, vi } from "vitest";

import { ancestorPathIds, buildKnowledgeGraph, flowPathForNodeId } from "./graph";
import { KnowledgeTree } from "./types";

const knowledgeTree: KnowledgeTree = {
  id: "root-id",
  title: "Document",
  summary: "Root summary",
  keywords: [],
  source_section_indexes: [],
  depth: 0,
  children: [
    {
      id: "topic-id",
      title: "Topic",
      summary: "Summary",
      keywords: ["keyword"],
      source_section_indexes: [0],
      depth: 1,
      children: [
        {
          id: "detail-id",
          title: "Detail",
          summary: "Detail summary",
          keywords: [],
          source_section_indexes: [1],
          depth: 2,
          children: [],
        },
      ],
    },
  ],
};

describe("buildKnowledgeGraph", () => {
  it("only includes descendants of expanded nodes", () => {
    const collapsedGraph = buildKnowledgeGraph(knowledgeTree, new Set(["root"]), () => undefined);
    const expandedGraph = buildKnowledgeGraph(knowledgeTree, new Set(["root", "root.0"]), () => undefined);

    expect(collapsedGraph.nodes.map((node) => node.id)).toEqual(["root", "root.0"]);
    expect(expandedGraph.nodes.map((node) => node.id)).toEqual(["root", "root.0", "root.0.0"]);
    expect(expandedGraph.edges).toHaveLength(2);
  });

  it("keeps the backend node id on every flow node", () => {
    const graph = buildKnowledgeGraph(knowledgeTree, new Set(["root", "root.0"]), () => undefined);

    expect(graph.nodes.map((node) => node.data.knowledgeNode.id)).toEqual(["root-id", "topic-id", "detail-id"]);
  });

  it("locates a node path and the ancestors that must be expanded", () => {
    expect(flowPathForNodeId(knowledgeTree, "detail-id")).toBe("root.0.0");
    expect(flowPathForNodeId(knowledgeTree, "missing")).toBeNull();
    expect(ancestorPathIds("root.0.0")).toEqual(["root", "root.0"]);
  });

  it("marks highlighted nodes for search results", () => {
    const graph = buildKnowledgeGraph(knowledgeTree, new Set(["root"]), () => undefined, {
      highlightedNodeIds: new Set(["topic-id"]),
    });

    expect(graph.nodes.map((node) => node.data.isMatch)).toEqual([false, true]);
  });

  it("lets a node request an enlarged view of its own content", () => {
    const onRequestZoom = vi.fn();
    const graph = buildKnowledgeGraph(knowledgeTree, new Set(["root", "root.0"]), () => undefined, {
      onRequestZoom,
    });

    graph.nodes[1].data.onZoomRequest();

    expect(onRequestZoom).toHaveBeenCalledWith(expect.objectContaining({ id: "topic-id" }));
  });

  it("routes the left branch of a balanced map from the root's left handle", () => {
    const balancedTree: KnowledgeTree = {
      ...knowledgeTree,
      children: [
        { ...knowledgeTree.children[0], id: "first-id", children: [] },
        { ...knowledgeTree.children[0], id: "second-id", children: [] },
      ],
    };

    const graph = buildKnowledgeGraph(
      balancedTree,
      new Set(["root", "root.0", "root.1"]),
      () => undefined,
    );
    const sides = new Map(graph.nodes.map((node) => [node.id, node.data.branchSide]));
    expect(sides.get("root")).toBe("root");
    expect(sides.get("root.0")).toBe("right");
    expect(sides.get("root.1")).toBe("left");

    const leftEdge = graph.edges.find((edge) => edge.target === "root.1");
    expect(leftEdge?.sourceHandle).toBe("source-left");
    expect(leftEdge?.targetHandle).toBe("target");
    const rightEdge = graph.edges.find((edge) => edge.target === "root.0");
    expect(rightEdge?.sourceHandle).toBe("source-right");
  });

  it("draws branches as curves so sibling lines never stack", () => {
    const graph = buildKnowledgeGraph(knowledgeTree, new Set(["root", "root.0"]), () => undefined);

    expect(graph.edges.every((edge) => edge.type === "bezier")).toBe(true);
    expect(graph.edges.every((edge) => edge.style?.strokeWidth === 1.6)).toBe(true);
  });

  it("keeps a node where the reader dropped it", () => {
    const graph = buildKnowledgeGraph(knowledgeTree, new Set(["root", "root.0"]), () => undefined);
    const laidOut = graph.nodes.find((node) => node.id === "root.0")?.position;
    expect(laidOut).toBeTruthy();

    const moved = buildKnowledgeGraph(knowledgeTree, new Set(["root", "root.0"]), () => undefined, {
      positionOffsets: new Map([["topic-id", { dx: 40, dy: -25 }]]),
    });
    const shifted = moved.nodes.find((node) => node.id === "root.0")?.position;

    expect(shifted).toEqual({ x: (laidOut?.x ?? 0) + 40, y: (laidOut?.y ?? 0) - 25 });
  });
});
