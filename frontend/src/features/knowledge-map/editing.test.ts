import { describe, expect, it } from "vitest";

import {
  addChildNode,
  collectSubtreeIds,
  deleteNode,
  findNode,
  findParentId,
  isDescendantOf,
  moveNode,
  updateNodeContent,
} from "./editing";
import { KnowledgeTree } from "./types";

function makeTree(): KnowledgeTree {
  return {
    id: "root",
    title: "Root",
    summary: "",
    keywords: [],
    source_section_indexes: [],
    depth: 0,
    children: [
      {
        id: "child-1",
        title: "Child",
        summary: "内容",
        keywords: [],
        source_section_indexes: [],
        depth: 1,
        children: [
          {
            id: "grandchild-1",
            title: "Grand",
            summary: "",
            keywords: [],
            source_section_indexes: [],
            depth: 2,
            children: [],
          },
        ],
      },
      {
        id: "child-2",
        title: "Second",
        summary: "",
        keywords: [],
        source_section_indexes: [],
        depth: 1,
        children: [],
      },
    ],
  };
}

describe("knowledge map editing", () => {
  it("adds a local child under the chosen node", () => {
    const result = addChildNode(makeTree(), "child-1");
    if (!result) throw new Error("expected a new child node");

    const created = findNode(result.tree, result.nodeId);
    expect(created?.title).toBe("新节点");
    expect(created?.depth).toBe(2);
    expect(created?.local).toBe(true);
    expect(findNode(result.tree, "child-1")?.children).toHaveLength(2);
  });

  it("updates node content and falls back to the default title", () => {
    const updated = updateNodeContent(makeTree(), "child-1", { title: " 改过的 ", summary: "新内容" });
    expect(findNode(updated, "child-1")?.title).toBe("改过的");
    expect(findNode(updated, "child-1")?.summary).toBe("新内容");

    const blank = updateNodeContent(makeTree(), "child-1", { title: "   ", summary: "" });
    expect(findNode(blank, "child-1")?.title).toBe("新节点");
  });

  it("removes a node together with its subtree and keeps the root", () => {
    const updated = deleteNode(makeTree(), "child-1");
    expect(updated?.children.map((child) => child.id)).toEqual(["child-2"]);
    expect(findNode(updated ?? makeTree(), "grandchild-1")).toBeNull();
    expect(deleteNode(makeTree(), "root")).toBeNull();
  });

  it("finds a node and its parent", () => {
    expect(findNode(makeTree(), "grandchild-1")?.title).toBe("Grand");
    expect(findNode(makeTree(), "missing")).toBeNull();
    expect(findParentId(makeTree(), "grandchild-1")).toBe("child-1");
    expect(findParentId(makeTree(), "child-2")).toBe("root");
    expect(findParentId(makeTree(), "missing")).toBeNull();
  });

  it("moves a node with its subtree under another node", () => {
    const moved = moveNode(makeTree(), "child-1", "child-2");
    if (!moved) throw new Error("expected the move to succeed");

    expect(moved.children.map((child) => child.id)).toEqual(["child-2"]);
    expect(findNode(moved, "child-2")?.children.map((child) => child.id)).toEqual(["child-1"]);
    expect(findNode(moved, "child-1")?.depth).toBe(2);
    expect(findNode(moved, "grandchild-1")?.depth).toBe(3);
  });

  it("refuses moves that would break the tree", () => {
    expect(moveNode(makeTree(), "root", "child-1")).toBeNull();
    expect(moveNode(makeTree(), "child-1", "child-1")).toBeNull();
    // Dropping a parent on its own descendant would create a cycle.
    expect(moveNode(makeTree(), "child-1", "grandchild-1")).toBeNull();
    expect(moveNode(makeTree(), "missing", "child-1")).toBeNull();
  });

  it("reports descendants so the map can refuse those drops", () => {
    expect(isDescendantOf(makeTree(), "child-1", "grandchild-1")).toBe(true);
    expect(isDescendantOf(makeTree(), "child-2", "grandchild-1")).toBe(false);
  });

  it("lists a node with its whole subtree so a branch can move as one block", () => {
    expect(collectSubtreeIds(makeTree().children[0])).toEqual(["child-1", "grandchild-1"]);
    expect(collectSubtreeIds(makeTree().children[1])).toEqual(["child-2"]);
  });
});
