"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";

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
      content: "Hey Pratik! Ask me about your attendance, marks, deadlines, placements, or schedule. I can also set reminders and plan your day.",
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

  // Send the initial message on mount if provided
  useEffect(() => {
    if (hasSentInitial.current || !initialMessage) return;
    hasSentInitial.current = true;
    sendMessage(initialMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage]);

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
                  ? "bg-chat-user text-foreground"
                  : "bg-chat-ai border border-border text-foreground"
              }`}
            >
              <p className="text-[11px] leading-relaxed whitespace-pre-wrap">{msg.content}</p>

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
            <div className="bg-chat-ai border border-border rounded-xl px-3 py-2">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-secondary rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-secondary rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-secondary rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
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
          placeholder="Ask anything..."
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
 * Hook to spawn the main Chat Agent floating window.
 * Includes welcome message, suggested actions, full conversation history.
 */
export function useChatAgent() {
  const { spawnWindow } = useWindowManager();

  const spawn = useCallback(
    (message?: string) => {
      spawnWindow(
        "Chat",
        "CampusFlow Chat",
        <ChatWindowContent initialMessage={message} />,
        {
          agentIcon: "💬",
          size: { width: 400, height: 450 },
          position: { x: 180, y: 80 },
        }
      );
    },
    [spawnWindow]
  );

  return { spawn };
}
