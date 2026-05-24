import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ExampleFeed } from "./_components/example-feed";
import { FinalCta } from "./_components/final-cta";
import { Hero } from "./_components/hero";
import { TopBar } from "./_components/top-bar";
import { WedgeDemo } from "./_components/wedge-demo";
import { WedgeThesis } from "./_components/wedge-thesis";

const SESSION_COOKIE = "auxd_session";

export default async function LandingPage() {
  // Signed-in viewers skip the marketing pitch and land on their feed.
  // The session cookie is enough to gate the redirect — backend
  // session validation runs on the destination via (app)/layout.tsx,
  // so a stale/forged cookie still gets a 401 redirect to /login from
  // there rather than serving authenticated content from /feed.
  const cookieStore = await cookies();
  if (cookieStore.get(SESSION_COOKIE)) {
    redirect("/feed");
  }
  return (
    <>
      <TopBar />
      <main>
        <Hero />
        <WedgeThesis />
        <WedgeDemo />
        <ExampleFeed />
        <FinalCta />
      </main>
    </>
  );
}
