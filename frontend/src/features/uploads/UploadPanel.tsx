"use client";

import { ChangeEvent, useState } from "react";

import { uploadDocument, UploadedDocument } from "@/lib/api/uploads";

const ACCEPTED_TYPES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
type UploadState = "idle" | "uploading" | "success" | "error";

type UploadPanelProps = {
  onUploaded?: (document: UploadedDocument) => void;
};

export function UploadPanel({ onUploaded }: UploadPanelProps) {
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState("选择 PDF 或 DOCX 文件开始上传。");
  const [document, setDocument] = useState<UploadedDocument | null>(null);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!ACCEPTED_TYPES.includes(file.type) && !/\.(pdf|docx)$/i.test(file.name)) {
      setState("error");
      setMessage("仅支持 PDF 或 DOCX 文件。");
      return;
    }
    setState("uploading");
    setDocument(null);
    setMessage(`正在上传 ${file.name}…`);
    try {
      const uploadedDocument = await uploadDocument(file);
      setDocument(uploadedDocument);
      setState("success");
      setMessage("文件已上传并完成类型验证，正在进入文档理解流程。");
      onUploaded?.(uploadedDocument);
    } catch (error: unknown) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "上传失败，请稍后重试。");
    }
  }

  const statusColor = state === "error" ? "text-rose-600" : state === "success" ? "text-emerald-600" : "text-slate-500";
  return (
    <section
      aria-labelledby="upload-title"
      className="w-full rounded-3xl border border-white/70 bg-white/80 p-7 shadow-[0_24px_60px_-30px_var(--brand-shadow)] backdrop-blur"
    >
      <p className="bg-gradient-to-r from-[var(--brand-1)] via-[var(--brand-2)] to-[var(--brand-4)] bg-clip-text text-sm font-semibold tracking-wide text-transparent">
        文档上传
      </p>
      <h1 id="upload-title" className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">上传资料</h1>
      <p className="mt-3 leading-6 text-slate-600">支持 PDF 和 DOCX。文件将被安全保存并验证类型，后续将进入文档理解流程。</p>
      <label className="mt-6 flex cursor-pointer flex-col items-center rounded-2xl border-2 border-dashed border-[color:var(--brand-line)] bg-gradient-to-br from-[var(--brand-soft)] via-[var(--brand-soft-2)] to-white px-6 py-8 text-center transition hover:border-[color:var(--brand-ring-soft)] hover:shadow-[0_16px_36px_-24px_var(--brand-shadow-strong)]">
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-[var(--brand-1)] via-[var(--brand-3)] to-[var(--brand-4)] text-white shadow-md">
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 16V4" />
            <path d="M8 8l4-4 4 4" />
            <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
          </svg>
        </span>
        <span className="mt-3 font-semibold text-slate-800">选择文件</span>
        <span className="mt-1 text-sm text-slate-500">PDF 或 DOCX，最大 25 MB</span>
        <input aria-label="选择文件" className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" disabled={state === "uploading"} onChange={handleFileChange} />
      </label>
      <p role={state === "error" ? "alert" : "status"} className={`mt-4 text-sm ${statusColor}`}>{message}</p>
      {document ? (
        <p className="mt-2 truncate rounded-lg bg-white/70 px-3 py-2 text-xs text-slate-500">
          已保存：{document.original_filename}（{document.size_bytes} 字节）
        </p>
      ) : null}
    </section>
  );
}
