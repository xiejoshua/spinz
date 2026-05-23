"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DiaryEntry } from "@/lib/diary-types";
import { useEffect, useState } from "react";

const CONFIRM_TOKEN = "delete";

type Props = {
  entry: DiaryEntry | null;
  onCancel: () => void;
  onConfirm: (entry: DiaryEntry) => void;
};

export function DeleteConfirmation({ entry, onCancel, onConfirm }: Props) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!entry) setTyped("");
  }, [entry]);

  const open = entry != null;
  const matches = typed.trim().toLowerCase() === CONFIRM_TOKEN;

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this diary entry?</DialogTitle>
          <DialogDescription>
            The entry is hidden immediately. You have 30 days to restore it from your trash before
            it’s removed permanently.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="delete-confirm-input">
            Type <span className="font-mono">{CONFIRM_TOKEN}</span> to confirm
          </Label>
          <Input
            id="delete-confirm-input"
            autoFocus
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={CONFIRM_TOKEN}
            autoComplete="off"
          />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={!matches || !entry}
            onClick={() => {
              if (entry && matches) onConfirm(entry);
            }}
          >
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
