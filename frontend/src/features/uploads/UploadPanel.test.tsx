import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { uploadDocument } from "@/lib/api/uploads";
import { UploadPanel } from "./UploadPanel";

vi.mock("@/lib/api/uploads", () => ({ uploadDocument: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UploadPanel", () => {
  it("shows a success status after a supported document uploads", async () => {
    vi.mocked(uploadDocument).mockResolvedValue({
      document_id: "id",
      original_filename: "report.pdf",
      media_type: "application/pdf",
      size_bytes: 12,
      storage_key: "id.pdf",
      uploaded_at: "2026-01-01T00:00:00Z",
    });
    render(<UploadPanel />);
    fireEvent.change(screen.getByLabelText("选择文件"), {
      target: { files: [new File(["%PDF-"], "report.pdf", { type: "application/pdf" })] },
    });

    await waitFor(() => {
      expect(screen.getByRole("status").textContent).toContain("文件已上传并完成类型验证");
    });
  });

  it("notifies the workspace after a successful upload", async () => {
    const onUploaded = vi.fn();
    vi.mocked(uploadDocument).mockResolvedValue({
      document_id: "doc-1",
      original_filename: "report.pdf",
      media_type: "application/pdf",
      size_bytes: 12,
      storage_key: "doc-1.pdf",
      uploaded_at: "2026-01-01T00:00:00Z",
    });
    render(<UploadPanel onUploaded={onUploaded} />);
    fireEvent.change(screen.getByLabelText("选择文件"), {
      target: { files: [new File(["%PDF-"], "report.pdf", { type: "application/pdf" })] },
    });

    await waitFor(() => {
      expect(onUploaded).toHaveBeenCalledWith(expect.objectContaining({ document_id: "doc-1" }));
    });
  });

  it("rejects an unsupported file before sending it", () => {
    render(<UploadPanel />);
    fireEvent.change(screen.getByLabelText("选择文件"), {
      target: { files: [new File(["text"], "notes.txt", { type: "text/plain" })] },
    });

    expect(screen.getByRole("alert").textContent).toContain("仅支持 PDF 或 DOCX 文件。");
    expect(uploadDocument).not.toHaveBeenCalled();
  });

  it("shows the server error when the upload is rejected", async () => {
    vi.mocked(uploadDocument).mockRejectedValue(new Error("File size exceeds the 25 MB limit."));
    render(<UploadPanel />);

    fireEvent.change(screen.getByLabelText("选择文件"), {
      target: { files: [new File(["%PDF-"], "huge.pdf", { type: "application/pdf" })] },
    });

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("File size exceeds the 25 MB limit.");
    });
  });

  it("surfaces a generic message when the failure is not an Error instance", async () => {
    vi.mocked(uploadDocument).mockRejectedValue("boom");
    render(<UploadPanel />);

    fireEvent.change(screen.getByLabelText("选择文件"), {
      target: { files: [new File(["%PDF-"], "report.pdf", { type: "application/pdf" })] },
    });

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("上传失败，请稍后重试。");
    });
  });
});
