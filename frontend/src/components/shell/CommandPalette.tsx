"use client";

import { useState } from "react";
import { useWindowManager } from "@/lib/windowManager";
import { useAttendanceRiskAgent } from "./AttendanceRiskAgentWindow";
import { useTimetableAgent } from "./TimetableAgentWindow";
import { useGPAAgent } from "./GPAAgentWindow";
import { useDeadlineAgent } from "./DeadlineAgentWindow";
import { usePlacementAgent } from "./PlacementAgentWindow";
import { useChatAgent } from "./ChatAgentWindow";
import { useEmailAgent } from "./EmailAgentWindow";

// ─── Component ───────────────────────────────────────────────────────────────

export default function CommandPalette() {
  const [input, setInput] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [processing, setProcessing] = useState(false);
  const { spawnWindow } = useWindowManager();
  const { spawn: spawnAttendance } = useAttendanceRiskAgent();
  const { spawn: spawnTimetable } = useTimetableAgent();
  const { spawn: spawnGPA } = useGPAAgent();
  const { spawn: spawnDeadlines } = useDeadlineAgent();
  const { spawn: spawnPlacements } = usePlacementAgent();
  const { spawn: spawnChat } = useChatAgent();
  const { spawn: spawnEmail } = useEmailAgent();

  const handleSubmit = async () => {
    const text = input.trim();
    if (!text || processing) return;

    setInput("");
    setProcessing(true);

    try {
      // Single API call — gets both the classification AND the response
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: "command_palette" }),
      });

      if (!res.ok) {
        spawnChat(text);
        setProcessing(false);
        return;
      }

      const data = await res.json();
      const intent = data.intent || "general";
      const response = data.response || "";

      // Route based on the intent returned by the backend
      // Use workflow_plan.agent for precise routing when available
      const planAgent = data.workflow_plan?.agent || "";

      switch (intent) {
        case "attendance_risk":
          spawnAttendance();
          break;
        case "academic":
          if (planAgent === "gpa_projection") {
            spawnGPA();
          } else {
            _spawnResponseWindow(response, "Academic Agent", "📊");
          }
          break;
        case "connector":
          // Route based on the exact agent from the planner, not regex on sub_intent
          if (planAgent === "timetable") {
            spawnTimetable("today");
          } else if (planAgent === "deadlines") {
            spawnDeadlines();
          } else if (planAgent === "placements") {
            spawnPlacements();
          } else if (planAgent === "email") {
            spawnEmail();
          } else if (planAgent === "calendar") {
            _spawnResponseWindow(response, "Calendar", "📅");
          } else if (planAgent === "whatsapp") {
            _spawnResponseWindow(response, "Messages", "💬");
          } else {
            _spawnResponseWindow(response, "Info", "🔗");
          }
          break;
        case "action":
          _spawnResponseWindow(response, "Action Agent", "⚡");
          break;
        case "schedule":
          _spawnResponseWindow(response, "Schedule Agent", "📅");
          break;
        case "general":
        default:
          // Open a chat window with the response already shown
          _spawnResponseWindow(response, "Chat", "💬");
          break;
      }
    } catch {
      spawnChat(text);
    }

    setProcessing(false);
  };

  const _spawnResponseWindow = (response: string, agentName: string, icon: string) => {
    spawnWindow(
      agentName,
      "Response",
      <div className="text-[11px] text-foreground whitespace-pre-wrap leading-relaxed">
        {response}
      </div>,
      {
        agentIcon: icon,
        size: { width: 380, height: 300 },
        position: { x: 180, y: 100 },
      }
    );
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
