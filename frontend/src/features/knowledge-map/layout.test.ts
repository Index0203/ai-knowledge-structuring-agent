import { describe, expect, it } from "vitest";

import { LayoutInput, layoutTree } from "./layout";

const tree: LayoutInput = {
  id: "root",
  children: [
    {
      id: "a",
      children: [
        { id: "a1", children: [] },
        { id: "a2", children: [] },
      ],
    },
    { id: "b", children: [] },
  ],
};

const options = { horizontalGap: 100, verticalGap: 10, nodeHeight: 20 };

describe("layoutTree", () => {
  it("grows a balanced map to both sides of the root", () => {
    const offsets = layoutTree(tree, options);

    expect(offsets.get("root")).toMatchObject({ x: 0, y: 0, side: "root" });
    expect(offsets.get("a")).toMatchObject({ x: 100, side: "right" });
    expect(offsets.get("a1")).toMatchObject({ x: 200, side: "right" });
    expect(offsets.get("b")).toMatchObject({ x: -100, side: "left" });
  });

  it("balances the two sides by the size of each subtree", () => {
    const wide: LayoutInput = {
      id: "root",
      children: [
        { id: "small-1", children: [] },
        { id: "small-2", children: [] },
        {
          id: "big",
          children: [
            { id: "big-1", children: [] },
            { id: "big-2", children: [] },
            { id: "big-3", children: [] },
          ],
        },
      ],
    };

    const offsets = layoutTree(wide, options);

    expect(offsets.get("small-1")?.side).toBe("right");
    expect(offsets.get("small-2")?.side).toBe("right");
    expect(offsets.get("big")?.side).toBe("left");
    expect(offsets.get("big-1")?.x).toBe(-200);
  });

  it("centres each side on the root", () => {
    const offsets = layoutTree(tree, options);

    expect(offsets.get("a1")?.y).toBe(-15);
    expect(offsets.get("a2")?.y).toBe(15);
    expect(offsets.get("a")?.y).toBe(0);
    expect(offsets.get("b")?.y).toBe(0);
  });

  it("keeps siblings on one side separated so branches never overlap", () => {
    const offsets = layoutTree(tree, options);
    const siblingYs = ["a1", "a2"].map((id) => offsets.get(id)?.y ?? 0);

    expect(siblingYs).toEqual([...siblingYs].sort((left, right) => left - right));
    expect(new Set(siblingYs).size).toBe(siblingYs.length);
    // The left branch is centred on the root, so the two sides cannot collide.
    expect(offsets.get("b")?.y).toBe(0);
  });

  it("can still lay the whole map out to the right", () => {
    const offsets = layoutTree(tree, { ...options, balanced: false });

    expect(offsets.get("root")?.side).toBe("root");
    expect(offsets.get("a")).toMatchObject({ x: 100, side: "right" });
    expect(offsets.get("b")).toMatchObject({ x: 100, side: "right" });
  });

  it("keeps a single child on the right so short maps stay readable", () => {
    const offsets = layoutTree(
      { id: "root", children: [{ id: "only", children: [] }] },
      options,
    );

    expect(offsets.get("only")).toMatchObject({ x: 100, side: "right" });
  });
});
