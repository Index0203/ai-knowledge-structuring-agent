import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QuestionAnswer, getQuestion, submitQuestion } from "@/lib/api/questions";
import { KnowledgeNodeQa } from "./KnowledgeNodeQa";
import { KnowledgeTreeNode } from "./types";

vi.mock("@/lib/api/questions", () => ({
  submitQuestion: vi.fn(),
  getQuestion: vi.fn(),
}));

const node: KnowledgeTreeNode = {
  id: "node-1",
  title: "Citations",
  summary: "Citation obligations",
  keywords: [],
  source_section_indexes: [1],
  depth: 1,
  children: [],
};

const citation = {
  chunk_id: "chunk-1",
  quote: "Every answer must cite the content block it came from.",
  section_title: "Citations",
  chunk_index: 2,
  page_number: 3,
  paragraph_index: null as number | null,
  relevance: 0.72,
};

function answerWith(overrides: Partial<QuestionAnswer>): QuestionAnswer {
  return {
    question_id: "question-1",
    document_id: "document-1",
    node_id: "node-1",
    intent: "ask",
    question: "What must every answer cite?",
    status: "answered",
    answer: "Every answer must cite the content block it came from.",
    answer_mode: "llm",
    model: "test-model",
    prompt_version: "node-assistant-v1",
    confidence: 0.8,
    citations: [],
    quiz_items: [],
    error_message: null,
    latency_ms: 120,
    created_at: "2026-01-01T00:00:00Z",
    answered_at: "2026-01-01T00:00:01Z",
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("KnowledgeNodeQa (Node AI Assistant)", () => {
  it("offers the four assistant capabilities", () => {
    render(<KnowledgeNodeQa node={node} pollIntervalMs={1} />);

    for (const label of ["解释这个节点", "举例说明", "深入学习", "生成测试问题"]) {
      expect(screen.getByRole("button", { name: new RegExp(label) })).toBeTruthy();
    }
    expect(screen.getByLabelText("输入问题")).toBeTruthy();
  });

  it("runs the explain capability and shows the grounded answer with citations", async () => {
    vi.mocked(submitQuestion).mockResolvedValue({
      question_id: "question-1",
      node_id: "node-1",
      intent: "explain",
      status: "queued",
      created_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(getQuestion).mockResolvedValue(
      answerWith({ intent: "explain", answer: "该节点说明答案必须引用来源。", citations: [citation] }),
    );
    render(<KnowledgeNodeQa node={node} pollIntervalMs={1} />);

    fireEvent.click(screen.getByRole("button", { name: /解释这个节点/ }));

    await waitFor(() => {
      expect(screen.getByText("该节点说明答案必须引用来源。")).toBeTruthy();
    });
    expect(submitQuestion).toHaveBeenCalledWith("node-1", "", "explain");
    expect(screen.getByRole("heading", { name: "引用来源", level: 4 })).toBeTruthy();
    expect(screen.getByText(/第 3 页/)).toBeTruthy();
  });

  it("renders generated quiz questions with their own citations", async () => {
    vi.mocked(submitQuestion).mockResolvedValue({
      question_id: "question-2",
      node_id: "node-1",
      intent: "quiz",
      status: "queued",
      created_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(getQuestion).mockResolvedValue(
      answerWith({
        intent: "quiz",
        answer: "共 1 道自测题。",
        citations: [citation],
        quiz_items: [
          { question: "答案必须做什么？", answer: "必须引用它来自的内容块。", citations: [citation] },
        ],
      }),
    );
    render(<KnowledgeNodeQa node={node} pollIntervalMs={1} />);

    fireEvent.click(screen.getByRole("button", { name: /生成测试问题/ }));

    await waitFor(() => {
      expect(screen.getByText(/1\. 答案必须做什么？/)).toBeTruthy();
    });
    expect(screen.getByText("必须引用它来自的内容块。")).toBeTruthy();
    expect(screen.getByText(/出处：Citations/)).toBeTruthy();
  });

  it("sends a free-form question when the user types one", async () => {
    vi.mocked(submitQuestion).mockResolvedValue({
      question_id: "question-3",
      node_id: "node-1",
      intent: "ask",
      status: "queued",
      created_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(getQuestion).mockResolvedValue(answerWith({ citations: [citation] }));
    render(<KnowledgeNodeQa node={node} pollIntervalMs={1} />);

    fireEvent.change(screen.getByLabelText("输入问题"), { target: { value: "What must every answer cite?" } });
    fireEvent.click(screen.getByRole("button", { name: "提问" }));

    await waitFor(() => {
      expect(submitQuestion).toHaveBeenCalledWith("node-1", "What must every answer cite?", "ask");
    });
  });

  it("renders a refusal without citations when evidence is insufficient", async () => {
    vi.mocked(submitQuestion).mockResolvedValue({
      question_id: "question-1",
      node_id: "node-1",
      intent: "explain",
      status: "queued",
      created_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(getQuestion).mockResolvedValue(
      answerWith({
        intent: "explain",
        status: "insufficient_evidence",
        answer: null,
        answer_mode: null,
        confidence: null,
        error_message: "No content block in this document matched the request closely enough.",
      }),
    );
    render(<KnowledgeNodeQa node={node} pollIntervalMs={1} />);

    fireEvent.click(screen.getByRole("button", { name: /解释这个节点/ }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("证据不足");
    });
    expect(screen.queryByRole("heading", { name: "引用来源", level: 4 })).toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("labels an extractive fallback answer honestly", async () => {
    vi.mocked(submitQuestion).mockResolvedValue({
      question_id: "question-1",
      node_id: "node-1",
      intent: "ask",
      status: "queued",
      created_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(getQuestion).mockResolvedValue(
      answerWith({
        answer_mode: "extractive_fallback",
        model: null,
        citations: [{ ...citation, page_number: null, paragraph_index: 4, relevance: 0.4 }],
      }),
    );
    render(<KnowledgeNodeQa node={node} pollIntervalMs={1} />);

    fireEvent.change(screen.getByLabelText("输入问题"), { target: { value: "What must every answer cite?" } });
    fireEvent.click(screen.getByRole("button", { name: "提问" }));

    await waitFor(() => {
      expect(screen.getByText(/未配置大模型/)).toBeTruthy();
    });
    expect(screen.getByText(/第 5 段/)).toBeTruthy();
  });
});
