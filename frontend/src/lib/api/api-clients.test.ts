import { afterEach, describe, expect, it, vi } from "vitest";

import { getDocumentStatus, getKnowledgeTree, startProcessing } from "./documents";
import { getQuestion, submitQuestion } from "./questions";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

const fetchMock = vi.fn();

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function stubFetch(): typeof fetchMock {
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("documents API client", () => {
  it("parses a document status payload", async () => {
    stubFetch().mockResolvedValue(
      jsonResponse({
        document_id: "doc-1",
        status: "indexed",
        error_code: "no_text_layer",
        chunk_count: 3,
        ocr_page_count: 2,
      }),
    );

    const status = await getDocumentStatus("doc-1");

    expect(status.status).toBe("indexed");
    expect(status.error_code).toBe("no_text_layer");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/v1/documents/doc-1"));
  });

  it("surfaces the server error message", async () => {
    stubFetch().mockResolvedValue(jsonResponse({ detail: "Document doc-9 does not exist." }, 404));

    await expect(getDocumentStatus("doc-9")).rejects.toThrow("Document doc-9 does not exist.");
  });

  it("falls back to a generic message when the body is not JSON", async () => {
    stubFetch().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not json");
      },
    } as unknown as Response);

    await expect(getKnowledgeTree("doc-1")).rejects.toThrow("无法读取知识结构。");
  });

  it("posts to the processing endpoint", async () => {
    stubFetch().mockResolvedValue(jsonResponse({ document_id: "doc-1", status: "indexing" }, 202));

    await startProcessing("doc-1");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/documents/doc-1/processing"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("questions API client", () => {
  it("sends the intent with the question", async () => {
    stubFetch().mockResolvedValue(
      jsonResponse({ question_id: "q1", node_id: "n1", intent: "quiz", status: "queued" }, 202),
    );

    const submitted = await submitQuestion("n1", "", "quiz");

    expect(submitted.intent).toBe("quiz");
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(init.body))).toEqual({ question: "", intent: "quiz" });
  });

  it("returns the answer payload with citations and quiz items", async () => {
    stubFetch().mockResolvedValue(
      jsonResponse({
        question_id: "q1",
        intent: "quiz",
        status: "answered",
        answer: "共 1 题",
        citations: [],
        quiz_items: [{ question: "q", answer: "a", citations: [] }],
      }),
    );

    const answer = await getQuestion("q1");

    expect(answer.quiz_items).toHaveLength(1);
    expect(answer.intent).toBe("quiz");
  });

  it("throws the server message when submitting fails", async () => {
    stubFetch().mockResolvedValue(jsonResponse({ detail: "Knowledge node n1 does not exist." }, 404));

    await expect(submitQuestion("n1", "这是什么？")).rejects.toThrow("Knowledge node n1 does not exist.");
  });
});
