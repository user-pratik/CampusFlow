"use client";

import { PanelType } from "@/lib/types";
import AttendancePanel from "./panels/AttendancePanel";
import MarksPanel from "./panels/MarksPanel";
import WhatsAppPanel from "./panels/WhatsAppPanel";
import EmailPanel from "./panels/EmailPanel";
import CalendarPanel from "./panels/CalendarPanel";
import TimetablePanel from "./panels/TimetablePanel";
import GroupsPanel from "./panels/GroupsPanel";

interface ContextPanelProps {
  type: PanelType;
  data: Record<string, unknown>;
  onClose: () => void;
}

export default function ContextPanel({ type, data, onClose }: ContextPanelProps) {
  const panels: Record<string, React.ReactNode> = {
    attendance: <AttendancePanel data={data} />,
    marks: <MarksPanel data={data} />,
    whatsapp: <WhatsAppPanel data={data} />,
    email: <EmailPanel data={data} />,
    calendar: <CalendarPanel data={data} />,
    timetable: <TimetablePanel data={data} />,
    groups: <GroupsPanel data={data} />,
  };

  return (
    <aside className="w-80 lg:w-96 border-l border-border bg-panel-bg flex flex-col shrink-0 overflow-hidden">
      {/* Panel header */}
      <div className="h-14 border-b border-border flex items-center justify-between px-4 shrink-0">
        <h2 className="text-sm font-medium text-foreground capitalize">
          {type}
        </h2>
        <button
          onClick={onClose}
          className="text-secondary hover:text-foreground text-lg transition-colors"
          aria-label="Close panel"
        >
          ✕
        </button>
      </div>

      {/* Panel content */}
      <div className="flex-1 overflow-y-auto p-4">
        {type && panels[type]}
      </div>
    </aside>
  );
}
