"use client";

import mockData from "@/lib/mockData.json";

interface Props {
  data: Record<string, unknown>;
}

export default function WhatsAppPanel({ data }: Props) {
  const messages = mockData.whatsappMessages;

  const typeColor = (type: string) => {
    switch (type) {
      case "academic": return "bg-accent-light text-accent";
      case "event": return "bg-success/10 text-success";
      case "placement": return "bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400";
      default: return "bg-surface-hover text-secondary";
    }
  };

  const timeAgo = (ts: string) => {
    const diff = Date.now() - new Date(ts).getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours < 1) return "Just now";
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-secondary">
        {messages.length} messages from {new Set(messages.map((m) => m.group)).size} groups
      </p>

      {messages.map((msg) => (
        <div
          key={msg.id}
          className="p-3 rounded-lg border border-border bg-surface hover:bg-surface-hover transition-colors"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-xs font-medium text-accent truncate">
                  {msg.group}
                </p>
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${typeColor(msg.type)}`}>
                  {msg.type}
                </span>
              </div>
              <p className="text-xs text-secondary mt-0.5">{msg.sender}</p>
            </div>
            <span className="text-[10px] text-secondary shrink-0">
              {timeAgo(msg.timestamp)}
            </span>
          </div>
          <p className="text-sm text-foreground mt-2 leading-relaxed">
            {msg.text}
          </p>
        </div>
      ))}
    </div>
  );
}
