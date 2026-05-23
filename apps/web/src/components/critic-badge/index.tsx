// Small inline "· Critic" suffix shown next to an editorial-roster account's
// display name (T152). Renders nothing when ``isCritic`` is falsy so callers
// can drop it next to every display_name without conditionals.

type Props = {
  isCritic: boolean | undefined | null;
};

export function CriticBadge({ isCritic }: Props) {
  if (!isCritic) return null;
  return (
    <span aria-label="Editorial critic account" className="ml-1 text-muted-foreground">
      · Critic
    </span>
  );
}
