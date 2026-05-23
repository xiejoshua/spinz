"use client";

import { Button } from "@/components/ui/button";
import { ChevronDown, Pencil } from "lucide-react";
import { useState } from "react";

type Props = {
  value: string;
  onChange: (value: string) => void;
};

const MAX_LENGTH = 10_000;

export function ReviewEditor({ value, onChange }: Props) {
  const [expanded, setExpanded] = useState(value.length > 0);

  if (!expanded) {
    return (
      <Button
        type="button"
        variant="ghost"
        onClick={() => setExpanded(true)}
        className="w-full justify-start gap-2 text-muted-foreground"
      >
        <Pencil className="size-4" aria-hidden="true" />
        Add a review
      </Button>
    );
  }

  return (
    <div className="space-y-1">
      <label htmlFor="log-review" className="sr-only">
        Review
      </label>
      <textarea
        id="log-review"
        rows={4}
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, MAX_LENGTH))}
        placeholder="What did you think?"
        className="block w-full resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <button
          type="button"
          onClick={() => {
            onChange("");
            setExpanded(false);
          }}
          className="inline-flex items-center gap-1 hover:text-foreground"
        >
          <ChevronDown className="size-3" aria-hidden="true" />
          Collapse
        </button>
        <span>
          {value.length} / {MAX_LENGTH.toLocaleString()}
        </span>
      </div>
    </div>
  );
}
