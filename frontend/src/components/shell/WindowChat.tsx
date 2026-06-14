"use client";

import { useState, useRef, useEffect, useCallback } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface WindowChatProps {
  /** Agent type identifier sent as window_context.agent (e.g. "attendance_risk") */
  agentType: string;
  /** Current data displayed in the window — sent as window_context.data */
  contextData: Record<string, unknown>;
  /** Whether the chat is initially expanded */
  defaultExpanded?: boolean;
}

// ─── Component ───────────────────────────────────────────────────────────────

/**
 * Shared mini-chat input embedded at the bottom of every agent floating window.
 * Sends follow-up messages to POST /api/chat with window_context attached.
 * Responses render inline as a message thread within the window.
 *
 * Usage:
 * ```tsx
 * <WindowChat agentType="attendance_risk" contextData={riskData} />
 * ```
 */
export default function WindowChat({ agentType, contextData, defaultExpanded = false }: WindowChatProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    // Add user message
    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: `window_${agentType}`,
          window_context: {
            agent: agentType,
            data: contextData,
          },
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const assistantMsg: ChatMessage = { role: "assistant", content: data.response };
        setMessages((prev) => [...prev, assistantMsg]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Sorry, something went wrong. Try again." },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Unable to reach backend." },
      ]);
    }

    setLoading(false);
  }, [input, loading, agentType, contextData]);

  // Collapsed state: just show the expand trigger
  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full mt-2 pt-2 border-t border-border flex items-center justify-center gap-1.5 text-[10px] text-secondary hover:text-accent transition-colors"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
        <span>Ask a follow-up...</span>
      </button>
    );
  }

  return (
    <div className="mt-2 pt-2 border-t border-border space-y-2">
      {/* Message thread */}
      {messages.length > 0 && (
        <div className="max-h-32 overflow-y-auto space-y-1.5 px-0.5">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`text-[11px] px-2 py-1.5 rounded-md ${
                msg.role === "user"
                  ? "bg-chat-user text-foreground ml-4"
                  : "bg-chat-ai border border-border text-foreground mr-4"
              }`}
            >
              {msg.content}
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-1 px-2 py-1.5 text-[11px] text-secondary">
              <span className="w-1 h-1 rounded-full bg-secondary animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1 h-1 rounded-full bg-secondary animate-bounce" style={{ animationDelay: "100ms" }} />
              <span className="w-1 h-1 rounded-full bg-secondary animate-bounce" style={{ animationDelay: "200ms" }} />
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Input bar */}
      <div className="flex items-center gap-1.5">
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
          placeholder="Ask about this data..."
          className="flex-1 text-[11px] px-2.5 py-1.5 bg-surface border border-border rounded-md text-foreground placeholder:text-secondary outline-none focus:border-accent"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="px-2 py-1.5 bg-accent text-white text-[10px] font-medium rounded-md hover:opacity-90 disabled:opacity-30 shrink-0"
        >
          ↑
        </button>
        <button
          onClick={() => setExpanded(false)}
          className="px-1.5 py-1.5 text-[10px] text-secondary hover:text-foreground rounded-md shrink-0"
          title="Collapse chat"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
