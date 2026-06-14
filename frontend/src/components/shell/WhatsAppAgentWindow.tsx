"use client";

import { useCallback, useEffect, useState } from "react";
import { useWindowManager } from "@/lib/windowManager";

interface WAGroup {
  name: string;
  count: number;
  last_message: string | null;
  messages: { text: string; sender: string; category: string; date: string }[];
}

export function useWhatsAppAgent() {
  const { spawnWindow } = useWindowManager();

  const spawn = useCallback(() => {
    spawnWindow(
      "WhatsApp Agent",
      "WhatsApp Groups",
      <WhatsAppAgentContent />,
      {
        agentIcon: "💬",
        size: { width: 420, height: 520 },
        position: { x: 140, y: 50 },
      }
    );
  }, [spawnWindow]);

  return { spawn };
}

function WhatsAppAgentContent() {
  const [groups, setGroups] = useState<WAGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/webhooks/whatsapp-groups", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => { setGroups(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center py-8"><span className="text-xs text-secondary">Loading groups...</span></div>;
  }

  if (groups.length === 0) {
    return (
      <div className="text-center py-8">
        <span className="text-2xl">💬</span>
        <p className="text-xs text-secondary mt-2">No WhatsApp messages yet.</p>
        <p className="text-[10px] text-secondary mt-1">Connect via n8n webhook.</p>
      </div>
    );
  }

  const selected = groups.find((g) => g.name === selectedGroup);

  if (selected) {
    return (
      <div className="flex flex-col h-full">
        <button onClick={() => setSelectedGroup(null)} className="text-xs text-accent hover:underline px-3 py-2">← Back</button>
        <div className="px-3 pb-2 border-b border-border">
          <p className="text-sm font-medium text-foreground">{selected.name}</p>
          <p className="text-[10px] text-secondary">{selected.count} messages</p>
        </div>
        <div className="flex-1 overflow-y-auto divide-y divide-border">
          {selected.messages.map((msg, i) => (
            <div key={i} className="px-3 py-2">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[9px] text-secondary">{msg.sender}</span>
                {msg.category !== "GENERAL" && (
                  <span className="text-[8px] px-1 py-0 rounded bg-accent/10 text-accent">{msg.category}</span>
                )}
              </div>
              <p className="text-xs text-foreground">{msg.text.slice(0, 200)}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <p className="px-3 py-2 text-[10px] text-secondary">
        {groups.reduce((a, g) => a + g.count, 0)} messages · {groups.length} groups
      </p>
      {groups.map((group) => (
        <button
          key={group.name}
          onClick={() => setSelectedGroup(group.name)}
          className="w-full px-3 py-2.5 text-left hover:bg-surface-hover transition-colors"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-foreground truncate">{group.name}</span>
            <span className="text-[10px] text-secondary shrink-0">{group.count}</span>
          </div>
          {group.last_message && (
            <p className="text-[10px] text-secondary truncate mt-0.5">{group.last_message}</p>
          )}
        </button>
      ))}
    </div>
  );
}

export default WhatsAppAgentContent;
