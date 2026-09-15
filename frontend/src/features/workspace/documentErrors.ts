import type { DocumentStatus } from "@/lib/api/documents";

type FailableDocument = Pick<DocumentStatus, "error_code" | "error_message">;

const FALLBACK_MESSAGE = "文档处理失败，请稍后重试。";

/**
 * Turns a backend failure code into an actionable message for the end user.
 * The technical `error_message` stays available for unknown failures.
 */
export function describeDocumentError(status: FailableDocument): string {
  switch (status.error_code) {
    case "no_text_layer":
      return "这份文件没有可以提取的文字层（扫描件或图片版 PDF），暂时无法生成知识结构。请提供可以选中文字的 PDF，或等待 OCR 支持。";
    case "unsupported_format":
      return "暂不支持这种文件类型，目前只接受 PDF 和 DOCX。";
    case "processing_failed":
      return status.error_message ?? FALLBACK_MESSAGE;
    default:
      return status.error_message ?? FALLBACK_MESSAGE;
  }
}
