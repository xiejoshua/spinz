import { PageHeader } from "@/components/nav/page-header";
import { UpNextList } from "@/components/up-next/up-next-list";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Up Next — auxd",
  description: "Your backlog of albums to listen to next.",
};

export default function UpNextPage() {
  return (
    <article className="container max-w-3xl space-y-8 py-10">
      <PageHeader
        eyebrow="Backlog"
        title="Up next."
        subtitle="Drag to reorder. Logging an album auto-removes it unless you turned that off in settings."
      />
      <UpNextList />
    </article>
  );
}
