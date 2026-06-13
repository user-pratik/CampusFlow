"use client";

import { useEffect, useState } from "react";
import { fetchLatestDigest, triggerDigest, type Digest } from "@/lib/api";

function parseDigestContent(content: string) {
  const parts = content.split("*").map((s) => s.trim()).filter(Boolean);
  const greeting = parts[0] || "";
  const bullets = parts.slice(1);
  return { greeting, bullets };
}

export default function MorningBriefing() {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    fetchLatestDigest()
      .then(setDigest)
      .catch(() => setDigest(null));
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    await triggerDigest().catch(() => {});
    setTimeout(() => {
      fetchLatestDigest()
        .then(setDigest)
        .catch(() => {})
        .finally(() => setGenerating(false));
    }, 2000);
  };

  const parsed = digest ? parseDigestContent(digest.content) : null;

  return (
    <section className="max-w-2xl mx-auto px-6 pt-16 pb-12">
      <p className="text-secondary text-xs uppercase tracking-widest mb-3">
        Morning Briefing
      </p>

      {parsed ? (
        <div className="space-y-6">
          <p className="font-display text-2xl md:text-3xl leading-snug font-light text-gray-900">
            {parsed.greeting}
          </p>

          {parsed.bullets.length > 0 && (
            <ul className="border-l border-gray-200 pl-6 space-y-4">
              {parsed.bullets.map((bullet, i) => (
                <li
                  key={i}
                  className="text-gray-600 leading-relaxed tracking-wide text-sm"
                >
                  {bullet}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="font-display text-2xl md:text-3xl leading-snug font-light text-secondary/60 italic">
          Nothing yet. Generate your first briefing below.
        </p>
      )}

      <button
        onClick={handleGenerate}
        disabled={generating}
        className="mt-6 text-xs text-secondary hover:text-foreground transition-colors underline underline-offset-4 decoration-border disabled:opacity-40"
      >
        {generating ? "Generating…" : "Generate new briefing"}
      </button>

      {digest && (
        <p className="mt-4 text-[11px] text-secondary/50">
          Last generated{" "}
          {new Date(digest.generated_at).toLocaleString("en-IN", {
            dateStyle: "medium",
            timeStyle: "short",
          })}
        </p>
      )}
    </section>
  );
}
