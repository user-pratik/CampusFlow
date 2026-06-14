"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { PanelType } from "@/lib/types";
import AttendancePanel from "./panels/AttendancePanel";
import MarksPanel from "./panels/MarksPanel";
import WhatsAppPanel from "./panels/WhatsAppPanel";
import EmailPanel from "./panels/EmailPanel";
import CalendarPanel from "./panels/CalendarPanel";
import TimetablePanel from "./panels/TimetablePanel";
import GroupsPanel from "./panels/GroupsPanel";

interface PanelOverlayProps {
  type: PanelType;
  data: Record<string, unknown>;
  onClose: () => void;
}

const PANEL_TITLES: Record<string, string> = {
  attendance: "Attendance",
  marks: "Marks",
  whatsapp: "WhatsApp",
  email: "Email",
  calendar: "Calendar",
  timetable: "Timetable",
  groups: "Groups",
};

export default function PanelOverlay({ type, data, onClose }: PanelOverlayProps) {
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
    <AnimatePresence>
      {type && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-30 bg-black/20 backdrop-blur-sm"
          />

          {/* Panel */}
          <motion.aside
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed top-0 right-0 z-40 h-full w-full max-w-[420px] flex flex-col border-l border-[var(--border-glass)] bg-[var(--bg-surface)] backdrop-blur-xl saturate-[1.8] shadow-[0_0_0_1px_var(--border-glass)]"
          >
            {/* Header */}
            <div className="h-14 flex items-center justify-between px-5 border-b border-[var(--border-glass)] shrink-0">
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                {type ? PANEL_TITLES[type] || type : ""}
              </h2>
              <button
                onClick={onClose}
                className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-glass)] transition-colors"
                aria-label="Close panel"
              >
                <X size={18} />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-5">
              {type && panels[type]}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
