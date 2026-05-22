import { greeting } from "@spinz/shared-types";

export default function Home() {
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>Spinz</h1>
      <p>{greeting()}</p>
      <p style={{ color: "#666", fontSize: "0.875rem" }}>
        Monorepo scaffold — T003 verified. Feature work begins in §1 backend foundation.
      </p>
    </main>
  );
}
