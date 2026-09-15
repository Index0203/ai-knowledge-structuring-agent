import { apiBaseUrl } from "./client";

export type QuestionStatus = "queued" | "running" | "answered" | "insufficient_evidence" | "failed";
export type AnswerMode = "llm" | "extractive_fallback";
export type NodeIntent = "explain" | "example" | "deep_dive" | "quiz" | "ask";

export type AnswerCitation = {
  chunk_id: string;
  quote: string;
  section_title: string;
  chunk_index: number;
  page_number: number | null;
  paragraph_index: number | null;
  relevance: number;
};

export type QuestionAnswer = {
  question_id: string;
  document_id: string;
  node_id: string;
  intent: NodeIntent;
  question: string;
  status: QuestionStatus;
  answer: string | null;
  answer_mode: AnswerMode | null;
  model: string | null;
  prompt_version: string | null;
  confidence: number | null;
  citations: AnswerCitation[];
  quiz_items: QuizItem[];
  error_message: string | null;
  latency_ms: number | null;
  created_at: string;
  answered_at: string | null;
};

export type QuizItem = {
  question: string;
  answer: string;
  citations: AnswerCitation[];
};

export type QuestionSubmitted = {
  question_id: string;
  node_id: string;
  intent: NodeIntent;
  status: QuestionStatus;
  created_at: string;
};

type ErrorPayload = { detail?: unknown };

async function readError(response: Response, fallback: string): Promise<Error> {
  const payload: ErrorPayload = await response.json().catch(() => ({}));
  return new Error(typeof payload.detail === "string" ? payload.detail : fallback);
}

export async function submitQuestion(
  nodeId: string,
  question: string,
  intent: NodeIntent = "ask",
): Promise<QuestionSubmitted> {
  const response = await fetch(`${apiBaseUrl}/api/v1/knowledge-nodes/${nodeId}/questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, intent }),
  });
  if (!response.ok) {
    throw await readError(response, "提问失败，请稍后重试。");
  }
  return response.json() as Promise<QuestionSubmitted>;
}

export async function getQuestion(questionId: string): Promise<QuestionAnswer> {
  const response = await fetch(`${apiBaseUrl}/api/v1/questions/${questionId}`);
  if (!response.ok) {
    throw await readError(response, "无法读取回答。");
  }
  return response.json() as Promise<QuestionAnswer>;
}
