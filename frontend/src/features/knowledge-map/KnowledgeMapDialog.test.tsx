import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeMapDialog } from "./KnowledgeMapDialog";
import { KnowledgeTree, KnowledgeTreeNode } from "./types";
import { downloadXmindFile } from "./xmind";

const node: KnowledgeTreeNode = {
  id: "chapter-1",
  title: "第二章 数智聚焦",
  summary: "章节导语",
  keywords: ["数智化"],
  source_section_indexes: [0],
  depth: 1,
  children: [],
};

const tree: KnowledgeTree = {
  id: "root",
  title: "Evidence Handbook",
  summary: "Document root",
  keywords: [],
  source_section_indexes: [],
  depth: 0,
  children: [node],
};

const secondNode: KnowledgeTreeNode = {
  id: "chapter-2",
  title: "第三章 程序实现",
  summary: "另一章的导语",
  keywords: [],
  source_section_indexes: [1],
  depth: 1,
  children: [],
};

const moveTree: KnowledgeTree = { ...tree, children: [node, secondNode] };

// React Flow needs a browser layout engine, so the canvas is stubbed here.
vi.mock("./xmind", () => ({ downloadXmindFile: vi.fn() }));

vi.mock("@/features/knowledge-map/KnowledgeMap", () => ({
  KnowledgeMap: ({
    onNodeExpandRequest,
    onSelectNode,
    onToggleFullscreen,
    onAddChildRequest,
    onEditRequest,
    onDeleteRequest,
    onMoveNode,
    onSaveEdit,
  }: {
    onNodeExpandRequest?: (value: KnowledgeTreeNode) => void;
    onSelectNode?: (value: KnowledgeTreeNode) => void;
    onToggleFullscreen?: () => void;
    onAddChildRequest?: (value: KnowledgeTreeNode) => void;
    onEditRequest?: (value: KnowledgeTreeNode) => void;
    onDeleteRequest?: (value: KnowledgeTreeNode) => void;
    onMoveNode?: (value: KnowledgeTreeNode, target: KnowledgeTreeNode) => void;
    onSaveEdit?: (value: KnowledgeTreeNode, patch: { title: string; summary: string }) => void;
  }) => (
    <div data-testid="map">
      <button type="button" onClick={() => onNodeExpandRequest?.(node)}>
        模拟双击节点
      </button>
      <button type="button" onClick={() => onSelectNode?.(node)}>
        模拟点击节点
      </button>
      <button type="button" onClick={() => onToggleFullscreen?.()}>
        模拟全屏切换
      </button>
      <button type="button" onClick={() => onAddChildRequest?.(node)}>
        模拟添加子节点
      </button>
      <button type="button" onClick={() => onEditRequest?.(node)}>
        模拟编辑节点
      </button>
      <button type="button" onClick={() => onDeleteRequest?.(node)}>
        模拟删除节点
      </button>
      <button type="button" onClick={() => onMoveNode?.(secondNode, node)}>
        模拟移动节点
      </button>
      <button
        type="button"
        onClick={() => onSaveEdit?.(node, { title: "改过的标题", summary: "改过的内容" })}
      >
        模拟保存编辑
      </button>
    </div>
  ),
}));

/** jsdom has no Fullscreen API, so the tests provide a minimal stand-in. */
function stubFullscreen(): { requestFullscreen: ReturnType<typeof vi.fn>; exitFullscreen: ReturnType<typeof vi.fn> } {
  let fullscreenElement: Element | null = null;
  const requestFullscreen = vi.fn(function (this: Element) {
    fullscreenElement = this;
    document.dispatchEvent(new Event("fullscreenchange"));
    return Promise.resolve();
  });
  const exitFullscreen = vi.fn(function () {
    fullscreenElement = null;
    document.dispatchEvent(new Event("fullscreenchange"));
    return Promise.resolve();
  });
  Object.defineProperty(document, "fullscreenElement", {
    configurable: true,
    get: () => fullscreenElement,
  });
  Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
    configurable: true,
    value: requestFullscreen,
  });
  Object.defineProperty(document, "exitFullscreen", {
    configurable: true,
    value: exitFullscreen,
  });
  return { requestFullscreen, exitFullscreen };
}

/** jsdom has no PointerEvent either, so dragging needs a MouseEvent-based stand-in. */
function stubPointerEvents(): void {
  class TestPointerEvent extends MouseEvent {
    readonly pointerId = 1;
  }
  Object.defineProperty(window, "PointerEvent", { configurable: true, value: TestPointerEvent });
}

afterEach(() => {
  cleanup();
  Reflect.deleteProperty(document, "fullscreenElement");
  Reflect.deleteProperty(document, "exitFullscreen");
  Reflect.deleteProperty(HTMLElement.prototype, "requestFullscreen");
  Reflect.deleteProperty(window, "PointerEvent");
});

describe("KnowledgeMapDialog", () => {
  it("shows search, details and the assistant in knowledge mode", () => {
    render(<KnowledgeMapDialog tree={tree} mode="knowledge" onClose={() => undefined} />);

    expect(screen.getByRole("dialog", { name: "知识地图" })).toBeTruthy();
    expect(screen.getByLabelText("搜索节点")).toBeTruthy();
    expect(screen.getByTestId("map")).toBeTruthy();
  });

  it("hides search and the assistant in mind-map mode", () => {
    render(<KnowledgeMapDialog tree={tree} mode="mindmap" onClose={() => undefined} />);

    expect(screen.getByRole("dialog", { name: "思维导图" })).toBeTruthy();
    expect(screen.queryByLabelText("搜索节点")).toBeNull();
    expect(screen.queryByLabelText("节点 AI 助手")).toBeNull();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<KnowledgeMapDialog tree={tree} mode="mindmap" onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });

  it("keeps the map open when Escape closes the enlarged node view", () => {
    const onClose = vi.fn();
    render(<KnowledgeMapDialog tree={tree} mode="knowledge" onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: "模拟双击节点" }));
    expect(screen.getByRole("dialog", { name: "节点放大视图" })).toBeTruthy();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "节点放大视图" })).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("adds a child node with Enter and keeps it in the tree", () => {
    const onTreeChange = vi.fn();
    render(
      <KnowledgeMapDialog tree={tree} mode="mindmap" onClose={() => undefined} onTreeChange={onTreeChange} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "模拟点击节点" }));
    fireEvent.keyDown(window, { key: "Enter" });

    expect(onTreeChange).toHaveBeenCalledTimes(1);
    const updated = onTreeChange.mock.calls[0][0] as KnowledgeTree;
    const parent = updated.children[0];
    expect(parent.children).toHaveLength(1);
    expect(parent.children[0].title).toBe("新节点");
    expect(parent.children[0].local).toBe(true);
  });

  it("deletes the selected node with Delete", () => {
    const onTreeChange = vi.fn();
    render(
      <KnowledgeMapDialog tree={tree} mode="mindmap" onClose={() => undefined} onTreeChange={onTreeChange} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "模拟点击节点" }));
    fireEvent.keyDown(window, { key: "Delete" });

    const updated = onTreeChange.mock.calls[0][0] as KnowledgeTree;
    expect(updated.children).toHaveLength(0);
  });

  it("ignores the map shortcuts while the reader is typing in a field", () => {
    const onTreeChange = vi.fn();
    render(
      <KnowledgeMapDialog
        tree={tree}
        mode="knowledge"
        onClose={() => undefined}
        onTreeChange={onTreeChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "模拟点击节点" }));
    fireEvent.keyDown(screen.getByLabelText("搜索节点"), { key: "Enter" });
    fireEvent.keyDown(screen.getByLabelText("输入问题"), { key: "Delete" });

    expect(onTreeChange).not.toHaveBeenCalled();
  });

  it("saves the content edited on a node", () => {
    const onTreeChange = vi.fn();
    render(
      <KnowledgeMapDialog tree={tree} mode="mindmap" onClose={() => undefined} onTreeChange={onTreeChange} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "模拟编辑节点" }));
    fireEvent.click(screen.getByRole("button", { name: "模拟保存编辑" }));

    const updated = onTreeChange.mock.calls[0][0] as KnowledgeTree;
    expect(updated.children[0].title).toBe("改过的标题");
    expect(updated.children[0].summary).toBe("改过的内容");
  });

  it("downloads the current map as an xmind file", () => {
    render(<KnowledgeMapDialog tree={tree} mode="mindmap" onClose={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: "下载 XMind" }));

    expect(downloadXmindFile).toHaveBeenCalledWith(tree);
  });

  it("exports the edited map, not the freshly generated one", () => {
    render(<KnowledgeMapDialog tree={tree} mode="mindmap" onClose={() => undefined} />);

    // Add a child, rename the original node, then download.
    fireEvent.click(screen.getByRole("button", { name: "模拟点击节点" }));
    fireEvent.keyDown(window, { key: "Enter" });
    fireEvent.click(screen.getByRole("button", { name: "模拟编辑节点" }));
    fireEvent.click(screen.getByRole("button", { name: "模拟保存编辑" }));
    fireEvent.click(screen.getByRole("button", { name: "下载 XMind" }));

    const exported = vi.mocked(downloadXmindFile).mock.calls.at(-1)?.[0] as KnowledgeTree;
    expect(exported.children[0].title).toBe("改过的标题");
    expect(exported.children[0].summary).toBe("改过的内容");
    expect(exported.children[0].children.map((child) => child.title)).toEqual(["新节点"]);
  });

  it("moves a dragged node under the node it was dropped on", () => {
    const onTreeChange = vi.fn();
    render(
      <KnowledgeMapDialog
        tree={moveTree}
        mode="mindmap"
        onClose={() => undefined}
        onTreeChange={onTreeChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "模拟移动节点" }));

    const updated = onTreeChange.mock.calls[0][0] as KnowledgeTree;
    expect(updated.children.map((child) => child.id)).toEqual(["chapter-1"]);
    expect(updated.children[0].children.map((child) => child.id)).toEqual(["chapter-2"]);
  });

  it("undoes the last edit with Ctrl+Z", () => {
    const onTreeChange = vi.fn();
    render(
      <KnowledgeMapDialog
        tree={moveTree}
        mode="mindmap"
        onClose={() => undefined}
        onTreeChange={onTreeChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "模拟移动节点" }));
    const moved = onTreeChange.mock.calls.at(-1)?.[0] as KnowledgeTree;
    expect(moved.children.map((child) => child.id)).toEqual(["chapter-1"]);

    fireEvent.keyDown(window, { key: "z", ctrlKey: true });

    // The node returns to its previous level, with an empty history step back.
    const restored = onTreeChange.mock.calls.at(-1)?.[0] as KnowledgeTree;
    expect(restored.children.map((child) => child.id)).toEqual(["chapter-1", "chapter-2"]);
    expect(restored.children[0].children).toEqual([]);
  });

  it("enables undo only after an edit and can redo it", () => {
    const onTreeChange = vi.fn();
    render(
      <KnowledgeMapDialog tree={tree} mode="mindmap" onClose={() => undefined} onTreeChange={onTreeChange} />,
    );

    expect(screen.getByRole("button", { name: "撤销" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "重做" }).hasAttribute("disabled")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "模拟删除节点" }));
    expect(screen.getByRole("button", { name: "撤销" }).hasAttribute("disabled")).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "撤销" }));
    const restored = onTreeChange.mock.calls.at(-1)?.[0] as KnowledgeTree;
    expect(restored.children.map((child) => child.id)).toEqual(["chapter-1"]);
    expect(screen.getByRole("button", { name: "重做" }).hasAttribute("disabled")).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "重做" }));
    const redone = onTreeChange.mock.calls.at(-1)?.[0] as KnowledgeTree;
    expect(redone.children).toHaveLength(0);
  });

  it("floats the assistant and expands it when a node is clicked in fullscreen", async () => {
    const { requestFullscreen, exitFullscreen } = stubFullscreen();
    render(<KnowledgeMapDialog tree={tree} mode="knowledge" onClose={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: "模拟全屏切换" }));
    expect(requestFullscreen).toHaveBeenCalledTimes(1);

    // The assistant floats beside the map but stays collapsed until a node is chosen.
    expect(await screen.findByRole("button", { name: "节点 AI 助手" })).toBeTruthy();
    expect(screen.queryByLabelText("节点 AI 助手面板")).toBeNull();
    expect(screen.queryByLabelText("节点详情")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "模拟点击节点" }));

    expect(await screen.findByLabelText("节点 AI 助手面板")).toBeTruthy();
    expect(screen.getByLabelText("节点详情")).toBeTruthy();
    expect(screen.getByText("解释这个节点")).toBeTruthy();

    // Leaving fullscreen restores the docked sidebar.
    fireEvent.click(screen.getByRole("button", { name: "模拟全屏切换" }));
    expect(exitFullscreen).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText("节点 AI 助手面板")).toBeNull();
    expect(screen.getByText("解释这个节点")).toBeTruthy();
  });

  it("keeps the dialog open when Escape leaves fullscreen", async () => {
    stubFullscreen();
    const onClose = vi.fn();
    render(<KnowledgeMapDialog tree={tree} mode="knowledge" onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: "模拟全屏切换" }));
    await screen.findByRole("button", { name: "节点 AI 助手" });

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).not.toHaveBeenCalled();
  });

  it("lets the reader drag the floating assistant and keeps it there", async () => {
    stubPointerEvents();
    stubFullscreen();
    render(<KnowledgeMapDialog tree={tree} mode="knowledge" onClose={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: "模拟全屏切换" }));
    fireEvent.click(screen.getByRole("button", { name: "模拟点击节点" }));

    const panel = await screen.findByLabelText("节点 AI 助手面板");
    const dragHandle = screen.getByLabelText("拖动移动面板");

    fireEvent.pointerDown(dragHandle, { button: 0, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(dragHandle, { clientX: 220, clientY: 160 });
    fireEvent.pointerUp(dragHandle, { clientX: 220, clientY: 160 });

    // The panel leaves its docked corner and stays where it was dropped.
    expect(panel.className).toContain("fixed");
    expect(panel.style.left).toBe("120px");
    expect(panel.style.top).toBe("60px");

    fireEvent.pointerMove(dragHandle, { clientX: 400, clientY: 300 });
    expect(panel.style.left).toBe("120px");
    expect(panel.style.top).toBe("60px");
  });

  it("lets the reader park the collapsed assistant pill without opening it", async () => {
    stubPointerEvents();
    stubFullscreen();
    render(<KnowledgeMapDialog tree={tree} mode="knowledge" onClose={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: "模拟全屏切换" }));

    const pill = await screen.findByRole("button", { name: "节点 AI 助手" });
    fireEvent.pointerDown(pill, { button: 0, clientX: 200, clientY: 120 });
    fireEvent.pointerMove(pill, { clientX: 260, clientY: 180 });
    fireEvent.pointerUp(pill, { clientX: 260, clientY: 180 });

    expect(pill.style.left).toBe("60px");
    expect(pill.style.top).toBe("60px");

    // The browser fires a click at the end of a drag; it must not open the panel.
    fireEvent.click(pill);
    expect(screen.queryByLabelText("节点 AI 助手面板")).toBeNull();

    // A plain click still opens the panel, parked where the pill was left.
    fireEvent.click(pill);
    const panel = await screen.findByLabelText("节点 AI 助手面板");
    expect(panel.style.left).toBe("60px");
    expect(panel.style.top).toBe("60px");
  });

  it("fills the window when the browser refuses fullscreen", async () => {
    const requestFullscreen = vi.fn(() => Promise.reject(new Error("fullscreen blocked")));
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: requestFullscreen,
    });
    render(<KnowledgeMapDialog tree={tree} mode="knowledge" onClose={() => undefined} />);

    fireEvent.click(screen.getByRole("button", { name: "模拟全屏切换" }));

    expect(await screen.findByRole("button", { name: "节点 AI 助手" })).toBeTruthy();
  });
});
