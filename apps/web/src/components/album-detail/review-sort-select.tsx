"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useUiStore } from "@/stores/ui";

export function ReviewSortSelect() {
  const feedSort = useUiStore((s) => s.feedSort);
  const setFeedSort = useUiStore((s) => s.setFeedSort);
  return (
    <Select value={feedSort} onValueChange={(v) => setFeedSort(v as typeof feedSort)}>
      <SelectTrigger className="h-8 w-auto px-2 text-xs" aria-label="Sort reviews">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="newest">Newest</SelectItem>
        <SelectItem value="most_liked">Most Liked</SelectItem>
        <SelectItem value="highest_rated">Highest Rated</SelectItem>
      </SelectContent>
    </Select>
  );
}
