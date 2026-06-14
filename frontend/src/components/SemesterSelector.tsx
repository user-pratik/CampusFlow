"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { fetchVtopSemesters } from "@/lib/api";

interface SemesterSelectorProps {
  onClose: () => void;
  onConfirm: (semesterId: string) => void;
}

export default function SemesterSelector({ onClose, onConfirm }: SemesterSelectorProps) {
  const [semesters, setSemesters] = useState<Record<string, string> | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryDisabled, setRetryDisabled] = useState(false);
  const retriesRef = useRef(0);
  const maxRetries = 3;

  const loadSemesters = useCallback(async () => {
    setLoading(true);
    setError(false);

    let attempts = 0;
    while (attempts < maxRetries) {
      try {
        const data = await fetchVtopSemesters();
        const entries = Object.entries(data.semesters);

        // Auto-proceed if only one semester
        if (entries.length === 1) {
          onConfirm(entries[0][1]);
          return;
        }

        setSemesters(data.semesters);
        // Pre-select first (most recent)
        if (entries.length > 0) {
          setSelected(entries[0][1]);
        }
        setLoading(false);
        retriesRef.current = 0;
        return;
      } catch {
        attempts++;
      }
    }

    // All retries exhausted
    setLoading(false);
    setError(true);
    retriesRef.current += 1;
    if (retriesRef.current >= maxRetries) {
      setRetryDisabled(true);
    }
  }, [onConfirm]);

  useEffect(() => {
    loadSemesters();
  }, [loadSemesters]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleConfirm = () => {
    if (selected) {
      onConfirm(selected);
    }
  };

  const handleRetry = () => {
    loadSemesters();
  };

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const content = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="semester-selector-title"
    >
      <div className="bg-panel-bg border border-border rounded-xl max-w-sm w-full p-6">
        {loading && (
          <div className="flex flex-col items-center gap-3">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-secondary">Loading semesters...</p>
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center gap-3">
            <p className="text-sm text-urgent">Couldn&apos;t load semesters</p>
            <button
              onClick={handleRetry}
              disabled={retryDisabled}
              className="bg-accent text-white rounded-lg py-2 px-4 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {retryDisabled ? "Try again later" : "Retry"}
            </button>
          </div>
        )}

        {!loading && !error && semesters && (
          <>
            <h2
              id="semester-selector-title"
              className="text-foreground font-medium text-base mb-4"
            >
              Select Semester
            </h2>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="w-full bg-surface border border-border rounded-lg text-foreground text-sm py-2 px-3 mb-4 outline-none focus:ring-2 focus:ring-accent"
            >
              {Object.entries(semesters).map(([name, id]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
            <button
              onClick={handleConfirm}
              className="w-full bg-accent text-white rounded-lg py-2 px-4 text-sm font-medium hover:opacity-90 transition-opacity"
            >
              Sync
            </button>
          </>
        )}
      </div>
    </div>
  );

  return createPortal(content, document.body);
}
