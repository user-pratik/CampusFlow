"use client";

import { useState, useEffect } from "react";
import SetupFlow from "@/components/SetupFlow";
import { AgentShell } from "@/components/shell";

export default function Home() {
  const [setupDone, setSetupDone] = useState(false);

  // Check if setup was already completed (persisted across sessions)
  useEffect(() => {
    const done = localStorage.getItem("campusflow-setup-done");
    if (done === "true") setSetupDone(true);
  }, []);

  const handleSetupComplete = () => {
    setSetupDone(true);
    localStorage.setItem("campusflow-setup-done", "true");
  };

  if (!setupDone) {
    return <SetupFlow onComplete={handleSetupComplete} />;
  }

  return <AgentShell />;
}
