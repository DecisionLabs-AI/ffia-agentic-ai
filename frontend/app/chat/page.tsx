"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
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

function AssistantAvatar() {
  return (
    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-orange-600 text-white shadow-lg shadow-orange-200">
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m-6 8a6 6 0 0 1 12 0v3a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3v-3Z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.5 12.5h.01M14.5 12.5h.01M10 16h4" />
      </svg>
    </div>
  );
}

function ChatExperience({ user }: { user: AuthUser }) {
  const [messages, setMessages] = useState<UiMessage[]>(initialMessages);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryItem[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const isEmptyChat = messages.length <= 1 && !loading;

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

  function deleteHistoryItem(itemId: string) {
    setAnalysisHistory((current) => {
      const next = current.filter((item) => item.id !== itemId);
      localStorage.setItem(historyKey(user.user_id), JSON.stringify(next));
      return next;
    });
  }

  function clearHistory() {
    if (!analysisHistory.length) return;
    const confirmed = window.confirm("ล้างประวัติการวิเคราะห์ทั้งหมดหรือไม่?");
    if (!confirmed) return;
    localStorage.removeItem(historyKey(user.user_id));
    setAnalysisHistory([]);
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

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    submitQuestion(input);
  }

  return (
    <AppShell>
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
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

        <section
          className={`overflow-y-auto rounded-3xl border border-orange-100 bg-white p-4 shadow-sm sm:p-6 ${
            isEmptyChat
              ? "min-h-[320px] max-h-[360px]"
              : "min-h-[420px] max-h-[62vh]"
          }`}
        >
          <div className="space-y-5">
            {messages.map((message, index) => (
              message.role === "human" ? (
                <div key={`${message.role}-${index}`} className="flex justify-end">
                  <div className="max-w-[86%] rounded-2xl bg-orange-600 px-4 py-3 text-sm leading-7 text-white shadow-sm sm:max-w-[75%]">
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  </div>
                </div>
              ) : (
                <div key={`${message.role}-${index}`} className="flex items-start gap-3 sm:gap-4">
                  <AssistantAvatar />
                  <div className="max-w-[calc(100%-4rem)] rounded-2xl border border-orange-100 bg-white px-4 py-3 text-sm leading-7 text-slate-800 shadow-md shadow-orange-100/70 sm:max-w-[75%]">
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    {message.error ? (
                      <p className="mt-2 text-xs font-semibold text-red-600">{message.error}</p>
                    ) : null}
                    {message.trace?.length ? (
                      <details className="mt-3 rounded-xl bg-orange-50/60 p-3 text-xs text-slate-600">
                        <summary className="cursor-pointer font-bold text-slate-800">รายละเอียดการตรวจข้อมูล</summary>
                        <div className="mt-2 space-y-2">
                          {message.trace.map((step, stepIndex) => (
                            <div key={`${step.tool}-${stepIndex}`} className="rounded-lg bg-white p-2">
                              <p className="font-bold">{step.tool}</p>
                              <p className="mt-1 line-clamp-4">{step.observation}</p>
                            </div>
                          ))}
                        </div>
                      </details>
                    ) : null}
                  </div>
                </div>
              )
            ))}
            {loading ? (
              <div className="flex items-start gap-3 sm:gap-4">
                <AssistantAvatar />
                <div className="max-w-sm rounded-2xl border border-orange-100 bg-white px-4 py-3 text-sm font-semibold text-slate-600 shadow-md shadow-orange-100/70">
                  FFIA กำลังวิเคราะห์ข้อมูลร้านและต้นทุน...
                </div>
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
              onKeyDown={handleInputKeyDown}
              rows={2}
              className="min-h-14 flex-1 resize-none rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-orange-300 focus:ring-2 focus:ring-orange-100"
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

        <section className="rounded-2xl border border-orange-100 bg-white p-3 shadow-sm">
          <div className="flex min-h-11 flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => setHistoryOpen((current) => !current)}
              className="flex items-center gap-2 text-left text-sm font-black text-slate-900 transition hover:text-orange-700"
              aria-expanded={historyOpen}
            >
              <span>{historyOpen ? "▼" : "▶"} ประวัติการวิเคราะห์ ({analysisHistory.length} รายการ)</span>
            </button>
            {historyOpen && analysisHistory.length ? (
              <button
                type="button"
                onClick={clearHistory}
                className="rounded-full border border-orange-100 bg-orange-50 px-3 py-1 text-xs font-bold text-orange-700 transition hover:border-orange-200 hover:bg-orange-100"
              >
                ล้างประวัติ
              </button>
            ) : null}
          </div>

          {historyOpen ? (
            analysisHistory.length ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {analysisHistory.map((item) => (
                  <div
                    key={item.id}
                    className="flex gap-2 rounded-2xl border border-slate-100 bg-slate-50 p-3 transition hover:border-orange-200 hover:bg-orange-50"
                  >
                    <button
                      type="button"
                      onClick={() => openHistoryItem(item)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <p className="line-clamp-2 text-sm font-bold text-slate-900">{item.question}</p>
                      <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-600">{item.answerPreview}</p>
                      <p className="mt-2 text-[11px] font-semibold text-slate-400">{formatHistoryTime(item.timestamp)}</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteHistoryItem(item.id)}
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                      aria-label="ลบประวัติรายการนี้"
                      title="ลบประวัติรายการนี้"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 7h12M10 11v6M14 11v6M9 7l1-2h4l1 2M8 7l1 13h6l1-13" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                ยังไม่มีประวัติการวิเคราะห์ในรอบนี้
              </div>
            )
          ) : null}
        </section>
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
