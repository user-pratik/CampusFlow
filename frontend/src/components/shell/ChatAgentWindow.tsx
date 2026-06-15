"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";
import { chatBus } from "@/lib/chatBus";
import ReactMarkdown from "react-markdown";

// ─── Types ───────────────────────────────────────────────────────────────────

interface SuggestedAction {
  label: string;
  type: string;
  payload?: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  actions?: SuggestedAction[];
  timestamp: Date;
}

interface ChatWindowContentProps {
  initialMessage?: string;
}

// ─── Window Content ──────────────────────────────────────────────────────────

function ChatWindowContent({ initialMessage }: ChatWindowContentProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Hey Ankit! Ask me about your attendance, marks, deadlines, placements, or schedule. I can also set reminders and plan your day.",
      actions: [
        { label: "How's my attendance?", type: "send" },
        { label: "What's due this week?", type: "send" },
        { label: "Show my CGPA", type: "send" },
        { label: "Any placement drives?", type: "send" },
      ],
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const hasSentInitial = useRef(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: ChatMessage = { role: "user", content: text, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: "main_chat",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        // Build suggested actions from backend response
        const actions: SuggestedAction[] = (data.actions || []).map(
          (a: { label: string; type: string; payload?: string }) => ({
            label: a.label,
            type: a.type || "send",
            payload: a.payload,
          })
        );

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.response,
            actions: actions.length > 0 ? actions : undefined,
            timestamp: new Date(),
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Something went wrong. Try again.", timestamp: new Date() },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Can't reach the backend — is it running?", timestamp: new Date() },
      ]);
    }

    setLoading(false);
  }, []);

  // Send the initial message on mount if provided
  useEffect(() => {
    if (hasSentInitial.current || !initialMessage) return;
    hasSentInitial.current = true;
    sendMessage(initialMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage]);

  // Subscribe to global chatBus — receives messages from Command Palette
  useEffect(() => {
    const unsubscribe = chatBus.subscribe((msg) => {
      sendMessage(msg);
    });
    return unsubscribe;
  }, [sendMessage]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    sendMessage(text);
  };

  const handleAction = (action: SuggestedAction) => {
    if (action.type === "send" || action.type === "reply") {
      sendMessage(action.label);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 mb-2 pr-1">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[90%] rounded-xl px-3 py-2 ${
                msg.role === "user"
                  ? "bg-emerald-900 text-emerald-50"
                  : "bg-slate-800 border border-slate-700 text-slate-100"
              }`}
            >
              <div className="text-[11px] leading-relaxed prose-chat">
                <ReactMarkdown
                  components={{
                    p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                    strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                    em: ({ children }) => <em className="italic">{children}</em>,
                    ul: ({ children }) => <ul className="list-disc list-inside mb-1.5 space-y-0.5">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal list-inside mb-1.5 space-y-0.5">{children}</ol>,
                    li: ({ children }) => <li className="ml-1">{children}</li>,
                    code: ({ children }) => <code className="bg-white/10 px-1 py-0.5 rounded text-[10px] font-mono">{children}</code>,
                    pre: ({ children }) => <pre className="bg-white/5 border border-white/10 rounded-md p-2 overflow-x-auto text-[10px] my-1.5">{children}</pre>,
                    h1: ({ children }) => <h1 className="text-sm font-bold mb-1">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-xs font-bold mb-1">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-xs font-semibold mb-0.5">{children}</h3>,
                    a: ({ children, href }) => <a href={href} className="text-accent underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                    blockquote: ({ children }) => <blockquote className="border-l-2 border-accent/50 pl-2 italic opacity-80 my-1">{children}</blockquote>,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              </div>

              {/* Suggested actions */}
              {msg.actions && msg.actions.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {msg.actions.map((action, j) => (
                    <button
                      key={j}
                      onClick={() => handleAction(action)}
                      className="text-[10px] px-2.5 py-1 rounded-full border border-accent/30 text-accent hover:bg-accent-light transition-colors"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              )}

              <p className="text-[9px] text-secondary mt-1.5">
                {msg.timestamp.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex items-center gap-1.5 pt-2 border-t border-slate-800">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Ask anything..."
          className="flex-1 text-xs px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder:text-slate-500 outline-none focus:border-emerald-500"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="px-3 py-2 bg-emerald-600 text-white text-xs font-medium rounded-lg hover:bg-emerald-500 transition-colors disabled:opacity-30 shrink-0"
        >
          ↑
        </button>
      </div>
    </div>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

/**
 * Hook to spawn the main Chat Agent floating window.
 * Ensures only ONE chat window exists — focuses it if already open.
 */
export function useChatAgent() {
  const { spawnWindow, windows, focusWindow, restoreWindow } = useWindowManager();

  const spawn = useCallback(
    (message?: string) => {
      // Check if chat window already exists
      const existing = windows.find(
        (w) => w.agentName === "Chat" && w.title === "CampusFlow Chat"
      );
      if (existing) {
        // Always ensure it's open and focused (never toggle-minimize from here)
        if (existing.state === "minimized") {
          restoreWindow(existing.id);
        } else {
          focusWindow(existing.id);
        }
        return;
      }

      // Center horizontally and vertically on screen
      const chatWidth = 400;
      const chatHeight = 500;
      const x = typeof window !== "undefined" ? Math.round(window.innerWidth / 2 - chatWidth / 2) : 300;
      const y = typeof window !== "undefined" ? Math.round(window.innerHeight / 2 - chatHeight / 2) : 100;

      spawnWindow(
        "Chat",
        "CampusFlow Chat",
        <ChatWindowContent initialMessage={message} />,
        {
          agentIcon: "💬",
          size: { width: chatWidth, height: chatHeight },
          position: { x, y },
          pinned: true,
        }
      );
    },
    [spawnWindow, windows, focusWindow, restoreWindow]
  );

  // Auto-spawn on first render
  const autoSpawn = useCallback(() => {
    const existing = windows.find(
      (w) => w.agentName === "Chat" && w.title === "CampusFlow Chat"
    );
    if (!existing) {
      const chatWidth = 400;
      const chatHeight = 500;
      const x = typeof window !== "undefined" ? Math.round(window.innerWidth / 2 - chatWidth / 2) : 300;
      const y = typeof window !== "undefined" ? Math.round(window.innerHeight / 2 - chatHeight / 2) : 100;

      spawnWindow(
        "Chat",
        "CampusFlow Chat",
        <ChatWindowContent />,
        {
          agentIcon: "💬",
          size: { width: chatWidth, height: chatHeight },
          position: { x, y },
          pinned: true,
        }
      );
    }
  }, [spawnWindow, windows]);

  return { spawn, autoSpawn };
}
