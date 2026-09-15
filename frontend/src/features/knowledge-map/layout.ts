export type LayoutInput = {
  id: string;
  children: LayoutInput[];
};

export type BranchSide = "root" | "left" | "right";

export type NodeOffset = {
  x: number;
  y: number;
  side: BranchSide;
};

export type LayoutOptions = {
  horizontalGap?: number;
  verticalGap?: number;
  nodeHeight?: number;
  /** Balanced maps grow left and right of the root, like a classic mind map. */
  balanced?: boolean;
};

export const DEFAULT_LAYOUT_OPTIONS: Required<LayoutOptions> = {
  horizontalGap: 320,
  verticalGap: 70,
  nodeHeight: 120,
  balanced: true,
};

type Point = { x: number; y: number };

/**
 * Mind-map layout: the root sits in the middle, branches grow to both sides and
 * every parent is centred on the span of its children (classic tidy tree, applied
 * once per side and mirrored for the left one).
 */
export function layoutTree(root: LayoutInput, options: LayoutOptions = {}): Map<string, NodeOffset> {
  const resolved = { ...DEFAULT_LAYOUT_OPTIONS, ...options };
  if (resolved.balanced && root.children.length > 1) {
    return layoutBalancedTree(root, resolved);
  }
  const offsets = tidyLayout(root, resolved);
  return toSidedOffsets(offsets, "right", root.id);
}

function layoutBalancedTree(
  root: LayoutInput,
  options: Required<LayoutOptions>,
): Map<string, NodeOffset> {
  const [rightChildren, leftChildren] = splitChildrenForBalance(root.children);
  const right = tidyLayout({ id: root.id, children: rightChildren }, options);
  const leftRootId = `${root.id}__left`;
  const left = tidyLayout({ id: leftRootId, children: leftChildren }, options);

  const offsets = toSidedOffsets(right, "right", root.id);
  const rightRootY = right.get(root.id)?.y ?? 0;
  for (const [id, offset] of offsets) {
    offset.y -= rightRootY;
  }

  const leftRootY = left.get(leftRootId)?.y ?? 0;
  for (const [id, offset] of left) {
    if (id === leftRootId) continue;
    offsets.set(id, { x: -offset.x, y: offset.y - leftRootY, side: "left" });
  }
  return offsets;
}

/** Keep the document order, but split it so both sides carry a similar amount. */
function splitChildrenForBalance(children: LayoutInput[]): [LayoutInput[], LayoutInput[]] {
  const weights = children.map(countLeaves);
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  let bestIndex = 1;
  let bestDifference = Number.POSITIVE_INFINITY;
  let carried = 0;

  for (let index = 1; index < children.length; index += 1) {
    carried += weights[index - 1];
    const difference = Math.abs(total - 2 * carried);
    if (difference < bestDifference) {
      bestDifference = difference;
      bestIndex = index;
    }
  }
  return [children.slice(0, bestIndex), children.slice(bestIndex)];
}

function countLeaves(node: LayoutInput): number {
  if (node.children.length === 0) return 1;
  return node.children.reduce((total, child) => total + countLeaves(child), 0);
}

function tidyLayout(root: LayoutInput, options: Required<LayoutOptions>): Map<string, Point> {
  const { horizontalGap, verticalGap, nodeHeight } = options;
  const unit = nodeHeight + verticalGap;
  const offsets = new Map<string, Point>();
  let cursor = 0;

  function place(node: LayoutInput, depth: number): number {
    const x = depth * horizontalGap;
    if (node.children.length === 0) {
      const y = cursor;
      cursor += unit;
      offsets.set(node.id, { x, y });
      return y;
    }
    const childCenters = node.children.map((child) => place(child, depth + 1));
    const y = (childCenters[0] + childCenters[childCenters.length - 1]) / 2;
    offsets.set(node.id, { x, y });
    return y;
  }

  place(root, 0);
  return offsets;
}

function toSidedOffsets(
  points: Map<string, Point>,
  side: BranchSide,
  rootId: string,
): Map<string, NodeOffset> {
  const offsets = new Map<string, NodeOffset>();
  points.forEach((point, id) => {
    offsets.set(id, { x: point.x, y: point.y, side: id === rootId ? "root" : side });
  });
  return offsets;
}
