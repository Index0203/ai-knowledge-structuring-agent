import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NodeSearch } from "./NodeSearch";
import { KnowledgeTree } from "./types";

const tree: KnowledgeTree = {
  id: "root",
  title: "Evidence Handbook",
  summary: "Document root",
  keywords: [],
  source_section_indexes: [],
  depth: 0,
  children: [
    {
      id: "chapter-1",
      title: "第二章 数智聚焦",
      summary: "章节导语",
      keywords: ["数智化"],
      source_section_indexes: [0],
      depth: 1,
      children: [
        {
          id: "section-1-1",
          title: "一、数字化知识库构建",
          summary: "统一数据标准并打通链路。",
          keywords: ["知识库"],
          source_section_indexes: [1],
          depth: 2,
          children: [],
        },
      ],
    },
  ],
};

afterEach(cleanup);

describe("NodeSearch", () => {
  it("shows no list until the user types", () => {
    render(<NodeSearch tree={tree} onSelectNode={() => undefined} />);

    expect(screen.queryByRole("list")).toBeNull();
  });

  it("filters nodes and reports matches", () => {
    render(<NodeSearch tree={tree} onSelectNode={() => undefined} />);

    fireEvent.change(screen.getByLabelText("搜索节点"), { target: { value: "知识库" } });

    expect(screen.getByText("一、数字化知识库构建")).toBeTruthy();
    expect(screen.queryByText("第二章 数智聚焦")).toBeNull();
  });

  it("reports an empty result set", () => {
    render(<NodeSearch tree={tree} onSelectNode={() => undefined} />);

    fireEvent.change(screen.getByLabelText("搜索节点"), { target: { value: "财务报表" } });

    expect(screen.getByText("没有匹配的节点")).toBeTruthy();
  });

  it("hands the chosen node back and clears the query", () => {
    const onSelectNode = vi.fn();
    render(<NodeSearch tree={tree} onSelectNode={onSelectNode} />);

    fireEvent.change(screen.getByLabelText("搜索节点"), { target: { value: "数智" } });
    fireEvent.click(screen.getByText("第二章 数智聚焦"));

    expect(onSelectNode).toHaveBeenCalledWith(expect.objectContaining({ id: "chapter-1" }));
    expect((screen.getByLabelText("搜索节点") as HTMLInputElement).value).toBe("");
    expect(screen.queryByRole("list")).toBeNull();
  });
});
