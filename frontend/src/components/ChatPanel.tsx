"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage, PanelType, SuggestedAction } from "@/lib/types";
import { getAIResponseAsync } from "@/lib/chatEngine";
import ChatWidget from "./widgets";
import { Send, Mic } from "lucide-react";

interface ChatPanelProps {
  openPanel: (type: PanelType, data?: Record<string, unknown>) => void;
}

export default function ChatPanel({ openPanel }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hey! I'm your CampusFlow assistant. Ask me about your attendance, marks, WhatsApp messages, emails, calendar, or anything else. I can also help you set reminders, draft replies, or plan your schedule.",
      timestamp: new Date(),
      suggestedActions: [
        { label: "How's my attendance?", type: "navigate", payload: "attendance" },
        { label: "Any new messages?", type: "navigate", payload: "whatsapp" },
        { label: "What's due this week?", type: "navigate", payload: "calendar" },
      ],
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    await new Promise((r) => setTimeout(r, 600 + Math.random() * 800));

    const response = await getAIResponseAsync(text);
    const aiMsg: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: response.content,
      timestamp: new Date(),
      suggestedActions: response.actions,
      panel: response.panel,
      panelData: response.panelData,
      widget: response.widget,
    };

    setMessages((prev) => [...prev, aiMsg]);
    setIsTyping(false);

    if (response.panel) {
      openPanel(response.panel, response.panelData);
    }
  };

  const handleAction = (action: SuggestedAction) => {
    if (action.type === "navigate" && action.payload) {
      openPanel(action.payload as PanelType);
    } else {
      setInput(action.label);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-[760px] mx-auto space-y-5">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-accent text-white"
                    : "bg-[var(--bg-surface)] border border-[var(--border-glass)] text-[var(--text-primary)]"
                }`}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </p>

                {msg.widget && <ChatWidget widget={msg.widget} />}

                {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {msg.suggestedActions.map((action, i) => (
                      <button
                        key={i}
                        onClick={() => handleAction(action)}
                        className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                          msg.role === "user"
                            ? "border-white/30 text-white/90 hover:bg-white/10"
                            : "border-accent/30 text-accent hover:bg-accent/10"
                        }`}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}

                <p className={`text-[10px] mt-2 ${msg.role === "user" ? "text-white/60" : "text-[var(--text-muted)]"}`}>
                  {msg.timestamp.toLocaleTimeString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
            </div>
          ))}

          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-[var(--bg-surface)] border border-[var(--border-glass)] rounded-2xl px-4 py-3">
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 bg-[var(--text-muted)] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-[var(--text-muted)] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-[var(--text-muted)] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="shrink-0 px-4 pb-20 pt-3">
        <div className="max-w-[760px] mx-auto">
          <div className="flex items-center gap-2 bg-[var(--bg-surface)] border border-[var(--border-glass)] rounded-full px-4 py-2 shadow-lg focus-within:shadow-[0_0_20px_var(--accent-glow)] transition-shadow">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="Ask CampusFlow anything..."
              className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none"
            />
            <button
              className="w-8 h-8 flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title="Voice (coming soon)"
            >
              <Mic size={16} />
            </button>
            <button
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-accent text-white disabled:opacity-40 transition-opacity hover:opacity-90"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
