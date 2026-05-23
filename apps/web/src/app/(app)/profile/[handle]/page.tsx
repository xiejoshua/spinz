import { ProfileClient } from "@/components/diary/profile-client";
import type { Metadata } from "next";

type Params = Promise<{ handle: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return {
    title: `@${cleaned} — auxd`,
    description: `${cleaned}'s diary on auxd`,
    openGraph: {
      title: `@${cleaned} on auxd`,
      description: `${cleaned}'s diary on auxd`,
    },
  };
}

export default async function ProfilePage({ params }: { params: Params }) {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return (
    <article className="container max-w-3xl space-y-6 py-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">@{cleaned}</h1>
        <p className="text-sm text-muted-foreground">Diary</p>
      </header>
      <ProfileClient handle={cleaned} />
    </article>
  );
}
