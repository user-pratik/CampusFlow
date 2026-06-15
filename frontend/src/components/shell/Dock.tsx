"use client";

import { useWindowManager } from "@/lib/windowManager";
import { useEmailAgent } from "./EmailAgentWindow";
import { useWhatsAppAgent } from "./WhatsAppAgentWindow";
import { useGPAAgent } from "./GPAAgentWindow";

/** Get gradient background for a minimized agent based on its name */
function getAgentGradient(agentName: string): string {
  const lower = agentName.toLowerCase();
  if (lower.includes("chat") || lower.includes("campusflow")) return "bg-gradient-to-br from-blue-400 to-blue-600";
  if (lower.includes("schedule") || lower.includes("timetable") || lower.includes("calendar")) return "bg-gradient-to-br from-orange-400 to-orange-600";
  if (lower.includes("attendance") || lower.includes("academic")) return "bg-gradient-to-br from-purple-400 to-purple-600";
  if (lower.includes("email") || lower.includes("mail")) return "bg-white";
  if (lower.includes("whatsapp") || lower.includes("message")) return "bg-white";
  if (lower.includes("gpa") || lower.includes("marks") || lower.includes("grade")) return "bg-gradient-to-br from-yellow-400 to-amber-600";
  if (lower.includes("deadline") || lower.includes("notice")) return "bg-gradient-to-br from-pink-400 to-rose-600";
  if (lower.includes("sync") || lower.includes("system")) return "bg-gradient-to-br from-teal-400 to-cyan-600";
  return "bg-gradient-to-br from-zinc-500 to-zinc-700";
}

/** Get icon for a minimized agent (dock size) */
function getAgentIcon(agentName: string, fallbackIcon: string): React.ReactNode {
  const lower = agentName.toLowerCase();
  /* eslint-disable @next/next/no-img-element */
  if (lower.includes("chat") || lower.includes("campusflow")) {
    return <img src="https://api.iconify.design/mdi/chat.svg?color=white" alt="Chat" className="w-7 h-7 object-contain" />;
  }
  if (lower.includes("schedule") || lower.includes("timetable") || lower.includes("calendar")) {
    return <img src="https://api.iconify.design/mdi/calendar-today.svg?color=white" alt="Schedule" className="w-7 h-7 object-contain" />;
  }
  if (lower.includes("attendance") || lower.includes("academic")) {
    return <img src="https://api.iconify.design/mdi/clipboard-check.svg?color=white" alt="Attendance" className="w-7 h-7 object-contain" />;
  }
  if (lower.includes("gpa") || lower.includes("marks") || lower.includes("grade")) {
    return <img src="https://api.iconify.design/mdi/calculator.svg?color=white" alt="GPA" className="w-7 h-7 object-contain" />;
  }
  if (lower.includes("email") || lower.includes("mail")) {
    return <img src="https://api.iconify.design/logos/google-gmail.svg" alt="Gmail" className="w-8 h-8 object-contain" />;
  }
  if (lower.includes("whatsapp") || lower.includes("message")) {
    return <img src="https://api.iconify.design/logos/whatsapp-icon.svg" alt="WhatsApp" className="w-8 h-8 object-contain" />;
  }
  if (lower.includes("sync") || lower.includes("system")) {
    return <img src="https://api.iconify.design/mdi/sync.svg?color=white" alt="Sync" className="w-7 h-7 object-contain" />;
  }
  if (lower.includes("deadline") || lower.includes("notice")) {
    return <img src="https://api.iconify.design/mdi/clock-alert.svg?color=white" alt="Deadline" className="w-7 h-7 object-contain" />;
  }
  /* eslint-enable @next/next/no-img-element */
  return <span className="text-lg">{fallbackIcon}</span>;
}

export default function Dock({ onToggleAppGrid }: { onToggleAppGrid?: () => void }) {
  const { windows, restoreWindow, closeWindow, activeWindowId } = useWindowManager();
  const { spawn: spawnEmail } = useEmailAgent();
  const { spawn: spawnWhatsApp } = useWhatsAppAgent();
  const { spawn: spawnGPA } = useGPAAgent();

  const minimizedWindows = windows.filter((w) => w.state === "minimized");

  return (
    <div className="fixed left-0 top-0 h-full w-4 hover:w-20 z-9999 group flex flex-col justify-center items-start">
      <div className="flex flex-col items-center gap-2 px-2 py-3 rounded-2xl bg-zinc-900/80 backdrop-blur-xl border border-white/10 shadow-2xl -translate-x-full group-hover:translate-x-2 transition-transform duration-300 ease-out">
        {/* Pinned app: Gmail */}
        <button
          onClick={spawnEmail}
          className="group/icon relative flex flex-col items-center"
          title="Open Gmail"
        >
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-md drop-shadow transition-transform hover:scale-110 duration-200 bg-white">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="https://api.iconify.design/logos/google-gmail.svg" alt="Gmail" className="w-8 h-8 object-contain" />
          </div>
        </button>

        {/* Pinned app: WhatsApp */}
        <button
          onClick={spawnWhatsApp}
          className="group/icon relative flex flex-col items-center"
          title="Open WhatsApp"
        >
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-md drop-shadow transition-transform hover:scale-110 duration-200 bg-white">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="https://api.iconify.design/logos/whatsapp-icon.svg" alt="WhatsApp" className="w-8 h-8 object-contain" />
          </div>
        </button>

        {/* Pinned app: GPA Estimator */}
        <button
          onClick={spawnGPA}
          className="group/icon relative flex flex-col items-center"
          title="Open GPA Estimator"
        >
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-md drop-shadow transition-transform hover:scale-110 duration-200 bg-gradient-to-br from-yellow-400 to-amber-600">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="https://api.iconify.design/mdi/calculator.svg?color=white" alt="GPA" className="w-7 h-7 object-contain" />
          </div>
        </button>

        {/* Separator between pinned apps and minimized agents */}
        {minimizedWindows.length > 0 && (
          <div className="h-px w-8 bg-white/10 my-1" />
        )}

        {/* Minimized agent windows */}
        {minimizedWindows.map((win) => (
          <button
            key={win.id}
            onClick={() => restoreWindow(win.id)}
            onContextMenu={(e) => {
              e.preventDefault();
              closeWindow(win.id);
            }}
            className="group/icon relative flex flex-col items-center"
            title={`${win.title} — ${win.agentName}\nRight-click to close`}
          >
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-md drop-shadow transition-transform hover:scale-110 duration-200 ${getAgentGradient(win.agentName)}`}>
              {getAgentIcon(win.agentName, win.agentIcon)}
            </div>
            {/* Active indicator dot */}
            <span className="absolute -right-1 top-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-white/80" />
          </button>
        ))}

        {/* Separator */}
        <div className="h-px w-8 bg-white/10 my-1" />

        {/* App Grid button (Show Applications) — frosted glass style */}
        <button
          onClick={onToggleAppGrid}
          className="w-12 h-12 rounded-2xl flex items-center justify-center bg-white/10 hover:bg-white/20 border border-white/10 backdrop-blur-md transition-all"
          title="Show Applications"
        >
          <svg className="w-6 h-6 text-white/70" viewBox="0 0 24 24" fill="currentColor">
            <circle cx="5" cy="5" r="2" />
            <circle cx="12" cy="5" r="2" />
            <circle cx="19" cy="5" r="2" />
            <circle cx="5" cy="12" r="2" />
            <circle cx="12" cy="12" r="2" />
            <circle cx="19" cy="12" r="2" />
            <circle cx="5" cy="19" r="2" />
            <circle cx="12" cy="19" r="2" />
            <circle cx="19" cy="19" r="2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
