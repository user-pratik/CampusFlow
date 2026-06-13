"use client";

import mockData from "@/lib/mockData.json";

interface Props {
  data: Record<string, unknown>;
}

export default function EmailPanel({ data }: Props) {
  const emails = mockData.emails;
  const highlight = data?.highlight as string | undefined;

  return (
    <div className="space-y-3">
      <p className="text-xs text-secondary">
        {emails.filter((e) => !e.read).length} unread of {emails.length} emails
      </p>

      {emails.map((email) => (
        <div
          key={email.id}
          className={`p-3 rounded-lg border transition-colors ${
            highlight && email.category === highlight
              ? "border-accent bg-accent-light"
              : email.read
              ? "border-border bg-surface"
              : "border-accent/30 bg-surface"
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                {!email.read && (
                  <span className="w-2 h-2 bg-accent rounded-full shrink-0" />
                )}
                <p className={`text-sm truncate ${!email.read ? "font-semibold text-foreground" : "text-foreground"}`}>
                  {email.subject}
                </p>
              </div>
              <p className="text-xs text-secondary mt-0.5 truncate">
                {email.from}
              </p>
            </div>
          </div>
          <p className="text-xs text-secondary mt-2 line-clamp-2 leading-relaxed">
            {email.preview}
          </p>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-[10px] text-secondary">
              {new Date(email.timestamp).toLocaleDateString("en-IN", {
                day: "numeric",
                month: "short",
              })}
            </span>
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-surface-hover text-secondary font-medium">
              {email.category}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
