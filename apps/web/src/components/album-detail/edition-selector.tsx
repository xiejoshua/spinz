"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AlbumPayload } from "@/lib/album-types";
import { useRouter } from "next/navigation";

type Props = {
  editions: AlbumPayload[];
  currentId: string;
};

export function EditionSelector({ editions, currentId }: Props) {
  const router = useRouter();
  return (
    <Select
      value={currentId}
      onValueChange={(value) => {
        if (value !== currentId) router.push(`/album/${value}`);
      }}
    >
      <SelectTrigger className="h-8 w-auto px-2 text-xs" aria-label="Switch edition">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {editions.map((edition) => (
          <SelectItem key={edition.id} value={edition.id}>
            {edition.title}
            {edition.release_year ? ` (${edition.release_year})` : ""}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
