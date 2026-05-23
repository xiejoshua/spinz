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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type { Review, ReviewVisibility } from "@/lib/review-types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

const MAX_BODY = 10_000;

type Props = {
  review: Review | null;
  onClose: () => void;
};

export function EditReviewDialog({ review, onClose }: Props) {
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<ReviewVisibility>("public");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (review) {
      setBody(review.body);
      setVisibility(review.visibility);
    } else {
      setBody("");
      setVisibility("public");
    }
  }, [review]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!review) return;
      await apiClient.patch<Review>(`/api/v1/reviews/${encodeURIComponent(review.id)}`, {
        body: body.trim(),
        visibility,
      });
    },
    onSuccess: () => {
      if (!review) return;
      capture("review.edit", { review_id: review.id });
      toast({ title: "Updated", description: "Review updated." });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
      onClose();
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.status === 422
            ? "Review can't be empty after sanitization."
            : error.status === 403
              ? "You can only edit your own reviews."
              : `Update failed (${error.status}).`
          : "Could not reach the server.";
      toast({ title: "Couldn't update", description: message });
    },
  });

  const open = review != null;
  const bodyTooLong = body.length > MAX_BODY;
  const bodyEmpty = body.trim().length === 0;
  const submitDisabled = mutation.isPending || bodyEmpty || bodyTooLong;

  return (
    <Dialog open={open} onOpenChange={(value) => (value ? null : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit review</DialogTitle>
          <DialogDescription>
            Markdown supported: bold (<code>**text**</code>), italic (<code>*text*</code>), line
            breaks. Previous versions are kept internally for 90 days.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="edit-review-body">Review body</Label>
            <textarea
              id="edit-review-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
              className="w-full resize-y rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            <p className="text-right text-xs text-muted-foreground tabular-nums">
              {body.length.toLocaleString()} / {MAX_BODY.toLocaleString()}
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="edit-review-visibility">Visibility</Label>
            <Select value={visibility} onValueChange={(v) => setVisibility(v as ReviewVisibility)}>
              <SelectTrigger id="edit-review-visibility" className="h-9 w-auto px-3 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="public">Public</SelectItem>
                <SelectItem value="followers">Followers only</SelectItem>
                <SelectItem value="private">Private</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            disabled={submitDisabled}
            onClick={() => {
              mutation.mutate();
            }}
          >
            {mutation.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
