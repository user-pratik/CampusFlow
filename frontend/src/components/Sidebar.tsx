"use client";

import { useEffect, useState } from "react";
import { useTheme } from "./ThemeProvider";
import { PanelType } from "@/lib/types";
import { fetchProfile, fetchAcademicProfile, fetchServiceStatus, checkSessionStatus, triggerVtopSyncNew, type Profile, type AcademicProfileData, type ServiceStatus } from "@/lib/api";
import VTOPLoginModal from "./VTOPLoginModal";
import SemesterSelector from "./SemesterSelector";

interface SidebarProps {
  openPanel: (type: PanelType, data?: Record<string, unknown>) => void;
  activePanel: PanelType;
}

export default function Sidebar({ openPanel, activePanel }: SidebarProps) {
  const { theme, toggle } = useTheme();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [academic, setAcademic] = useState<AcademicProfileData | null>(null);
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showSemesterSelector, setShowSemesterSelector] = useState(false);

  useEffect(() => {
    fetchProfile().then(setProfile).catch(() => {});
    fetchAcademicProfile().then(setAcademic).catch(() => {});
    fetchServiceStatus().then(setStatus).catch(() => {});
  }, []);

  // Refresh status periodically
  useEffect(() => {
    const interval = setInterval(() => {
      fetchServiceStatus().then(setStatus).catch(() => {});
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const sessionStatus = await checkSessionStatus();
      if (sessionStatus.status === "valid") {
        setShowSemesterSelector(true);
      } else {
        setShowLoginModal(true);
      }
    } catch {
      setSyncResult("✗ Offline");
      setSyncing(false);
      setTimeout(() => setSyncResult(null), 4000);
    }
  };

  const handleLoginSuccess = () => {
    setShowLoginModal(false);
    setShowSemesterSelector(true);
  };

  const handleSemesterConfirm = async (semesterId: string) => {
    setShowSemesterSelector(false);
    try {
      await triggerVtopSyncNew(semesterId);
      setSyncResult("✓ Synced");
      fetchAcademicProfile().then(setAcademic).catch(() => {});
    } catch {
      setSyncResult("✗ Failed");
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncResult(null), 4000);
    }
  };

  const navItems: { id: PanelType; icon: string; label: string }[] = [
    { id: "attendance", icon: "📊", label: "Attendance" },
    { id: "marks", icon: "📝", label: "Marks" },
    { id: "whatsapp", icon: "💬", label: "WhatsApp" },
    { id: "email", icon: "📧", label: "Email" },
    { id: "calendar", icon: "📅", label: "Calendar" },
    { id: "timetable", icon: "🕐", label: "Timetable" },
    { id: "groups", icon: "👥", label: "Groups" },
  ];

  return (
    <aside className="w-16 md:w-56 flex flex-col border-r border-border bg-panel-bg shrink-0">
      {/* Logo / Profile */}
      <div className="p-3 md:p-4 border-b border-border">
        <div className="hidden md:block">
          <p className="font-display text-lg font-semibold text-foreground">
            CampusFlow
          </p>
          <p className="text-xs text-secondary mt-1 truncate">
            {profile?.name || "Loading..."} &middot; {profile?.reg_no || ""}
          </p>
        </div>
        <div className="md:hidden flex justify-center">
          <span className="text-xl">🎓</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => openPanel(item.id)}
            className={`w-full flex items-center gap-3 px-3 md:px-4 py-2.5 text-left transition-colors ${
              activePanel === item.id
                ? "bg-accent-light text-accent"
                : "text-secondary hover:text-foreground hover:bg-surface"
            }`}
          >
            <span className="text-base shrink-0">{item.icon}</span>
            <span className="hidden md:inline text-sm font-medium">
              {item.label}
            </span>
          </button>
        ))}
      </nav>

      {/* Bottom: Sync + Theme toggle + CGPA */}
      <div className="border-t border-border p-3 md:p-4 space-y-3">
        {/* Service status indicators */}
        <div className="hidden md:flex items-center gap-2 text-[10px]">
          <span
            className={`w-2 h-2 rounded-full ${status?.vtop?.session_valid ? "bg-success" : "bg-urgent"}`}
            title={status?.vtop?.session_valid ? "VTOP session active" : "VTOP session expired"}
          />
          <span className="text-secondary">VTOP</span>
          <span
            className={`w-2 h-2 rounded-full ml-2 ${status?.whatsapp?.connected ? "bg-success" : "bg-yellow-500"}`}
            title={status?.whatsapp?.connected ? "WhatsApp connected" : `WhatsApp: ${status?.whatsapp?.state || "offline"}`}
          />
          <span className="text-secondary">WA</span>
          <span
            className={`w-2 h-2 rounded-full ml-2 ${status?.ngrok?.active ? "bg-success" : "bg-urgent"}`}
            title={status?.ngrok?.active ? `ngrok: ${status.ngrok.url}` : "ngrok inactive"}
          />
          <span className="text-secondary">ngrok</span>
        </div>

        {/* Sync button */}
        <button
          onClick={handleSync}
          disabled={syncing}
          className={`w-full flex items-center justify-center md:justify-start gap-2 py-2 px-3 text-xs font-medium rounded transition-colors ${
            syncing
              ? "bg-accent/20 text-accent cursor-wait"
              : syncResult
              ? syncResult.includes("✓")
                ? "bg-success/10 text-success"
                : syncResult.includes("🌐") || syncResult.includes("⚠")
                ? "bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400"
                : "bg-urgent/10 text-urgent"
              : "bg-accent-light text-accent hover:bg-accent/20"
          }`}
          title="Sync everything: VTOP login + data sync + WhatsApp QR"
        >
          <span className={syncing ? "animate-spin" : ""}>
            {syncing ? "↻" : syncResult ? "" : "🔄"}
          </span>
          <span className="hidden md:inline">
            {syncing ? "Syncing VTOP..." : syncResult || "Sync Now"}
          </span>
        </button>

        <div className="hidden md:flex items-center justify-between">
          <span className="text-xs text-secondary">CGPA</span>
          <span className="text-sm font-semibold text-foreground">
            {academic?.cgpa?.toFixed(2) || "—"}
          </span>
        </div>
        <button
          onClick={toggle}
          className="w-full flex items-center justify-center md:justify-start gap-2 py-2 px-3 text-xs text-secondary hover:text-foreground transition-colors rounded"
          aria-label="Toggle theme"
        >
          <span>{theme === "dark" ? "☀️" : "🌙"}</span>
          <span className="hidden md:inline">
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </span>
        </button>
      </div>

      {showLoginModal && (
        <VTOPLoginModal
          onClose={() => { setShowLoginModal(false); setSyncing(false); }}
          onLoginSuccess={handleLoginSuccess}
        />
      )}
      {showSemesterSelector && (
        <SemesterSelector
          onClose={() => { setShowSemesterSelector(false); setSyncing(false); }}
          onConfirm={handleSemesterConfirm}
        />
      )}
    </aside>
  );
}
