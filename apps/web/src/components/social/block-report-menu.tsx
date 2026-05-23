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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
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
import type { ProfileResponse } from "@/lib/social-types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MoreVertical } from "lucide-react";
import { useState } from "react";

type BlockReason = "harassment" | "spam" | "impersonation" | "other";
type ReportReason = "harassment" | "spam" | "impersonation" | "hate_speech" | "other";

type Props = {
  handle: string;
  userId: string;
  /** Hide on self / anonymous / already-blocked viewers. */
  visible: boolean;
};

export function BlockReportMenu({ handle, userId, visible }: Props) {
  const [blockOpen, setBlockOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [blockReason, setBlockReason] = useState<BlockReason>("harassment");
  const [blockNotes, setBlockNotes] = useState("");
  const [reportReason, setReportReason] = useState<ReportReason>("harassment");
  const [reportDetail, setReportDetail] = useState("");
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const blockMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post(`/api/v1/users/${encodeURIComponent(handle)}/block`, {
        reason: blockReason,
        notes: blockNotes.trim() || undefined,
      });
    },
    onSuccess: () => {
      capture("social.block", { blockee_handle: handle, reason: blockReason });
      toast({ title: "Blocked", description: `@${handle} can no longer see your activity.` });
      queryClient.setQueryData<ProfileResponse>(["profile", handle], (cur) =>
        cur ? { ...cur, relation: "blocked" } : cur
      );
      void queryClient.invalidateQueries({ queryKey: ["profile", handle] });
      setBlockOpen(false);
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? `Block failed (${error.status}).`
          : "Could not reach the server.";
      toast({ title: "Couldn't block", description: message });
    },
  });

  const reportMutation = useMutation({
    mutationFn: async () => {
      // T155 — backend now persists user reports through to a real
      // Report row. The 404 fallback is no longer needed.
      await apiClient.post("/api/v1/reports/user", {
        user_id: userId,
        reason: reportReason,
        detail: reportDetail.trim() || undefined,
      });
    },
    onSuccess: () => {
      capture("moderation.report_user", { reported_handle: handle, reason: reportReason });
      toast({
        title: "Report received",
        description: "Our team will review and take action if needed.",
      });
      setReportOpen(false);
      setReportDetail("");
    },
    onError: () => {
      toast({ title: "Couldn't send report", description: "Try again later." });
    },
  });

  if (!visible) return null;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label="More actions"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <MoreVertical aria-hidden="true" className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setReportOpen(true)}>Report</DropdownMenuItem>
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onSelect={() => setBlockOpen(true)}
          >
            Block
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={blockOpen} onOpenChange={(v) => (v ? null : setBlockOpen(false))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Block @{handle}?</DialogTitle>
            <DialogDescription>
              They won't be able to see your profile, follow you, or interact with your content. Any
              existing follows between you are dissolved.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="block-reason">Reason</Label>
              <Select value={blockReason} onValueChange={(v) => setBlockReason(v as BlockReason)}>
                <SelectTrigger id="block-reason">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="harassment">Harassment</SelectItem>
                  <SelectItem value="spam">Spam</SelectItem>
                  <SelectItem value="impersonation">Impersonation</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="block-notes">Notes (optional)</Label>
              <Input
                id="block-notes"
                value={blockNotes}
                onChange={(e) => setBlockNotes(e.target.value)}
                placeholder="What happened?"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setBlockOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={blockMutation.isPending}
              onClick={() => {
                blockMutation.mutate();
              }}
            >
              Block
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={reportOpen} onOpenChange={(v) => (v ? null : setReportOpen(false))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Report @{handle}</DialogTitle>
            <DialogDescription>
              Pick a reason and add detail. Reports are reviewed by the moderation team.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="report-reason">Reason</Label>
              <Select
                value={reportReason}
                onValueChange={(v) => setReportReason(v as ReportReason)}
              >
                <SelectTrigger id="report-reason">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="harassment">Harassment</SelectItem>
                  <SelectItem value="spam">Spam</SelectItem>
                  <SelectItem value="impersonation">Impersonation</SelectItem>
                  <SelectItem value="hate_speech">Hate speech</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="report-detail">Detail (optional)</Label>
              <textarea
                id="report-detail"
                value={reportDetail}
                onChange={(e) => setReportDetail(e.target.value)}
                rows={4}
                className="w-full resize-y rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setReportOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={reportMutation.isPending}
              onClick={() => {
                reportMutation.mutate();
              }}
            >
              {reportMutation.isPending ? "Sending…" : "Send report"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
