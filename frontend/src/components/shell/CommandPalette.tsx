"use client";

import { useState } from "react";
import { useChatAgent } from "./ChatAgentWindow";
import { useEmailAgent } from "./EmailAgentWindow";
import { useWhatsAppAgent } from "./WhatsAppAgentWindow";
import { chatBus } from "@/lib/chatBus";

// ─── Component ───────────────────────────────────────────────────────────────

export default function CommandPalette() {
  const [input, setInput] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [processing, setProcessing] = useState(false);
  const { spawn: spawnChat } = useChatAgent();
  const { spawn: spawnEmail } = useEmailAgent();
  const { spawn: spawnWhatsApp } = useWhatsAppAgent();

  const handleSubmit = async () => {
    const text = input.trim();
    if (!text || processing) return;

    setInput("");
    setProcessing(true);

    // Step 3: Intent keyword interception — open relevant windows alongside chat
    const lowerText = text.toLowerCase();
    if (lowerText.includes("whatsapp") || lowerText.includes("messages")) {
      spawnWhatsApp();
    }
    if (lowerText.includes("gmail") || lowerText.includes("email") || lowerText.includes("mail")) {
      spawnEmail();
    }

    // Step 1: Open/focus the Chat window and send the message via the bus
    spawnChat(); // Opens if not exists, focuses if already open (singleton)
    // Small delay to ensure the Chat component is mounted and subscribed
    setTimeout(() => chatBus.send(text), 50);

    setProcessing(false);
  };

  return (
    <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-9998 w-full max-w-xl px-4">
      <div
        className={`flex items-center gap-3 bg-panel-bg/95 backdrop-blur-md border rounded-2xl px-4 py-3 shadow-lg transition-all ${
          isFocused ? "border-accent ring-2 ring-accent/20 shadow-xl" : "border-border"
        }`}
      >
        {/* Command icon */}
        <span className="text-secondary text-sm shrink-0">
          {processing ? (
            <span className="inline-block w-3.5 h-3.5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          ) : (
            "⌘"
          )}
        </span>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="Ask CampusFlow anything... (attendance, deadlines, schedule)"
          className="flex-1 bg-transparent text-sm text-foreground placeholder:text-secondary outline-none"
          disabled={processing}
        />

        <button
          onClick={handleSubmit}
          disabled={!input.trim() || processing}
          className="px-3 py-1.5 bg-accent text-white text-xs font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-30 shrink-0"
        >
          {processing ? "..." : "Ask"}
        </button>
      </div>
      <p className="text-center text-[10px] text-secondary mt-1.5">
        Responses appear as floating windows · Press Enter to send
      </p>
    </div>
  );
}
