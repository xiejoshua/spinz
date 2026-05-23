"use client";

import { Input } from "@/components/ui/input";
import { Loader2, Search } from "lucide-react";

type Props = {
  value: string;
  onChange: (value: string) => void;
  loading: boolean;
};

export function SearchInput({ value, onChange, loading }: Props) {
  return (
    <div className="relative">
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        type="search"
        inputMode="search"
        autoFocus
        autoComplete="off"
        spellCheck={false}
        placeholder="Search albums or artists…"
        aria-label="Search albums"
        className="pl-9 pr-10"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {loading && (
        <Loader2
          aria-hidden="true"
          className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin text-muted-foreground"
        />
      )}
    </div>
  );
}
