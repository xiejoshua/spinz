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
import type { Review } from "@/lib/review-types";
import { useEffect, useState } from "react";

const CONFIRM_TOKEN = "delete";

type Props = {
  review: Review | null;
  onCancel: () => void;
  onConfirm: (review: Review) => void;
};

export function DeleteReviewConfirmation({ review, onCancel, onConfirm }: Props) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!review) setTyped("");
  }, [review]);

  const open = review != null;
  const matches = typed.trim().toLowerCase() === CONFIRM_TOKEN;

  return (
    <Dialog open={open} onOpenChange={(value) => (value ? null : onCancel())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this review?</DialogTitle>
          <DialogDescription>
            The review is hidden immediately. You have 30 days to recover it from your trash before
            it's removed permanently. Likes on the review are cleared on permanent removal.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="delete-review-confirm-input">
            Type <span className="font-mono">{CONFIRM_TOKEN}</span> to confirm
          </Label>
          <Input
            id="delete-review-confirm-input"
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
            disabled={!matches || !review}
            onClick={() => {
              if (review && matches) onConfirm(review);
            }}
          >
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
