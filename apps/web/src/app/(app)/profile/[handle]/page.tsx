import { ProfileClient, type ProfileView } from "@/components/diary/profile-client";
import type { Metadata } from "next";

type Params = Promise<{ handle: string }>;
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function resolveView(raw: string | string[] | undefined): ProfileView {
  return raw === "reviews" ? "reviews" : "diary";
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Params;
  searchParams: SearchParams;
}): Promise<Metadata> {
  const { handle } = await params;
  const sp = await searchParams;
  const view = resolveView(sp.view);
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  if (view === "reviews") {
    return {
      title: `Reviews by @${cleaned} — auxd`,
      description: `Reviews written by ${cleaned} on auxd`,
      openGraph: {
        title: `Reviews by @${cleaned} on auxd`,
        description: `Reviews written by ${cleaned} on auxd`,
      },
    };
  }
  return {
    title: `@${cleaned} — auxd`,
    description: `${cleaned}'s diary on auxd`,
    openGraph: {
      title: `@${cleaned} on auxd`,
      description: `${cleaned}'s diary on auxd`,
    },
  };
}

export default async function ProfilePage({
  params,
  searchParams,
}: {
  params: Params;
  searchParams: SearchParams;
}) {
  const { handle } = await params;
  const sp = await searchParams;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  const view = resolveView(sp.view);
  return (
    <article className="container max-w-3xl py-10">
      <ProfileClient handle={cleaned} view={view} />
    </article>
  );
}
