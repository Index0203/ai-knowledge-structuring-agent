import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DocumentStatus, getDocumentStatus, getKnowledgeTree, startKnowledgeTree, startProcessing } from "@/lib/api/documents";
import { uploadDocument } from "@/lib/api/uploads";
import { KnowledgeTree } from "@/features/knowledge-map/types";
import { DocumentWorkspace } from "./DocumentWorkspace";

vi.mock("@/lib/api/documents", () => ({
  startProcessing: vi.fn(),
  getDocumentStatus: vi.fn(),
  startKnowledgeTree: vi.fn(),
  getKnowledgeTree: vi.fn(),
}));

vi.mock("@/lib/api/uploads", () => ({ uploadDocument: vi.fn() }));

// React Flow needs a browser layout engine, so the canvas is stubbed in unit tests.
vi.mock("@/features/knowledge-map/KnowledgeMap", () => ({
  KnowledgeMap: () => <div data-testid="knowledge-map" />,
}));

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
      keywords: [],
      source_section_indexes: [0],
      depth: 1,
      children: [],
    },
  ],
};

function indexedStatus(): DocumentStatus {
  return {
    document_id: "doc-1",
    original_filename: "report.pdf",
    media_type: "application/pdf",
    size_bytes: 1024,
    status: "indexed",
    error_message: null,
    error_code: null,
    page_count: 3,
    paragraph_count: null,
    ocr_page_count: 2,
    chunk_count: 4,
    embedding_model: "deterministic-hashing-256",
    tree_status: "none",
    tree_error: null,
    tree_mode: null,
    created_at: "2026-01-01T00:00:00Z",
    indexed_at: "2026-01-01T00:00:01Z",
    tree_built_at: null,
  };
}

async function uploadAFile(): Promise<void> {
  fireEvent.change(screen.getByLabelText("选择文件"), {
    target: { files: [new File(["%PDF-"], "report.pdf", { type: "application/pdf" })] },
  });
  await screen.findByRole("button", { name: /生成思维导图/ });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("DocumentWorkspace", () => {
  it("offers five colour themes and applies the chosen one to the whole page", () => {
    render(<DocumentWorkspace />);

    expect(screen.getByRole("button", { name: "紫粉" }).getAttribute("aria-pressed")).toBe("true");
    expect(document.querySelector('[data-theme="instagram"]')).toBeTruthy();

    for (const label of ["海盐蓝", "薄荷绿", "紫罗兰", "落日橘"]) {
      expect(screen.getByRole("button", { name: label })).toBeTruthy();
    }

    fireEvent.click(screen.getByRole("button", { name: "薄荷绿" }));

    const wrapper = document.querySelector("[data-theme]") as HTMLElement;
    expect(wrapper.getAttribute("data-theme")).toBe("mint");
    expect(wrapper.style.getPropertyValue("--brand-1")).toBe("#0F766E");
    expect(screen.getByRole("button", { name: "薄荷绿" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("remembers the chosen theme for the next visit", () => {
    render(<DocumentWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: "落日橘" }));

    expect(window.localStorage.getItem("knowledge-agent-theme")).toBe("sunset");
  });

  it("restores the stored theme on mount", () => {
    window.localStorage.setItem("knowledge-agent-theme", "ocean");

    render(<DocumentWorkspace />);

    const wrapper = document.querySelector("[data-theme]") as HTMLElement;
    expect(wrapper.getAttribute("data-theme")).toBe("ocean");
    expect(screen.getByRole("button", { name: "海盐蓝" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("offers both views after an upload and opens the knowledge map with search", async () => {
    vi.mocked(uploadDocument).mockResolvedValue({
      document_id: "doc-1",
      original_filename: "report.pdf",
      media_type: "application/pdf",
      size_bytes: 1024,
      storage_key: "doc-1.pdf",
      uploaded_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(startProcessing).mockResolvedValue({ document_id: "doc-1", status: "indexing" });
    vi.mocked(getDocumentStatus).mockResolvedValue(indexedStatus());
    vi.mocked(startKnowledgeTree).mockResolvedValue({ document_id: "doc-1", status: "building" });
    vi.mocked(getKnowledgeTree).mockResolvedValue({
      document_id: "doc-1",
      status: "ready",
      mode: "structure_fallback",
      error_message: null,
      tree,
    });

    render(<DocumentWorkspace pollIntervalMs={1} />);
    await uploadAFile();
    fireEvent.click(screen.getByRole("button", { name: /生成知识地图/ }));

    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: "知识地图" })).toBeTruthy();
    });
    expect(startProcessing).toHaveBeenCalledWith("doc-1");
    expect(screen.getByTestId("knowledge-map")).toBeTruthy();
    expect(screen.getByLabelText("搜索节点")).toBeTruthy();
    const statusMessages = screen.getAllByRole("status").map((element) => element.textContent ?? "");
    expect(statusMessages.some((text) => text.includes("已通过 OCR 识别"))).toBe(true);
  });

  it("opens the mind map without the search and question panel", async () => {
    vi.mocked(uploadDocument).mockResolvedValue({
      document_id: "doc-2",
      original_filename: "report.pdf",
      media_type: "application/pdf",
      size_bytes: 1024,
      storage_key: "doc-2.pdf",
      uploaded_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(startProcessing).mockResolvedValue({ document_id: "doc-2", status: "indexing" });
    vi.mocked(getDocumentStatus).mockResolvedValue({ ...indexedStatus(), document_id: "doc-2", ocr_page_count: 0 });
    vi.mocked(startKnowledgeTree).mockResolvedValue({ document_id: "doc-2", status: "building" });
    vi.mocked(getKnowledgeTree).mockResolvedValue({
      document_id: "doc-2",
      status: "ready",
      mode: "llm",
      error_message: null,
      tree,
    });

    render(<DocumentWorkspace pollIntervalMs={1} />);
    await uploadAFile();
    fireEvent.click(screen.getByRole("button", { name: /生成思维导图/ }));

    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: "思维导图" })).toBeTruthy();
    });
    expect(screen.queryByLabelText("搜索节点")).toBeNull();
    expect(screen.queryByLabelText("节点问答")).toBeNull();
  });

  it("explains a failed scan in the user's language instead of opening a map", async () => {
    vi.mocked(uploadDocument).mockResolvedValue({
      document_id: "doc-3",
      original_filename: "scan.pdf",
      media_type: "application/pdf",
      size_bytes: 9_658_665,
      storage_key: "doc-3.pdf",
      uploaded_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(startProcessing).mockResolvedValue({ document_id: "doc-3", status: "indexing" });
    vi.mocked(getDocumentStatus).mockResolvedValue({
      ...indexedStatus(),
      document_id: "doc-3",
      status: "failed",
      error_code: "no_text_layer",
      error_message: "The PDF has no extractable text layer: 25 of 25 pages are images.",
      chunk_count: 0,
    });

    render(<DocumentWorkspace pollIntervalMs={1} />);
    await uploadAFile();
    fireEvent.click(screen.getByRole("button", { name: /生成知识地图/ }));

    await waitFor(() => {
      const messages = screen.getAllByRole("status").map((element) => element.textContent ?? "");
      expect(messages.some((text) => text.includes("没有可以提取的文字层"))).toBe(true);
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("reports a tree failure that happens after indexing", async () => {
    vi.mocked(uploadDocument).mockResolvedValue({
      document_id: "doc-4",
      original_filename: "report.pdf",
      media_type: "application/pdf",
      size_bytes: 1024,
      storage_key: "doc-4.pdf",
      uploaded_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(startProcessing).mockResolvedValue({ document_id: "doc-4", status: "indexing" });
    vi.mocked(getDocumentStatus).mockResolvedValue({ ...indexedStatus(), document_id: "doc-4", ocr_page_count: 0 });
    vi.mocked(startKnowledgeTree).mockResolvedValue({ document_id: "doc-4", status: "building" });
    vi.mocked(getKnowledgeTree).mockResolvedValue({
      document_id: "doc-4",
      status: "failed",
      mode: null,
      error_message: "The document contains no extractable text.",
      tree: null,
    });

    render(<DocumentWorkspace pollIntervalMs={1} />);
    await uploadAFile();
    fireEvent.click(screen.getByRole("button", { name: /生成知识地图/ }));

    await waitFor(() => {
      const messages = screen.getAllByRole("status").map((element) => element.textContent ?? "");
      expect(messages.some((text) => text.includes("no extractable text"))).toBe(true);
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
