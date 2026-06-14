"use client";

import { useRef } from "react";
import { motion, useMotionValue, useTransform, useSpring } from "framer-motion";
import { PanelType } from "@/lib/types";
import {
  BarChart2,
  FileText,
  Mail,
  Calendar,
  MessageCircle,
  Clock,
  Users,
  RefreshCw,
  Sun,
  Moon,
} from "lucide-react";
import { useTheme } from "./ThemeProvider";

interface DockItem {
  id: PanelType;
  icon: React.ReactNode;
  label: string;
}

interface FloatingDockProps {
  activePanel: PanelType;
  openPanel: (type: PanelType) => void;
  onSync: () => void;
  syncing: boolean;
}

const DOCK_ITEMS: DockItem[] = [
  { id: "attendance", icon: <BarChart2 size={22} />, label: "Attendance" },
  { id: "marks", icon: <FileText size={22} />, label: "Marks" },
  { id: "email", icon: <Mail size={22} />, label: "Email" },
  { id: "calendar", icon: <Calendar size={22} />, label: "Calendar" },
  { id: "whatsapp", icon: <MessageCircle size={22} />, label: "WhatsApp" },
  { id: "timetable", icon: <Clock size={22} />, label: "Timetable" },
  { id: "groups", icon: <Users size={22} />, label: "Groups" },
];

function DockIcon({
  item,
  isActive,
  mouseX,
  onClick,
}: {
  item: DockItem;
  isActive: boolean;
  mouseX: any;
  onClick: () => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);

  const distance = useTransform(mouseX, (val: number) => {
    const bounds = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 };
    return val - bounds.x - bounds.width / 2;
  });

  const widthSync = useTransform(distance, [-150, 0, 150], [44, 58, 44]);
  const width = useSpring(widthSync, { mass: 0.1, stiffness: 150, damping: 12 });

  return (
    <motion.button
      ref={ref}
      style={{ width, height: width }}
      onClick={onClick}
      className={`relative flex items-center justify-center rounded-xl transition-colors ${
        isActive
          ? "bg-accent/20 text-accent"
          : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-glass)]"
      }`}
      title={item.label}
      whileTap={{ scale: 0.9 }}
    >
      {item.icon}
      {isActive && (
        <span className="absolute -bottom-1.5 w-1 h-1 rounded-full bg-accent" />
      )}
    </motion.button>
  );
}

export default function FloatingDock({ activePanel, openPanel, onSync, syncing }: FloatingDockProps) {
  const mouseX = useMotionValue(Infinity);
  const { theme, toggle } = useTheme();

  return (
    <motion.div
      onMouseMove={(e) => mouseX.set(e.pageX)}
      onMouseLeave={() => mouseX.set(Infinity)}
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-end gap-1 px-3 py-2 rounded-2xl border border-[var(--border-glass)] bg-[var(--dock-bg)] backdrop-blur-xl shadow-lg"
    >
      {DOCK_ITEMS.map((item) => (
        <DockIcon
          key={item.id}
          item={item}
          isActive={activePanel === item.id}
          mouseX={mouseX}
          onClick={() => openPanel(item.id!)}
        />
      ))}

      {/* Divider */}
      <div className="w-px h-8 bg-[var(--border-glass)] mx-1 self-center" />

      {/* Sync button */}
      <motion.button
        onClick={onSync}
        disabled={syncing}
        className="flex items-center justify-center w-11 h-11 rounded-xl text-[var(--text-muted)] hover:text-accent hover:bg-[var(--bg-glass)] transition-colors disabled:opacity-50"
        title="Sync VTOP"
        whileTap={{ scale: 0.9 }}
      >
        <RefreshCw size={20} className={syncing ? "animate-spin" : ""} />
      </motion.button>

      {/* Theme toggle */}
      <motion.button
        onClick={toggle}
        className="flex items-center justify-center w-11 h-11 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-glass)] transition-colors"
        title={theme === "dark" ? "Light mode" : "Dark mode"}
        whileTap={{ scale: 0.9 }}
      >
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </motion.button>
    </motion.div>
  );
}
