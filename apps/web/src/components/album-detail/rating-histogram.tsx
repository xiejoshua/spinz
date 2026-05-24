"use client";

import { BarChart } from "@mui/x-charts/BarChart";
import { useMemo } from "react";

type Props = {
  /**
   * 10-element array of counts for each half-star bucket from ½ to 5.
   *   index 0 → ½ star, 1 → 1 star, …, 9 → 5 stars.
   * If not provided, a synthetic distribution is derived from avg + count
   * (right-skewed normal around avg). This is litmus-grade only —
   * backend should produce real counts in a future task.
   */
  distribution?: number[];
  avgRating?: number;
  ratingCount?: number;
};

const BUCKETS = ["½", "1", "1½", "2", "2½", "3", "3½", "4", "4½", "5"];

function syntheticDistribution(avg: number, total: number): number[] {
  const sigma = 1.2; // half-star units
  const out = new Array(10).fill(0);
  if (total === 0) return out;
  let sum = 0;
  for (let i = 0; i < 10; i++) {
    const x = (i + 1) * 0.5;
    const w = Math.exp(-((x - avg) ** 2) / (2 * sigma ** 2));
    out[i] = w;
    sum += w;
  }
  return out.map((w) => Math.round((w / sum) * total));
}

export function RatingHistogram({ distribution, avgRating = 0, ratingCount = 0 }: Props) {
  const data = useMemo(() => {
    return distribution ?? syntheticDistribution(avgRating, ratingCount);
  }, [distribution, avgRating, ratingCount]);

  if (ratingCount === 0) return null;

  return (
    <section aria-labelledby="rating-distribution-heading" className="space-y-2">
      <h2
        id="rating-distribution-heading"
        className="font-mono uppercase"
        style={{
          fontSize: "11px",
          letterSpacing: "0.18em",
          color: "var(--muted)",
        }}
      >
        Rating distribution
      </h2>
      <div
        className="rounded-md p-3"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
        }}
      >
        <BarChart
          height={120}
          xAxis={[
            {
              data: BUCKETS,
              scaleType: "band",
              disableLine: true,
              disableTicks: true,
              tickLabelStyle: {
                fontSize: 11,
                fill: "var(--muted)",
                fontFamily: "var(--font-mono)",
              },
            },
          ]}
          yAxis={[{ disableLine: true, disableTicks: true, position: "none" }]}
          series={[
            {
              data,
              color: "var(--accent)",
            },
          ]}
          margin={{ top: 8, bottom: 24, left: 0, right: 0 }}
          slotProps={{ legend: { sx: { display: "none" } } }}
          grid={{ horizontal: false, vertical: false }}
          borderRadius={2}
        />
      </div>
    </section>
  );
}
