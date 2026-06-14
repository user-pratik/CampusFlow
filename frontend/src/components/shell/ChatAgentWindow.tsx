"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  hint?: string | null;
}

interface ChatWindowContentProps {
  initialMessage: string;
}

// ─── Window Content ──────────────────────────────────────────────────────────

function ChatWindowContent({ initialMessage }: ChatWindowContentProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const hasSentInitial = useRef(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Send the initial message on mount
  useEffect(() => {
    if (hasSentInitial.current || !initialMessage) return;
    hasSentInitial.current = true;
    sendMessage(initialMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage]);

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: "chat_window",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        // Detect if response maps to a specialized agent window
        const intent = data.intent || "";
        let hint: string | null = null;
        if (intent === "attendance_risk" || (intent === "academic" && /attendance/i.test(text))) {
          hint = "For interactive data, type 'attendance' in the command bar below.";
        } else if (intent === "academic" && /cgpa|gpa|grade/i.test(text)) {
          hint = "For the interactive calculator, type 'gpa' in the command bar below.";
        }

        setMessages((prev) => [...prev, { role: "assistant", content: data.response, hint }]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Sorry, something went wrong." },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Unable to reach backend." },
      ]);
    }

    setLoading(false);
  }, []);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    sendMessage(text);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-2 mb-2">
        {messages.map((msg, i) => (
          <div key={i}>
            <div
              className={`text-[11px] px-2.5 py-2 rounded-lg ${
                msg.role === "user"
                  ? "bg-chat-user text-foreground ml-6"
                  : "bg-chat-ai border border-border text-foreground mr-4"
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
            </div>
            {msg.hint && (
              <p className="text-[10px] text-accent mt-1 ml-1 italic">
                💡 {msg.hint}
              </p>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-1 px-3 py-2 text-xs text-secondary">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce" style={{ animationDelay: "100ms" }} />
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce" style={{ animationDelay: "200ms" }} />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex items-center gap-1.5 pt-2 border-t border-border">
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
          placeholder="Continue the conversation..."
          className="flex-1 text-xs px-3 py-2 bg-surface border border-border rounded-lg text-foreground placeholder:text-secondary outline-none focus:border-accent"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="px-3 py-2 bg-accent text-white text-xs font-medium rounded-lg hover:opacity-90 disabled:opacity-30 shrink-0"
        >
          ↑
        </button>
      </div>
    </div>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

/**
 * Hook to spawn the generic Chat Agent floating window.
 * Used as fallback when no specialized agent confidently matches the query.
 */
export function useChatAgent() {
  const { spawnWindow } = useWindowManager();

  const spawn = useCallback(
    (message: string) => {
      spawnWindow(
        "Chat",
        "CampusFlow Chat",
        <ChatWindowContent initialMessage={message} />,
        {
          agentIcon: "💬",
          size: { width: 380, height: 400 },
          position: { x: 200, y: 100 },
        }
      );
    },
    [spawnWindow]
  );

  return { spawn };
}
