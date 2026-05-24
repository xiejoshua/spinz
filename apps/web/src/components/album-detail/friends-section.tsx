import { AuxIcon } from "@/components/icons/aux";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { DiaryRow } from "@/lib/album-types";

export function FriendsSection({ friends }: { friends: DiaryRow[] }) {
  if (friends.length === 0) {
    return null;
  }
  return (
    <section aria-labelledby="friends-heading" className="space-y-3">
      <h2 id="friends-heading" className="text-lg font-semibold">
        Friends
      </h2>
      <ul className="divide-y rounded-md border">
        {friends.map((entry) => (
          <li key={entry.id} className="flex items-center gap-3 px-3 py-2">
            <Avatar className="size-9">
              <AvatarFallback>{entry.user_id.slice(0, 2).toUpperCase()}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">User {entry.user_id.slice(0, 8)}</p>
              <p className="truncate text-xs text-muted-foreground">
                {new Date(entry.logged_at).toLocaleDateString()}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2 text-sm">
              {entry.rating != null && (
                <span>
                  <span aria-hidden="true">{"★".repeat(Math.round(entry.rating))}</span>
                  <span className="sr-only">Rated {entry.rating} of 5 stars</span>
                </span>
              )}
              {entry.auxed && (
                <span
                  aria-hidden="true"
                  className="inline-flex items-center"
                  style={{ color: "var(--gold)" }}
                >
                  <AuxIcon filled size={14} />
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
