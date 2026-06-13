import ConflictAlert from "@/components/ConflictAlert";
import MorningBriefing from "@/components/MorningBriefing";
import CampusFeed from "@/components/CampusFeed";

export default function Home() {
  return (
    <main className="flex-1">
      <ConflictAlert />
      <MorningBriefing />
      <div className="max-w-2xl mx-auto px-6">
        <hr className="border-border" />
      </div>
      <CampusFeed />
    </main>
  );
}
