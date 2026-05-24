const columns = [
  {
    num: "01",
    title: "Social-graph first.",
    body: "Discovery through the people you follow.",
  },
  {
    num: "02",
    title: "Album-as-unit.",
    body: "A reaction is tied to an album, not a song-of-the-moment.",
  },
  {
    num: "03",
    title: "Reviews as essays.",
    body: "Join the discourse on your favorite works and take back music as an art form.",
  },
];

export function WedgeThesis() {
  return (
    <section
      id="wedge"
      className="w-full"
      style={{ background: "var(--background)" }}
    >
      <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-3 md:gap-10">
          {columns.map((col) => (
            <div key={col.num}>
              <div
                className="font-mono font-medium uppercase"
                style={{
                  fontSize: "11px",
                  letterSpacing: "0.18em",
                  color: "var(--muted)",
                }}
              >
                {col.num}
              </div>
              <div
                className="mt-4 mb-6 h-px"
                style={{ background: "var(--separator)" }}
              />
              <h2
                className="font-serif font-semibold leading-[1.15] tracking-[-0.01em]"
                style={{
                  fontSize: "28px",
                  color: "var(--foreground)",
                }}
              >
                {col.title}
              </h2>
              <p
                className="mt-4 font-sans text-[16px] leading-[1.6]"
                style={{
                  color: "var(--muted)",
                  maxWidth: "32ch",
                }}
              >
                {col.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
