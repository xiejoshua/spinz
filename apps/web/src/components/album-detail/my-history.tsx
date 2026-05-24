import { AuxIcon } from "@/components/icons/aux";
import { Badge } from "@/components/ui/badge";
import type { DiaryRow } from "@/lib/album-types";

type Props = {
  history: DiaryRow[];
};

export function MyHistory({ history }: Props) {
  if (history.length === 0) {
    return null;
  }
  return (
    <section aria-labelledby="my-history-heading" className="space-y-2">
      <h2 id="my-history-heading" className="text-lg font-semibold">
        My history ({history.length})
      </h2>
      <ul className="divide-y rounded-md border">
        {history.map((entry) => (
          <li key={entry.id} className="flex items-center gap-3 px-3 py-2 text-sm">
            <span className="text-muted-foreground">
              {new Date(entry.logged_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
              })}
            </span>
            {entry.rating != null && (
              <span>
                <span aria-hidden="true">{"★".repeat(Math.round(entry.rating))}</span>
                <span className="sr-only">Rated {entry.rating} of 5 stars</span>
                <span className="ml-1 text-muted-foreground">{entry.rating.toFixed(1)}</span>
              </span>
            )}
            {entry.auxed && (
              <Badge variant="secondary" className="h-5 px-1.5 py-0">
                <span
                  aria-hidden="true"
                  className="mr-1 inline-flex items-center"
                  style={{ color: "var(--gold)" }}
                >
                  <AuxIcon filled size={12} />
                </span>
                Aux’d
              </Badge>
            )}
            {entry.visibility !== "public" && (
              <Badge variant="outline" className="h-5 px-1.5 py-0 capitalize">
                {entry.visibility}
              </Badge>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
