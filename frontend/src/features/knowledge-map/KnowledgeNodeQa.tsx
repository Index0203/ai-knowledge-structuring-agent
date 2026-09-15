"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import {
  AnswerCitation,
  NodeIntent,
  QuestionAnswer,
  QuizItem,
  getQuestion,
  submitQuestion,
} from "@/lib/api/questions";
import { KnowledgeTreeNode } from "./types";

type AssistantState = "idle" | "asking" | "answered" | "refused" | "error";

type KnowledgeNodeQaProps = {
  node: KnowledgeTreeNode;
  pollIntervalMs?: number;
  maxPolls?: number;
};

export const ASSISTANT_ACTIONS: Array<{ intent: NodeIntent; label: string; hint: string }> = [
  { intent: "explain", label: "解释这个节点", hint: "用通俗语言说明它是什么" },
  { intent: "example", label: "举例说明", hint: "优先使用原文中的案例与数据" },
  { intent: "deep_dive", label: "深入学习", hint: "拆解要点并给出延伸阅读" },
  { intent: "quiz", label: "生成测试问题", hint: "出题并给出答案与出处" },
];

const DEFAULT_POLL_INTERVAL_MS = 1000;
const DEFAULT_MAX_POLLS = 60;

function citationLabel(citation: AnswerCitation): string {
  if (citation.page_number !== null) return `第 ${citation.page_number} 页`;
  if (citation.paragraph_index !== null) return `第 ${citation.paragraph_index + 1} 段`;
  return "原文";
}

export function KnowledgeNodeQa({
  node,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  maxPolls = DEFAULT_MAX_POLLS,
}: KnowledgeNodeQaProps) {
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<AssistantState>("idle");
  const [answer, setAnswer] = useState<QuestionAnswer | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [pendingLabel, setPendingLabel] = useState("");

  useEffect(() => {
    setQuestion("");
    setState("idle");
    setAnswer(null);
    setErrorMessage("");
    setPendingLabel("");
  }, [node.id]);

  async function run(intent: NodeIntent, text: string, label: string): Promise<void> {
    setState("asking");
    setAnswer(null);
    setErrorMessage("");
    setPendingLabel(label);
    try {
      const submitted = await submitQuestion(node.id, text, intent);
      const result = await pollAnswer(submitted.question_id, pollIntervalMs, maxPolls);
      setAnswer(result);
      setState(result.status === "answered" ? "answered" : "refused");
    } catch (error: unknown) {
      setState("error");
      setErrorMessage(error instanceof Error ? error.message : "提问失败，请稍后重试。");
    } finally {
      setPendingLabel("");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed.length < 2) {
      setState("error");
      setErrorMessage("请至少输入两个字符的问题。");
      return;
    }
    await run("ask", trimmed, "提问");
  }

  const isAsking = state === "asking";

  return (
    <section
      aria-label="节点 AI 助手"
      className="mt-4 rounded-2xl border border-[color:var(--brand-line)] bg-white/85 p-5 shadow-sm backdrop-blur"
    >
      <h3 className="text-sm font-semibold text-slate-900">节点 AI 助手</h3>
      <p className="mt-1 text-xs text-slate-500">
        回答只使用该节点的 Node Context（节点信息 + 原文证据块），并附引用来源；证据不足时会直接拒答。
      </p>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {ASSISTANT_ACTIONS.map((action) => (
          <button
            key={action.intent}
            type="button"
            className="rounded-xl border border-slate-200 px-3 py-2 text-left transition hover:border-[color:var(--brand-ring-soft)] hover:bg-[var(--brand-soft-2)] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isAsking}
            onClick={() => void run(action.intent, "", action.label)}
          >
            <span className="block text-sm font-medium text-slate-800">{action.label}</span>
            <span className="mt-0.5 block text-xs text-slate-500">{action.hint}</span>
          </button>
        ))}
      </div>

      <form className="mt-3" onSubmit={handleSubmit}>
        <textarea
          aria-label="输入问题"
          className="h-16 w-full resize-none rounded-xl border border-slate-200 bg-white/90 p-3 text-sm text-slate-800 outline-none transition focus:border-[color:var(--brand-3)] focus:ring-2 focus:ring-[color:var(--brand-ring)]"
          disabled={isAsking}
          maxLength={1000}
          placeholder={`围绕「${node.title}」提问…`}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button
          type="submit"
          className="mt-2 w-full rounded-xl bg-gradient-to-r from-[var(--brand-1)] via-[var(--brand-2)] to-[var(--brand-3)] px-3 py-2 text-sm font-medium text-white shadow-[0_12px_26px_-16px_var(--brand-shadow-strong)] transition hover:-translate-y-0.5 disabled:translate-y-0 disabled:bg-slate-300 disabled:bg-none disabled:opacity-70"
          disabled={isAsking}
        >
          {isAsking && pendingLabel === "提问" ? "检索原文中…" : "提问"}
        </button>
      </form>

      {isAsking ? (
        <p role="status" className="mt-3 text-sm text-slate-600">
          正在执行「{pendingLabel}」，检索该节点的原文证据…
        </p>
      ) : null}
      {state === "error" ? (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {errorMessage}
        </p>
      ) : null}
      {state === "refused" ? (
        <div role="alert" className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          <p className="font-medium">证据不足，已拒答。</p>
          <p className="mt-1 text-xs">{answer?.error_message ?? "文档中没有找到足以支撑结论的内容。"}</p>
        </div>
      ) : null}
      {state === "answered" && answer ? (
        <div className="mt-3">
          {answer.answer_mode === "extractive_fallback" ? (
            <p className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
              未配置大模型，以下为原文摘录（未改写、未扩写）。
            </p>
          ) : null}
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{answer.answer}</p>

          {answer.quiz_items.length > 0 ? (
            <div className="mt-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">测试问题</h4>
              <ol className="mt-2 space-y-3">
                {answer.quiz_items.map((item, index) => (
                  <QuizCard key={`${item.question}-${index}`} item={item} index={index} />
                ))}
              </ol>
            </div>
          ) : null}

          {answer.citations.length > 0 ? (
            <>
              <h4 className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">引用来源</h4>
              <ol className="mt-2 space-y-2">
                {answer.citations.map((citation, index) => (
                  <li key={citation.chunk_id} className="rounded-lg border border-slate-200 p-3">
                    <p className="text-xs text-slate-500">
                      [{index + 1}] {citation.section_title} · {citationLabel(citation)} · 相关度{" "}
                      {citation.relevance.toFixed(2)}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-700">{citation.quote}</p>
                  </li>
                ))}
              </ol>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function QuizCard({ item, index }: { item: QuizItem; index: number }) {
  return (
    <li className="rounded-lg border border-slate-200 p-3">
      <p className="text-sm font-medium text-slate-800">
        {index + 1}. {item.question}
      </p>
      <p className="mt-1 text-sm leading-6 text-slate-700">{item.answer}</p>
      {item.citations.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {item.citations.map((citation) => (
            <li key={citation.chunk_id} className="text-xs text-slate-500">
              出处：{citation.section_title} · {citationLabel(citation)}
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

async function pollAnswer(questionId: string, pollIntervalMs: number, maxPolls: number): Promise<QuestionAnswer> {
  for (let attempt = 0; attempt < maxPolls; attempt += 1) {
    const result = await getQuestion(questionId);
    if (result.status === "answered" || result.status === "insufficient_evidence") return result;
    if (result.status === "failed") {
      throw new Error(result.error_message ?? "回答生成失败。");
    }
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }
  throw new Error("回答生成超时，请稍后重试。");
}
