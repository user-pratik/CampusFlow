"use client";

import { useEffect, useState } from "react";

/**
 * Use relative URL to leverage Next.js rewrites (next.config.ts proxies /api/* to backend).
 * This avoids CORS issues and port mismatches — the browser always talks to the Next.js
 * server on the same origin, and Next.js forwards to localhost:8000 server-side.
 */
const BASE = "";

interface EmailNotification {
  id: number;
  gmail_msg_id: string;
  subject: string;
  sender: string;
  received_at: string;
  category: string;
  priority: "high" | "medium" | "low";
  summary: string;
  is_read: boolean;
}

interface Props {
  data: Record<string, unknown>;
}

const CATEGORIES = ["ALL", "EXAM", "PLACEMENT", "FEE", "EVENT", "ANNOUNCEMENT"] as const;

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-urgent/10 text-urgent border-urgent/20",
  medium: "bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800",
  low: "bg-surface text-secondary border-border",
};

const CATEGORY_ICONS: Record<string, string> = {
  EXAM: "📝",
  PLACEMENT: "💼",
  FEE: "💰",
  EVENT: "🎉",
  ANNOUNCEMENT: "📢",
  GENERAL: "📧",
};

export default function EmailPanel({ data }: Props) {
  const [emails, setEmails] = useState<EmailNotification[]>([]);
  const [category, setCategory] = useState<string>("ALL");
  const [syncing, setSyncing] = useState(false);
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE}/api/gmail/auth-status`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setAuthed(d.authenticated))
      .catch(() => {
        setAuthed(false);
        setError("Unable to reach backend — is it running?");
      });
  }, []);

  useEffect(() => {
    if (authed) loadEmails();
  }, [authed, category]);

  const loadEmails = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = category === "ALL"
        ? `${BASE}/api/gmail/all`
        : `${BASE}/api/gmail/all?category=${category}`;
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) {
        setError(`Server error (${res.status}). Try syncing again.`);
        return;
      }
      setEmails(await res.json());
    } catch (err) {
      // TypeError: Failed to fetch — backend unreachable
      setError("Unable to load emails — is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setError(null);
    try {
      const res = await fetch(`${BASE}/api/gmail/sync`, { method: "POST" });
      if (!res.ok) {
        setError(`Sync failed (${res.status}).`);
        return;
      }
      await loadEmails();
    } catch {
      setError("Sync failed — backend unreachable.");
    } finally {
      setSyncing(false);
    }
  };

  const handleAuth = async () => {
    setAuthLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BASE}/api/gmail/auth`, { method: "POST" });
      if (!res.ok) {
        setError("Authentication request failed.");
        return;
      }
      const d = await res.json();
      if (d.status === "authenticated") setAuthed(true);
    } catch {
      setError("Unable to reach backend for authentication.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleMarkRead = async (msgId: string) => {
    try {
      await fetch(`${BASE}/api/gmail/mark-read/${msgId}`, { method: "POST" });
      setEmails((prev) =>
        prev.map((e) => (e.gmail_msg_id === msgId ? { ...e, is_read: true } : e))
      );
    } catch {
      // Silently fail for mark-read — non-critical
    }
  };

  // Error banner component
  const ErrorBanner = () =>
    error ? (
      <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
        <div className="flex items-center gap-2">
          <span className="text-sm">⚠️</span>
          <p className="text-xs text-red-700 dark:text-red-400">{error}</p>
          <button
            onClick={() => { setError(null); if (authed) loadEmails(); }}
            className="ml-auto text-[10px] text-red-600 dark:text-red-400 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      </div>
    ) : null;

  if (authed === false) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <ErrorBanner />
        <span className="text-4xl">📧</span>
        <p className="text-foreground font-medium">Connect Gmail</p>
        <p className="text-xs text-secondary text-center">
          Connect your VIT email to see AI-classified notifications.
        </p>
        <button
          onClick={handleAuth}
          disabled={authLoading}
          className="px-4 py-2 bg-accent text-white rounded-lg text-xs font-medium hover:opacity-90 disabled:opacity-50"
        >
          {authLoading ? "Connecting..." : "Connect Gmail"}
        </button>
      </div>
    );
  }

  if (authed === null) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <ErrorBanner />

      {/* Sync button */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-secondary">
          {emails.filter((e) => !e.is_read).length} unread of {emails.length}
        </p>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="px-2 py-1 bg-accent-light text-accent text-[10px] font-medium rounded hover:bg-accent/20 disabled:opacity-50"
        >
          {syncing ? "↻ Syncing..." : "🔄 Sync Emails"}
        </button>
      </div>

      {/* Category filter */}
      <div className="flex gap-1 flex-wrap">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={`px-2 py-0.5 text-[10px] rounded-full transition-colors ${
              category === cat
                ? "bg-accent text-white"
                : "bg-surface text-secondary hover:text-foreground"
            }`}
          >
            {cat === "ALL" ? "All" : cat}
          </button>
        ))}
      </div>

      {/* Loading state */}
      {loading && !emails.length && (
        <div className="flex items-center justify-center py-8">
          <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Email list */}
      {!loading && emails.length === 0 ? (
        <div className="text-center py-8">
          <span className="text-2xl">📭</span>
          <p className="text-xs text-secondary mt-2">No emails yet. Click &quot;Sync Emails&quot; to fetch.</p>
        </div>
      ) : (
        emails.map((email) => (
          <div
            key={email.gmail_msg_id}
            onClick={() => !email.is_read && handleMarkRead(email.gmail_msg_id)}
            className={`p-3 rounded-lg border cursor-pointer transition-colors ${
              !email.is_read ? "border-accent/30 bg-accent/5" : "border-border bg-surface"
            }`}
          >
            <div className="flex items-start gap-2">
              <span className="text-sm shrink-0 mt-0.5">
                {CATEGORY_ICONS[email.category] || "📧"}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span
                    className={`px-1 py-0 text-[9px] rounded border ${
                      PRIORITY_COLORS[email.priority] || PRIORITY_COLORS.low
                    }`}
                  >
                    {email.priority}
                  </span>
                  {!email.is_read && (
                    <span className="w-1.5 h-1.5 bg-accent rounded-full" />
                  )}
                </div>
                <p className="text-xs text-foreground font-medium truncate">
                  {email.subject}
                </p>
                <p className="text-[10px] text-secondary mt-0.5 line-clamp-2">
                  {email.summary}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[9px] text-secondary truncate">
                    {email.sender?.split("<")[0]?.trim()}
                  </span>
                  <span className="text-[9px] text-secondary">
                    {email.received_at ? new Date(email.received_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                    }) : ""}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
