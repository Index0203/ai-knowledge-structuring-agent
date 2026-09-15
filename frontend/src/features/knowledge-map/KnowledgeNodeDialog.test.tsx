import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeNodeDialog } from "./KnowledgeNodeDialog";
import { KnowledgeTreeNode } from "./types";

const longSummary =
  "随着优质中小企业梯度培育体系深化，专精特新“小巨人”企业创新能力加速跃升，形成专于一域、精于细节、特于优势、新于内核的核心竞争力，成为产业升级与技术突破的关键力量。";

const node: KnowledgeTreeNode = {
  id: "node-1",
  title: "一、专精特新概念及内涵",
  summary: longSummary,
  keywords: ["专精特新", "核心竞争力"],
  source_section_indexes: [3, 4],
  depth: 2,
  children: [],
};

afterEach(cleanup);

describe("KnowledgeNodeDialog", () => {
  it("shows the whole node content that the map card truncates", () => {
    render(<KnowledgeNodeDialog node={node} mode="mindmap" onClose={() => undefined} />);

    expect(screen.getByRole("dialog", { name: "节点放大视图" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: node.title })).toBeTruthy();
    expect(screen.getByText(longSummary)).toBeTruthy();
    expect(screen.getByText("专精特新")).toBeTruthy();
    expect(screen.getByText(/第 4 节/)).toBeTruthy();
  });

  it("offers the question panel only in knowledge map mode", () => {
    const view = render(<KnowledgeNodeDialog node={node} mode="knowledge" onClose={() => undefined} />);
    expect(screen.getByLabelText("输入问题")).toBeTruthy();
    view.unmount();

    render(<KnowledgeNodeDialog node={node} mode="mindmap" onClose={() => undefined} />);
    expect(screen.queryByLabelText("输入问题")).toBeNull();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<KnowledgeNodeDialog node={node} mode="mindmap" onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });
});
