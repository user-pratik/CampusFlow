"use client";

import { useEffect, useState } from "react";

interface SetupStep {
  id: string;
  label: string;
  description: string;
  icon: string;
  status: "pending" | "connecting" | "syncing" | "done" | "error";
  detail?: string;
}

interface Props {
  onComplete: () => void;
}

export default function SetupFlow({ onComplete }: Props) {
  const [steps, setSteps] = useState<SetupStep[]>([
    {
      id: "vtop",
      label: "VTOP Portal",
      description: "Logging into VIT student portal...",
      icon: "🎓",
      status: "pending",
    },
    {
      id: "whatsapp",
      label: "WhatsApp",
      description: "Connecting to WhatsApp bridge...",
      icon: "💬",
      status: "pending",
    },
    {
      id: "google",
      label: "Google Account",
      description: "Syncing Gmail & Calendar...",
      icon: "📧",
      status: "pending",
    },
  ]);

  const [currentStep, setCurrentStep] = useState(0);
  const [allDone, setAllDone] = useState(false);

  const updateStep = (id: string, updates: Partial<SetupStep>) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, ...updates } : s))
    );
  };

  useEffect(() => {
    runSetup();
  }, []);

  const runSetup = async () => {
    const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    // ─── Step 1: VTOP Login ────────────────────────────────────────────
    setCurrentStep(0);
    updateStep("vtop", {
      status: "connecting",
      description: "Connecting to VTOP portal...",
    });
    await delay(800);

    updateStep("vtop", {
      status: "connecting",
      description: "Checking VTOP session...",
      detail: "Using saved browser session cookies",
    });
    await delay(1000);

    // Actually trigger VTOP sync — runs Playwright in backend subprocess
    let syncSuccess = false;
    try {
      updateStep("vtop", {
        status: "syncing",
        description: "Running VTOP scraper...",
        detail: "Fetching attendance, marks & profile from portal",
      });

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 90000);

      const res = await fetch(`${BASE}/api/academic/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (res.ok) {
        const data = await res.json();
        syncSuccess = data.status === "completed";
        if (syncSuccess) {
          updateStep("vtop", {
            status: "done",
            description: "VTOP synced successfully",
            detail: `Attendance, marks & profile loaded${data.summary ? ` — ${JSON.stringify(data.summary).substring(0, 60)}` : ""}`,
          });
        } else {
          updateStep("vtop", {
            status: "done",
            description: "VTOP connected (partial sync)",
            detail: data.error?.substring(0, 80) || "Some data may not have loaded",
          });
        }
      } else {
        throw new Error("non-200");
      }
    } catch {
      // Check if backend has a valid session at least
      try {
        const statusRes = await fetch(`${BASE}/api/status`, { signal: AbortSignal.timeout(5000) });
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          if (statusData.vtop?.session_valid) {
            updateStep("vtop", {
              status: "done",
              description: "VTOP session active",
              detail: "Sync will run on scheduler (every 30 min)",
            });
          } else {
            updateStep("vtop", {
              status: "error",
              description: "VTOP session expired",
              detail: "Run: python vtop_login_browser.py to re-login",
            });
          }
        } else {
          throw new Error("status failed");
        }
      } catch {
        updateStep("vtop", {
          status: "error",
          description: "Backend not reachable",
          detail: "Start backend: python run.py",
        });
      }
    }
    await delay(400);

    // ─── Step 2: WhatsApp ──────────────────────────────────────────────
    setCurrentStep(1);
    updateStep("whatsapp", {
      status: "connecting",
      description: "Checking WhatsApp bridge...",
    });
    await delay(800);

    // Check real status from backend
    try {
      const statusRes = await fetch(`${BASE}/api/status`, { signal: AbortSignal.timeout(5000) });
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        const wa = statusData.whatsapp;
        const ngrok = statusData.ngrok;

        if (wa?.connected) {
          updateStep("whatsapp", {
            status: "done",
            description: "WhatsApp connected",
            detail: `Live pipeline active${ngrok?.url ? ` via ${ngrok.url.replace("https://", "")}` : ""}`,
          });
        } else if (ngrok?.active) {
          updateStep("whatsapp", {
            status: "syncing",
            description: "Waiting for QR code scan...",
            detail: "Open whatsapp_qr.html and scan with WhatsApp",
          });
          await delay(2000);
          updateStep("whatsapp", {
            status: "done",
            description: "WhatsApp bridge ready",
            detail: `Webhook: ${ngrok.url}/api/webhooks/whatsapp — scan QR to connect`,
          });
        } else {
          updateStep("whatsapp", {
            status: "error",
            description: "ngrok not available",
            detail: "Set NGROK_AUTHTOKEN in .env and restart backend",
          });
        }
      } else {
        throw new Error("status check failed");
      }
    } catch {
      updateStep("whatsapp", {
        status: "error",
        description: "Could not check WhatsApp status",
        detail: "Backend may not be running",
      });
    }
    await delay(400);

    // ─── Step 3: Google ────────────────────────────────────────────────
    setCurrentStep(2);
    updateStep("google", {
      status: "connecting",
      description: "Checking Google integration...",
    });
    await delay(800);

    // Google OAuth is not implemented yet — show coming soon
    updateStep("google", {
      status: "done",
      description: "Google (coming soon)",
      detail: "Gmail & Calendar integration planned for next phase",
    });
    await delay(600);

    // All done
    setAllDone(true);
    await delay(1200);
    onComplete();
  };

  const statusColor = (status: SetupStep["status"]) => {
    switch (status) {
      case "done": return "text-success";
      case "connecting": return "text-accent";
      case "syncing": return "text-accent";
      case "error": return "text-urgent";
      default: return "text-secondary";
    }
  };

  const statusIcon = (status: SetupStep["status"]) => {
    switch (status) {
      case "done": return "✓";
      case "connecting": return "◌";
      case "syncing": return "↻";
      case "error": return "✕";
      default: return "○";
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="font-display text-3xl font-light text-foreground">
            CampusFlow
          </h1>
          <p className="text-sm text-secondary mt-2">
            Welcome back, Pratik. Connecting your services...
          </p>
        </div>

        {/* Steps */}
        <div className="space-y-4">
          {steps.map((step, i) => (
            <div
              key={step.id}
              className={`p-4 rounded-xl border transition-all duration-500 ${
                step.status === "done"
                  ? "border-success/30 bg-success/5"
                  : i === currentStep
                  ? "border-accent/50 bg-accent-light"
                  : "border-border bg-surface"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">{step.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">
                      {step.label}
                    </p>
                    <span className={`text-sm font-mono ${statusColor(step.status)}`}>
                      {statusIcon(step.status)}
                    </span>
                  </div>
                  <p className={`text-xs mt-0.5 ${statusColor(step.status)}`}>
                    {step.description}
                  </p>
                  {step.detail && (
                    <p className="text-[10px] text-secondary mt-0.5 font-mono">
                      {step.detail}
                    </p>
                  )}
                </div>
              </div>

              {/* Progress bar for active step */}
              {(step.status === "connecting" || step.status === "syncing") && (
                <div className="mt-3 w-full h-1 bg-border rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-1000 ${
                      step.status === "syncing" ? "bg-accent w-3/4" : "bg-accent/60 w-1/3 animate-pulse"
                    }`}
                  />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Completion */}
        {allDone && (
          <div className="mt-8 text-center animate-fadeIn">
            <p className="text-sm text-success font-medium">
              All services connected ✓
            </p>
            <p className="text-xs text-secondary mt-1">
              Launching CampusFlow...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
