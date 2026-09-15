import { describe, expect, it } from "vitest";

import { describeDocumentError } from "./documentErrors";

describe("describeDocumentError", () => {
  it("explains a scanned PDF in actionable Chinese", () => {
    const message = describeDocumentError({
      error_code: "no_text_layer",
      error_message: "The PDF has no extractable text layer: 25 of 25 pages are images.",
    });

    expect(message).toContain("没有可以提取的文字层");
    expect(message).toContain("可以选中文字的 PDF");
  });

  it("explains an unsupported format", () => {
    expect(
      describeDocumentError({ error_code: "unsupported_format", error_message: null }),
    ).toContain("只接受 PDF 和 DOCX");
  });

  it("falls back to the technical message for unknown failures", () => {
    expect(
      describeDocumentError({ error_code: "processing_failed", error_message: "Parser crashed." }),
    ).toBe("Parser crashed.");
  });

  it("uses a safe default when nothing is known", () => {
    expect(describeDocumentError({ error_code: null, error_message: null })).toBe(
      "文档处理失败，请稍后重试。",
    );
  });
});
