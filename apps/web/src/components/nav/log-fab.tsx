"use client";

import { Button } from "@/components/ui/button";
import { useUiStore } from "@/stores/ui";
import { Plus } from "lucide-react";

export function LogFab() {
  const openLogSheet = useUiStore((s) => s.openLogSheet);
  return (
    <Button
      type="button"
      onClick={() => openLogSheet()}
      size="icon"
      aria-label="Log an album"
      className="fixed bottom-20 right-4 z-40 size-14 rounded-full shadow-lg"
    >
      <Plus className="size-6" aria-hidden="true" />
    </Button>
  );
}
