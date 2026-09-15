import { apiBaseUrl } from "./client";

export type UploadedDocument = {
  document_id: string;
  original_filename: string;
  media_type: "application/pdf" | "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  size_bytes: number;
  storage_key: string;
  uploaded_at: string;
};

type ErrorPayload = { detail?: unknown };

function getErrorMessage(payload: ErrorPayload): string {
  return typeof payload.detail === "string" ? payload.detail : "Upload failed. Please try again.";
}

export async function uploadDocument(file: File): Promise<UploadedDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${apiBaseUrl}/api/v1/uploads`, { method: "POST", body: formData });
  if (!response.ok) {
    const payload: ErrorPayload = await response.json().catch(() => ({}));
    throw new Error(getErrorMessage(payload));
  }
  return response.json() as Promise<UploadedDocument>;
}
