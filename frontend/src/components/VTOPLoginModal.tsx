"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { checkSessionStatus } from "@/lib/api";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface VTOPLoginModalProps {
  onClose: () => void;
  onLoginSuccess: () => void;
}

export default function VTOPLoginModal({ onClose, onLoginSuccess }: VTOPLoginModalProps) {
  const [status, setStatus] = useState<"launching" | "waiting" | "error">("launching");
  const [errorMsg, setErrorMsg] = useState("");
  const modalRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Store focus and manage it
  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement;
    modalRef.current?.focus();
    return () => {
      previousFocusRef.current?.focus();
    };
  }, []);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Launch the browser login on mount
  useEffect(() => {
    const launch = async () => {
      try {
        const res = await fetch(`${BASE}/api/vtop/launch-login`, { method: "POST" });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setErrorMsg(data.error || "Failed to launch browser");
          setStatus("error");
          return;
        }
        setStatus("waiting");
      } catch {
        setErrorMsg("Could not reach the server");
        setStatus("error");
      }
    };
    launch();
  }, []);

  // Poll session status every 3 seconds once browser is launched
  useEffect(() => {
    if (status !== "waiting") return;

    const interval = setInterval(async () => {
      try {
        const result = await checkSessionStatus();
        if (result.status === "valid") {
          onLoginSuccess();
        }
      } catch {
        // Keep polling
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [status, onLoginSuccess]);

  const handleRetry = async () => {
    setStatus("launching");
    setErrorMsg("");
    try {
      const res = await fetch(`${BASE}/api/vtop/launch-login`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setErrorMsg(data.error || "Failed to launch browser");
        setStatus("error");
        return;
      }
      setStatus("waiting");
    } catch {
      setErrorMsg("Could not reach the server");
      setStatus("error");
    }
  };

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  const modalContent = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label="VTOP Login"
    >
      <div
        ref={modalRef}
        className="bg-panel-bg border border-border rounded-xl p-8 max-w-md w-full shadow-xl"
        tabIndex={-1}
      >
        {status === "launching" && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <p className="text-foreground font-medium">Launching VTOP login...</p>
            <p className="text-sm text-secondary text-center">
              A browser window will open shortly.
            </p>
          </div>
        )}

        {status === "waiting" && (
          <div className="flex flex-col items-center gap-4">
            <span className="text-4xl">🌐</span>
            <p className="text-foreground font-medium">Browser opened</p>
            <p className="text-sm text-secondary text-center">
              Solve the reCAPTCHA and click Login in the browser window.
              <br />
              This modal will close automatically once login succeeds.
            </p>
            <div className="flex items-center gap-2 mt-2">
              <div className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-secondary">Waiting for login...</span>
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="flex flex-col items-center gap-4">
            <span className="text-4xl">⚠️</span>
            <p className="text-foreground font-medium">Could not launch browser</p>
            <p className="text-sm text-secondary text-center">{errorMsg}</p>
            <button
              onClick={handleRetry}
              className="px-4 py-2 text-sm font-medium bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        <button
          onClick={onClose}
          className="mt-6 w-full text-center text-xs text-secondary hover:text-foreground transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
