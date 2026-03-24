import { TopHeader } from "../components/TopHeader";
import { HeroStatus } from "../components/HeroStatus";
import { IssuesPanel } from "../components/IssuesPanel";
import { DeclarationSummary } from "../components/DeclarationSummary";
import { DocumentsSummary } from "../components/DocumentsSummary";
import { SecondaryNav } from "../components/SecondaryNav";

export function DeclarationDashboardPage() {
  return (
    <div className="h-screen w-full flex flex-col bg-[#f8f8fa] overflow-hidden" style={{ minWidth: 1280 }}>
      <TopHeader />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto px-6 py-6 space-y-5">
          <HeroStatus />
          <div className="grid grid-cols-5 gap-5">
            <div className="col-span-3">
              <IssuesPanel />
            </div>
            <div className="col-span-2">
              <DeclarationSummary />
            </div>
          </div>
          <DocumentsSummary />
          <SecondaryNav />
          <div className="h-4" />
        </div>
      </main>
    </div>
  );
}
