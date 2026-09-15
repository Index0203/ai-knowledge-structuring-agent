import { describe, expect, it } from "vitest";

import { filterKnowledgeNodes } from "./search";
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

describe("filterKnowledgeNodes", () => {
  it("returns nothing for an empty query", () => {
    expect(filterKnowledgeNodes(tree, "   ")).toEqual([]);
  });

  it("matches titles, summaries and keywords case-insensitively", () => {
    expect(filterKnowledgeNodes(tree, "数智").map((node) => node.id)).toEqual(["chapter-1"]);
    expect(filterKnowledgeNodes(tree, "知识库").map((node) => node.id)).toEqual(["section-1-1"]);
    expect(filterKnowledgeNodes(tree, "EVIDENCE").map((node) => node.id)).toEqual(["root"]);
  });

  it("reports no match for unrelated queries", () => {
    expect(filterKnowledgeNodes(tree, "财务报表")).toEqual([]);
  });
});
