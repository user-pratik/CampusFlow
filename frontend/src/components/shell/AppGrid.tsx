"use client";

import { useEmailAgent } from "./EmailAgentWindow";
import { useWhatsAppAgent } from "./WhatsAppAgentWindow";
import { useGPAAgent } from "./GPAAgentWindow";
import { useTimetableAgent } from "./TimetableAgentWindow";
import { useAttendanceRiskAgent } from "./AttendanceRiskAgentWindow";
import { useChatAgent } from "./ChatAgentWindow";

interface AppGridProps {
  isOpen: boolean;
  onClose: () => void;
  onSyncClick: () => void;
}

interface AppEntry {
  name: string;
  icon: React.ReactNode;
  action: () => void;
}

/** Get gradient classes for each app's icon background */
function getAppGradient(name: string): string {
  switch (name) {
    case "Chat": return "bg-gradient-to-br from-blue-400 to-blue-600";
    case "Gmail": return "bg-white";
    case "WhatsApp": return "bg-white";
    case "Schedule": return "bg-gradient-to-br from-orange-400 to-orange-600";
    case "Attendance": return "bg-gradient-to-br from-purple-400 to-purple-600";
    case "GPA Estimator": return "bg-gradient-to-br from-yellow-400 to-amber-600";
    case "Sync VTOP": return "bg-gradient-to-br from-teal-400 to-cyan-600";
    default: return "bg-gradient-to-br from-zinc-600 to-zinc-800";
  }
}

export default function AppGrid({ isOpen, onClose, onSyncClick }: AppGridProps) {
  const { spawn: spawnEmail } = useEmailAgent();
  const { spawn: spawnWhatsApp } = useWhatsAppAgent();
  const { spawn: spawnGPA } = useGPAAgent();
  const { spawn: spawnTimetable } = useTimetableAgent();
  const { checkAndSpawn: spawnAttendance } = useAttendanceRiskAgent();
  const { autoSpawn: spawnChat } = useChatAgent();

  if (!isOpen) return null;

  const apps: AppEntry[] = [
    {
      name: "Chat",
      icon: (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="https://api.iconify.design/mdi/chat.svg?color=white" alt="Chat" className="w-10 h-10 object-contain" />
      ),
      action: spawnChat,
    },
    {
      name: "Gmail",
      icon: (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="https://api.iconify.design/logos/google-gmail.svg" alt="Gmail" className="w-12 h-12 object-contain" />
      ),
      action: spawnEmail,
    },
    {
      name: "WhatsApp",
      icon: (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="https://api.iconify.design/logos/whatsapp-icon.svg" alt="WhatsApp" className="w-12 h-12 object-contain" />
      ),
      action: spawnWhatsApp,
    },
    {
      name: "Schedule",
      icon: (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="https://api.iconify.design/mdi/calendar-today.svg?color=white" alt="Schedule" className="w-10 h-10 object-contain" />
      ),
      action: () => spawnTimetable("today"),
    },
    {
      name: "Attendance",
      icon: (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="https://api.iconify.design/mdi/clipboard-check.svg?color=white" alt="Attendance" className="w-10 h-10 object-contain" />
      ),
      action: spawnAttendance,
    },
    {
      name: "GPA Estimator",
      icon: (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="https://api.iconify.design/mdi/calculator.svg?color=white" alt="GPA Estimator" className="w-10 h-10 object-contain" />
      ),
      action: spawnGPA,
    },
    {
      name: "Sync VTOP",
      icon: (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="https://api.iconify.design/mdi/sync.svg?color=white" alt="Sync" className="w-10 h-10 object-contain" />
      ),
      action: onSyncClick,
    },
  ];

  return (
    <div
      className="fixed inset-0 z-40 bg-zinc-950/80 backdrop-blur-md flex flex-col items-center justify-center pt-10"
      onClick={onClose}
    >
      <div
        className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-8 p-8"
        onClick={(e) => e.stopPropagation()}
      >
        {apps.map((app) => (
          <button
            key={app.name}
            onClick={() => {
              app.action();
              onClose();
            }}
            className="flex flex-col items-center p-4 rounded-2xl hover:scale-105 transition-transform duration-200 group"
            title={app.name}
          >
            <div className={`w-20 h-20 rounded-3xl flex items-center justify-center shadow-lg drop-shadow-md ${getAppGradient(app.name)}`}>
              <span className="text-white">
                {app.icon}
              </span>
            </div>
            <span className="text-white text-sm font-medium mt-3 drop-shadow-md">
              {app.name}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
