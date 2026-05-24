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
import { useMutation } from "@tanstack/react-query";
import { Flag } from "lucide-react";
import { useState } from "react";

type AlbumReportReason = "wrong_metadata" | "duplicate" | "other";

type Props = {
  albumId: string;
  /** Album title is displayed in the dialog header for clarity. */
  albumTitle: string;
};

/**
 * Album-level "report wrong info" button + dialog (T167).
 *
 * Posts to ``POST /api/v1/reports/album`` which writes a Report row
 * with ``target_type=album`` for the founder-run merge CLI to triage.
 * Success path shows a toast and closes the dialog; 422 / 429 / network
 * errors surface a generic-but-actionable toast.
 */
export function ReportWrongAlbum({ albumId, albumTitle }: Props) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<AlbumReportReason>("wrong_metadata");
  const [detail, setDetail] = useState("");
  const { toast } = useToast();

  const mutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/api/v1/reports/album", {
        album_id: albumId,
        reason,
        detail: detail.trim() || undefined,
      });
    },
    onSuccess: () => {
      capture("album.report_wrong", { album_id: albumId, reason });
      toast({
        title: "Report received",
        description: "Thanks — we'll review and fix the entry.",
      });
      setOpen(false);
      setDetail("");
    },
    onError: (error) => {
      const message =
        error instanceof ApiError && error.status === 429
          ? "You've sent a lot of reports — try again later."
          : "Couldn't send the report. Try again later.";
      toast({ title: "Report failed", description: message });
    },
  });

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="text-xs text-muted-foreground"
        onClick={() => setOpen(true)}
      >
        <Flag aria-hidden="true" className="mr-1 size-3" />
        Report wrong album info
      </Button>
      <Dialog open={open} onOpenChange={(v) => (v ? null : setOpen(false))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Report wrong info on {albumTitle}</DialogTitle>
            <DialogDescription>
              Pick a reason and add detail. Reports feed the moderation queue and the founder
              album-merge tool.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="album-report-reason">Reason</Label>
              <Select value={reason} onValueChange={(v) => setReason(v as AlbumReportReason)}>
                <SelectTrigger id="album-report-reason">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="wrong_metadata">Wrong metadata</SelectItem>
                  <SelectItem value="duplicate">Duplicate album</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="album-report-detail">Detail (optional)</Label>
              <textarea
                id="album-report-detail"
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                rows={4}
                className="w-full resize-y rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                placeholder="What's wrong? If duplicate, share the canonical album id or URL."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Sending…" : "Send report"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
