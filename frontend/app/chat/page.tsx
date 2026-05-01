"use client";

import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import AuthGuard from "@/components/AuthGuard";
import { AuthUser } from "@/lib/auth";
import { ChatMessage, ToolStep, sendMessage } from "@/lib/api";

const quickQuestions = [
  "ดีเซลขึ้น 5 บาท กระทบฉันแค่ไหน",
  "ช่องทางเดลิเวอรี่ยังทำกำไรไหม",
  "โปรนี้ยังคุ้มไหม",
  "ต้นทุนฉันแพงตรงไหน",
  "กำไรหายไปตรงไหน",
  "วัตถุดิบไหนแพงที่สุด",
];

type UiMessage = {
  role: "human" | "ai";
  content: string;
  trace?: ToolStep[];
  error?: string;
};

type AnalysisHistoryItem = {
  id: string;
  question: string;
  answer: string;
  answerPreview: string;
  timestamp: string;
};

function initialMessages(): UiMessage[] {
  return [
    {
      role: "ai",
      content: "สวัสดี ฉันคือ FFIA ถามเรื่องต้นทุนจริง น้ำมัน GP เดลิเวอรี่ โปรโมชัน หรือวัตถุดิบที่กระทบกำไรได้เลย",
    },
  ];
}

function historyKey(userId: string) {
  return `ffia_analysis_history_${userId}`;
}

function makePreview(text: string) {
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length > 96 ? `${normalized.slice(0, 96)}...` : normalized;
}

function formatHistoryTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function ChatExperience({ user }: { user: AuthUser }) {
  const [messages, setMessages] = useState<UiMessage[]>(initialMessages);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryItem[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q");
    if (q) setInput(q);
  }, []);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(historyKey(user.user_id));
      setAnalysisHistory(stored ? JSON.parse(stored) : []);
    } catch {
      setAnalysisHistory([]);
    }
  }, [user.user_id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function saveHistoryItem(question: string, answer: string) {
    const item: AnalysisHistoryItem = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      question,
      answer,
      answerPreview: makePreview(answer),
      timestamp: new Date().toISOString(),
    };
    setAnalysisHistory((current) => {
      const next = [item, ...current].slice(0, 20);
      localStorage.setItem(historyKey(user.user_id), JSON.stringify(next));
      return next;
    });
  }

  function openHistoryItem(item: AnalysisHistoryItem) {
    setMessages([
      ...initialMessages(),
      { role: "human", content: item.question },
      { role: "ai", content: item.answer },
    ]);
    setInput("");
  }

  async function submitQuestion(question: string) {
    const text = question.trim();
    if (!text || loading) return;
    const history: ChatMessage[] = messages.map((message) => ({
      role: message.role,
      content: message.content,
    }));

    setMessages((current) => [...current, { role: "human", content: text }]);
    setInput("");
    setLoading(true);
    try {
      const response = await sendMessage(text, history, user.user_id);
      const answer = response.output || "FFIA ยังไม่มีคำตอบสำหรับคำถามนี้";
      setMessages((current) => [
        ...current,
        {
          role: "ai",
          content: answer,
          trace: response.intermediate_steps,
          error: response.error,
        },
      ]);
      saveHistoryItem(text, answer);
    } catch (err: unknown) {
      setMessages((current) => [
        ...current,
        {
          role: "ai",
          content: "ขออภัย ตอนนี้เชื่อมต่อ FFIA ไม่สำเร็จ ลองใหม่อีกครั้งหลังตรวจว่า backend ทำงานอยู่",
          error: err instanceof Error ? err.message : "chat_error",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitQuestion(input);
  }

  return (
    <AppShell>
      <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-6xl flex-col gap-5 lg:min-h-[calc(100vh-4rem)]">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">AI business advisor</p>
          <h1 className="mt-2 text-3xl font-black text-slate-950">ถาม FFIA</h1>
          <p className="mt-2 text-sm text-slate-600">ถามแบบเจ้าของร้าน: คุ้มไหม แพงตรงไหน กระทบกำไรเท่าไร และควรทำอะไรก่อน</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {quickQuestions.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => submitQuestion(question)}
              className="rounded-full border border-orange-200 bg-white px-4 py-2 text-sm font-semibold text-orange-800 transition hover:bg-orange-50 disabled:opacity-60"
              disabled={loading}
            >
              {question}
            </button>
          ))}
        </div>

        <section className="min-h-[360px] flex-1 overflow-y-auto rounded-3xl border border-orange-100 bg-white p-4 shadow-sm sm:p-6">
          <div className="space-y-5">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`flex ${message.role === "human" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-7 shadow-sm sm:max-w-[75%] ${
                  message.role === "human"
                    ? "bg-orange-600 text-white"
                    : "border border-slate-100 bg-slate-50 text-slate-800"
                }`}>
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.error ? (
                    <p className="mt-2 text-xs font-semibold text-red-600">{message.error}</p>
                  ) : null}
                  {message.trace?.length ? (
                    <details className="mt-3 rounded-xl bg-white p-3 text-xs text-slate-600">
                      <summary className="cursor-pointer font-bold text-slate-800">รายละเอียดการตรวจข้อมูล</summary>
                      <div className="mt-2 space-y-2">
                        {message.trace.map((step, stepIndex) => (
                          <div key={`${step.tool}-${stepIndex}`} className="rounded-lg bg-slate-50 p-2">
                            <p className="font-bold">{step.tool}</p>
                            <p className="mt-1 line-clamp-4">{step.observation}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                  ) : null}
                </div>
              </div>
            ))}
            {loading ? (
              <div className="max-w-sm rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-600">
                FFIA กำลังวิเคราะห์ข้อมูลร้านและต้นทุน...
              </div>
            ) : null}
            <div ref={bottomRef} />
          </div>
        </section>

        <form onSubmit={handleSubmit} className="rounded-2xl border border-orange-100 bg-white p-3 shadow-sm">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              rows={2}
              className="min-h-14 flex-1 resize-none rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-orange-400 focus:ring-4 focus:ring-orange-100"
              placeholder="พิมพ์คำถาม เช่น โปรลด 20% ยังเหลือกำไรไหม หรือดีเซลขึ้น 5 บาทกระทบเมนูขายดีแค่ไหน"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="self-stretch rounded-xl bg-orange-600 px-5 text-sm font-black text-white transition hover:bg-orange-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              ส่ง
            </button>
          </div>
        </form>

        <details className="rounded-2xl border border-orange-100 bg-white p-4 shadow-sm">
          <summary className="cursor-pointer text-sm font-black text-slate-900">
            ประวัติการวิเคราะห์ ({analysisHistory.length} รายการ)
          </summary>

          {analysisHistory.length ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {analysisHistory.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => openHistoryItem(item)}
                  className="rounded-2xl border border-slate-100 bg-slate-50 p-3 text-left transition hover:border-orange-200 hover:bg-orange-50"
                >
                  <p className="line-clamp-2 text-sm font-bold text-slate-900">{item.question}</p>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-600">{item.answerPreview}</p>
                  <p className="mt-2 text-[11px] font-semibold text-slate-400">{formatHistoryTime(item.timestamp)}</p>
                </button>
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
              ยังไม่มีประวัติการวิเคราะห์ในรอบนี้
            </div>
          )}
        </details>
      </div>
    </AppShell>
  );
}

export default function ChatPage() {
  return (
    <AuthGuard>
      {(user) => <ChatExperience user={user} />}
    </AuthGuard>
  );
}
