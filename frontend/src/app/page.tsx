"use client";

import { useState, useEffect } from "react";
import SetupFlow from "@/components/SetupFlow";
import Sidebar from "@/components/Sidebar";
import ChatPanel from "@/components/ChatPanel";
import ContextPanel from "@/components/ContextPanel";
import { PanelType } from "@/lib/types";

export default function Home() {
  const [setupDone, setSetupDone] = useState(false);
  const [activePanel, setActivePanel] = useState<PanelType>(null);
  const [panelData, setPanelData] = useState<Record<string, unknown>>({});

  // Check if setup was already completed (persisted across sessions)
  useEffect(() => {
    const done = localStorage.getItem("campusflow-setup-done");
    if (done === "true") setSetupDone(true);
  }, []);

  const handleSetupComplete = () => {
    setSetupDone(true);
    localStorage.setItem("campusflow-setup-done", "true");
  };

  const openPanel = (type: PanelType, data?: Record<string, unknown>) => {
    setActivePanel(type);
    if (data) setPanelData(data);
  };

  const closePanel = () => {
    setActivePanel(null);
    setPanelData({});
  };

  if (!setupDone) {
    return <SetupFlow onComplete={handleSetupComplete} />;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar openPanel={openPanel} activePanel={activePanel} />
      <ChatPanel openPanel={openPanel} />
      {activePanel && (
        <ContextPanel
          type={activePanel}
          data={panelData}
          onClose={closePanel}
        />
      )}
    </div>
  );
}
