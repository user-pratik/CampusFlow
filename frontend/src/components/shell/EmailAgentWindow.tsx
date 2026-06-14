"use client";

import { useCallback, useEffect, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";

interface EmailItem {
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

const CATEGORIES = ["ALL", "EXAM", "PLACEMENT", "FEE", "EVENT", "ANNOUNCEMENT"] as const;

const PRIORITY_BADGE: Record<string, string> = {
  high: "bg-urgent/10 text-urgent",
  medium: "bg-conflict/10 text-conflict",
  low: "bg-surface text-secondary",
};

const CATEGORY_ICON: Record<string, string> = {
  EXAM: "📝",
  PLACEMENT: "💼",
  FEE: "💰",
  EVENT: "🎉",
  ANNOUNCEMENT: "📢",
  GENERAL: "📧",
};

export function useEmailAgent() {
  const { spawnWindow } = useWindowManager();

  const spawn = useCallback(() => {
    spawnWindow(
      "Email Agent",
      "Email Intelligence",
      <EmailAgentContent />,
      {
        agentIcon: "📧",
        size: { width: 440, height: 560 },
        position: { x: 180, y: 60 },
      }
    );
  }, [spawnWindow]);

  return { spawn };
}

function EmailAgentContent() {
  const [emails, setEmails] = useState<EmailItem[]>([]);
  const [category, setCategory] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/gmail/auth-status", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setAuthed(d.authenticated))
      .catch(() => setAuthed(false));
  }, []);

  const fetchEmails = useCallback(async () => {
    try {
      const url = category === "ALL" ? "/api/gmail/emails-only" : `/api/gmail/emails-only?category=${category}`;
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) setEmails(await res.json());
    } catch { /* silent */ }
    setLoading(false);
  }, [category]);

  useEffect(() => {
    if (authed) fetchEmails();
  }, [authed, fetchEmails]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await fetch("/api/gmail/sync", { method: "POST" });
      await fetchEmails();
    } catch { /* silent */ }
    setSyncing(false);
  };

  const handleAuth = async () => {
    try {
      const res = await fetch("/api/gmail/auth", { method: "POST" });
      const d = await res.json();
      if (d.status === "authenticated") {
        setAuthed(true);
      }
    } catch { /* silent */ }
  };

  if (authed === false) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-8">
        <span className="text-3xl">📧</span>
        <p className="text-sm text-foreground font-medium">Connect Gmail</p>
        <p className="text-xs text-secondary text-center px-4">
          Connect your VIT email to see AI-classified notifications.
        </p>
        <button
          onClick={handleAuth}
          className="px-3 py-1.5 bg-accent text-white rounded-md text-xs font-medium hover:opacity-90"
        >
          Connect Gmail
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <span className="text-xs text-secondary">Loading emails...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with sync */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="text-[10px] text-secondary">
          {emails.filter((e) => !e.is_read).length} unread / {emails.length} total
        </span>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-1 text-[10px] px-2 py-1 bg-accent/10 text-accent rounded-md hover:bg-accent/20 transition-colors disabled:opacity-40"
        >
          <span className={syncing ? "animate-spin" : ""}>↻</span>
          {syncing ? "Syncing" : "Sync Gmail"}
        </button>
      </div>

      {/* Category tabs */}
      <div className="flex gap-1 px-3 py-2 border-b border-border overflow-x-auto">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={`px-2 py-0.5 text-[10px] rounded-full whitespace-nowrap transition-colors ${
              category === cat
                ? "bg-accent text-white"
                : "bg-surface text-secondary hover:text-foreground"
            }`}
          >
            {cat === "ALL" ? "All" : cat}
          </button>
        ))}
      </div>

      {/* Email list */}
      <div className="flex-1 overflow-y-auto">
        {emails.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-xs text-secondary">No emails. Click Sync to fetch.</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {emails.map((email, idx) => (
              <div key={`${email.gmail_msg_id}-${idx}`} className={`px-3 py-2.5 ${!email.is_read ? "bg-accent/5" : ""}`}>
                <div className="flex items-start gap-2">
                  <span className="text-sm shrink-0">{CATEGORY_ICON[email.category] || "📧"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className={`text-[9px] px-1 py-0 rounded ${PRIORITY_BADGE[email.priority] || ""}`}>
                        {email.priority}
                      </span>
                      {!email.is_read && <span className="w-1.5 h-1.5 bg-accent rounded-full" />}
                    </div>
                    <p className="text-xs text-foreground font-medium truncate">{email.subject}</p>
                    <p className="text-[10px] text-secondary truncate mt-0.5">{email.summary}</p>
                    <p className="text-[9px] text-secondary mt-0.5">
                      {email.sender?.split("<")[0]?.trim()} · {new Date(email.received_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default EmailAgentContent;
