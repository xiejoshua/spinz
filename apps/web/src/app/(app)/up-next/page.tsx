import { UpNextList } from "@/components/up-next/up-next-list";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Up Next — auxd",
  description: "Your backlog of albums to listen to next.",
};

export default function UpNextPage() {
  return (
    <article className="container max-w-3xl space-y-4 py-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Up Next</h1>
        <p className="text-sm text-muted-foreground">
          Drag to reorder. Logging an album auto-removes it unless you turned that off in settings.
        </p>
      </header>
      <UpNextList />
    </article>
  );
}
