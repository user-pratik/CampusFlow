"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage, PanelType, SuggestedAction } from "@/lib/types";
import { getAIResponseAsync } from "@/lib/chatEngine";
import ChatWidget from "./widgets";

interface ChatPanelProps {
  openPanel: (type: PanelType, data?: Record<string, unknown>) => void;
}

export default function ChatPanel({ openPanel }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hey Pratik! I'm your CampusFlow assistant. Ask me about your attendance, marks, WhatsApp messages, emails, calendar, or anything else. I can also help you set reminders, draft replies, or plan your schedule.",
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

    // Simulate AI thinking delay
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

    // Auto-open relevant panel
    if (response.panel) {
      openPanel(response.panel, response.panelData);
    }
  };

  const handleAction = (action: SuggestedAction) => {
    if (action.type === "navigate" && action.payload) {
      openPanel(action.payload as PanelType);
    } else {
      // Treat as a new message
      setInput(action.label);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-w-0">
      {/* Chat header */}
      <header className="h-14 border-b border-border flex items-center px-6 bg-panel-bg shrink-0">
        <h1 className="text-sm font-medium text-foreground">
          AI Assistant
        </h1>
        <span className="ml-2 w-2 h-2 bg-success rounded-full" />
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] md:max-w-[70%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-chat-user text-foreground"
                  : "bg-chat-ai border border-border text-foreground"
              }`}
            >
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </p>

              {/* Inline widget (schedule, calendar, task list) */}
              {msg.widget && <ChatWidget widget={msg.widget} />}

              {/* Suggested actions */}
              {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {msg.suggestedActions.map((action, i) => (
                    <button
                      key={i}
                      onClick={() => handleAction(action)}
                      className="text-xs px-3 py-1.5 rounded-full border border-accent/30 text-accent hover:bg-accent-light transition-colors"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              )}

              <p className="text-[10px] text-secondary mt-2">
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
            <div className="bg-chat-ai border border-border rounded-2xl px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-secondary rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-secondary rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-secondary rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border p-4 bg-panel-bg shrink-0">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="Ask about attendance, marks, messages, schedule..."
            className="chat-input flex-1 px-4 py-3 text-sm bg-surface border border-border rounded-xl text-foreground placeholder:text-secondary"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isTyping}
            className="px-4 py-3 bg-accent text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
