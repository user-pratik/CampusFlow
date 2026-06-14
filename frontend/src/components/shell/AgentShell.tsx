"use client";

import { useCallback, useEffect, useState } from "react";
import { WindowManagerProvider, useWindowManager } from "@/lib/windowManager";
import TopBar from "./TopBar";
import Desktop from "./Desktop";
import { useTimetableAgent } from "./TimetableAgentWindow";
import { useAttendanceRiskAgent } from "./AttendanceRiskAgentWindow";
import { useNotificationCenter } from "./NotificationCenter";
import { useEmailAgent } from "./EmailAgentWindow";
import { useGPAAgent } from "./GPAAgentWindow";
import { useWhatsAppAgent } from "./WhatsAppAgentWindow";
import { useChatAgent } from "./ChatAgentWindow";

const MOCK_AGENT_COUNT = 3;

function SyncWindowContent({ onComplete }: { onComplete: (status: "done" | "error") => void }) {
  const [step, setStep] = useState<"checking" | "login" | "semester" | "syncing" | "done" | "error">("checking");
  const [semesters, setSemesters] = useState<Record<string, string>>({});
  const [selectedSem, setSelectedSem] = useState("");
  const [result, setResult] = useState<string>("");

  async function fetchSemesters(): Promise<boolean> {
    try {
      const res = await fetch("/api/vtop/semesters", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        const sems = data.semesters || {};
        setSemesters(sems);
        return Object.keys(sems).length > 0;
      }
    } catch {
      // fall through
    }
    return false;
  }

  // Step 1: Check session then fetch semesters
  useEffect(() => {
    async function check() {
      try {
        const res = await fetch("/api/vtop/session-status", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          if (data.status === "valid") {
            // Session valid — now fetch semesters
            const hasSemesters = await fetchSemesters();
            if (hasSemesters) {
              setStep("semester");
            } else {
              setStep("error");
              setResult("Session valid but no semesters returned. VTOP may be down or session expired mid-request.");
              onComplete("error");
            }
          } else {
            setStep("login");
          }
        } else {
          setStep("login");
        }
      } catch {
        setStep("error");
        setResult("Cannot reach backend — is it running?");
        onComplete("error");
      }
    }
    check();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSync() {
    if (!selectedSem) return;
    setStep("syncing");
    try {
      const res = await fetch("/api/vtop/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ semester_id: selectedSem }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "session_expired") {
          setResult("Session expired during sync — please log in again.");
          setStep("error");
          onComplete("error");
        } else {
          setResult(`✓ Synced: ${data.attendance_count || 0} attendance, ${data.marks_count || 0} marks, ${data.timetable_count || 0} timetable slots`);
          setStep("done");
          onComplete("done");
        }
      } else {
        setResult("Sync failed — server error");
        setStep("error");
        onComplete("error");
      }
    } catch {
      setResult("Network error");
      setStep("error");
      onComplete("error");
    }
  }

  return (
    <div className="space-y-3">
      {step === "checking" && (
        <div className="flex items-center gap-2 text-xs text-secondary">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          Checking VTOP session...
        </div>
      )}

      {step === "login" && (
        <div className="space-y-2">
          <p className="text-xs text-foreground font-medium">⚠️ VTOP session expired or not set</p>
          <p className="text-[11px] text-secondary">
            Click below to open the VTOP login browser. Complete the login + reCAPTCHA, then click Retry.
          </p>
          <div className="flex gap-2">
            <button
              onClick={async () => {
                try {
                  await fetch("/api/vtop/launch-login", { method: "POST" });
                } catch { /* silent */ }
              }}
              className="text-xs px-3 py-1.5 bg-accent text-white rounded-md hover:opacity-90"
            >
              Open VTOP Login
            </button>
            <button
              onClick={async () => {
                setStep("checking");
                // Try to store session from file first
                try {
                  await fetch("/api/vtop/store-session", { method: "POST" });
                } catch { /* silent */ }
                // Then check if we have a valid session now
                try {
                  const res = await fetch("/api/vtop/session-status", { cache: "no-store" });
                  if (res.ok) {
                    const data = await res.json();
                    if (data.status === "valid") {
                      const hasSems = await fetchSemesters();
                      setStep(hasSems ? "semester" : "login");
                    } else {
                      setStep("login");
                    }
                  } else {
                    setStep("login");
                  }
                } catch {
                  setStep("login");
                }
              }}
              className="text-xs px-3 py-1.5 border border-border text-secondary rounded-md hover:bg-surface"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {step === "semester" && (
        <div className="space-y-2">
          <p className="text-xs text-foreground font-medium">✓ Session active — select semester:</p>
          <select
            value={selectedSem}
            onChange={(e) => setSelectedSem(e.target.value)}
            className="w-full text-xs bg-surface border border-border rounded-md px-2.5 py-1.5 text-foreground outline-none"
          >
            <option value="">Choose semester...</option>
            {Object.entries(semesters).map(([name, id]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
          <button
            onClick={handleSync}
            disabled={!selectedSem}
            className="w-full text-xs px-3 py-2 bg-accent text-white rounded-md disabled:opacity-40"
          >
            Sync Now
          </button>
        </div>
      )}

      {step === "syncing" && (
        <div className="flex items-center gap-2 text-xs text-secondary">
          <span className="animate-spin">↻</span>
          Syncing attendance, marks, timetable...
        </div>
      )}

      {(step === "done" || step === "error") && (
        <div className={`text-xs space-y-2 ${step === "done" ? "text-success" : "text-urgent"}`}>
          <p>{result}</p>
          {step === "error" && (
            <button
              onClick={() => setStep("login")}
              className="text-xs px-3 py-1.5 border border-border text-secondary rounded-md hover:bg-surface"
            >
              Try Again
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function AgentShellInner() {
  const { spawnWindow } = useWindowManager();
  const [hasSpawnedDemo, setHasSpawnedDemo] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "done" | "error">("idle");
  const { autoSpawn: autoSpawnTimetable } = useTimetableAgent();
  const { checkAndSpawn: checkAttendanceRisk } = useAttendanceRiskAgent();
  const { unreadCount, openNotificationCenter } = useNotificationCenter();
  const { spawn: spawnEmail } = useEmailAgent();
  const { spawn: spawnGPA } = useGPAAgent();
  const { spawn: spawnWhatsApp } = useWhatsAppAgent();
  const { autoSpawn: autoSpawnChat } = useChatAgent();

  // Spawn Chat window immediately on app load (pinned, bottom-right)
  useEffect(() => {
    const timer = setTimeout(() => {
      autoSpawnChat();
    }, 300);
    return () => clearTimeout(timer);
  }, [autoSpawnChat]);

  // Spawn Timetable Agent window on app load
  useEffect(() => {
    const timer = setTimeout(() => {
      autoSpawnTimetable();
    }, 600);
    return () => clearTimeout(timer);
  }, [autoSpawnTimetable]);

  // Attendance Risk Agent: check on load and spawn if warning/critical found
  useEffect(() => {
    const timer = setTimeout(() => {
      checkAttendanceRisk();
    }, 1800);
    return () => clearTimeout(timer);
  }, [checkAttendanceRisk]);

  const handleSyncClick = useCallback(() => {
    setSyncStatus("syncing");
    spawnWindow(
      "System",
      "Sync VTOP",
      <SyncWindowContent onComplete={(status) => {
        setSyncStatus(status);
        // Reset to idle after 4s
        setTimeout(() => setSyncStatus("idle"), 4000);
      }} />,
      {
        agentIcon: "🔄",
        size: { width: 340, height: 220 },
        position: { x: 500, y: 40 },
      }
    );
  }, [spawnWindow]);

  // Spawn demo windows on mount (mock data for shell demonstration)
  useEffect(() => {
    if (hasSpawnedDemo) return;
    setHasSpawnedDemo(true);

    // Simulate agents spawning windows with staggered timing
    const timers: NodeJS.Timeout[] = [];

    timers.push(
      setTimeout(() => {
        spawnWindow(
          "Deadline Agent",
          "2 New Deadlines",
          <div className="space-y-3">
            <div className="p-2 rounded-md bg-surface border border-border">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">CAT-1 Exam: BCSE302L</span>
                <span className="text-[10px] px-1.5 py-0.5 bg-urgent/10 text-urgent rounded">2 days</span>
              </div>
              <p className="text-xs text-secondary mt-1">Data Structures — Slot A1</p>
            </div>
            <div className="p-2 rounded-md bg-surface border border-border">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Assignment: BECE301L</span>
                <span className="text-[10px] px-1.5 py-0.5 bg-conflict text-foreground rounded">5 days</span>
              </div>
              <p className="text-xs text-secondary mt-1">Digital Logic Design — Upload PDF</p>
            </div>
            <p className="text-xs text-secondary italic mt-2">
              📌 Pin this window to keep deadlines visible
            </p>
          </div>,
          { position: { x: 60, y: 60 }, size: { width: 380, height: 280 } }
        );
      }, 800)
    );

    timers.push(
      setTimeout(() => {
        spawnWindow(
          "Academic Agent",
          "Attendance Alert",
          <div className="space-y-3">
            <div className="flex items-center gap-2 p-2 rounded-md bg-urgent/5 border border-urgent/20">
              <span className="text-lg">⚠️</span>
              <div>
                <p className="text-sm font-medium text-urgent">BECE301L — 73%</p>
                <p className="text-xs text-secondary">
                  Below 75% threshold. You need 4 consecutive classes to recover.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-md bg-surface border border-border">
              <span className="text-lg">✅</span>
              <div>
                <p className="text-sm font-medium text-success">BCSE302L — 91%</p>
                <p className="text-xs text-secondary">Healthy. Can skip 3 more classes safely.</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-md bg-surface border border-border">
              <span className="text-lg">✅</span>
              <div>
                <p className="text-sm font-medium text-success">BCSE303L — 88%</p>
                <p className="text-xs text-secondary">On track.</p>
              </div>
            </div>
          </div>,
          { position: { x: 480, y: 80 }, size: { width: 380, height: 310 } }
        );
      }, 1500)
    );

    timers.push(
      setTimeout(() => {
        spawnWindow(
          "Notice Agent",
          "Campus Notice",
          <div className="space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] px-1.5 py-0.5 bg-accent-light text-accent rounded font-medium">
                Academic
              </span>
              <span className="text-[10px] text-secondary">from VIT Official Group</span>
            </div>
            <p className="text-sm text-foreground">
              Mid-semester examination schedule has been released for Winter 2025-26. 
              Check VTOP for your individual timetable.
            </p>
            <div className="flex gap-2 mt-3">
              <button className="text-xs px-3 py-1.5 bg-accent text-white rounded-md hover:opacity-90 transition-opacity">
                View Schedule
              </button>
              <button className="text-xs px-3 py-1.5 border border-border text-secondary rounded-md hover:bg-surface transition-colors">
                Dismiss
              </button>
            </div>
          </div>,
          { position: { x: 200, y: 350 }, size: { width: 360, height: 230 } }
        );
      }, 2400)
    );

    return () => timers.forEach(clearTimeout);
  }, [hasSpawnedDemo, spawnWindow]);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopBar
        agentCount={MOCK_AGENT_COUNT}
        notificationCount={unreadCount}
        onNotificationClick={openNotificationCenter}
        onSyncClick={handleSyncClick}
        syncStatus={syncStatus}
        onLaunchEmail={spawnEmail}
        onLaunchWhatsApp={spawnWhatsApp}
        onLaunchMarks={spawnGPA}
      />
      <Desktop />
    </div>
  );
}

export default function AgentShell() {
  return (
    <WindowManagerProvider>
      <AgentShellInner />
    </WindowManagerProvider>
  );
}
