"use client";

import { useEffect, useState } from "react";
import mockData from "@/lib/mockData.json";
import { fetchProfile, type Profile } from "@/lib/api";

interface Props {
  data: Record<string, unknown>;
}

export default function GroupsPanel({ data }: Props) {
  const groups = mockData.suggestedGroups;
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    fetchProfile().then(setProfile).catch(() => {});
  }, []);

  return (
    <div className="space-y-4">
      <div className="bg-surface rounded-xl p-4">
        <p className="text-xs text-secondary uppercase tracking-wide">
          Suggested for you
        </p>
        <p className="text-sm text-foreground mt-1">
          Based on your interests: {profile?.interests?.join(", ") || "Loading..."}
        </p>
      </div>

      <div className="space-y-2">
        {groups.map((group, i) => (
          <div
            key={i}
            className="p-3 rounded-lg border border-border bg-surface hover:bg-surface-hover transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">
                  👥 {group.name}
                </p>
                <p className="text-xs text-secondary mt-0.5">
                  {group.members} members
                </p>
                <p className="text-[10px] text-accent mt-1">{group.reason}</p>
              </div>
              <button className="text-xs px-3 py-1.5 rounded-lg bg-accent text-white hover:opacity-90 transition-opacity shrink-0">
                Join
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
