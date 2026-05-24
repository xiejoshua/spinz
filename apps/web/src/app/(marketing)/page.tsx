import { ExampleFeed } from "./_components/example-feed";
import { FinalCta } from "./_components/final-cta";
import { Hero } from "./_components/hero";
import { TopBar } from "./_components/top-bar";
import { WedgeDemo } from "./_components/wedge-demo";
import { WedgeThesis } from "./_components/wedge-thesis";

export default function LandingPage() {
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
