"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import { useAuthStore } from "@/stores/auth";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

type DeletionStateResponse = {
  status: string;
  scheduled_for: string | null;
};

export function DataSettings() {
  const router = useRouter();
  const { toast } = useToast();
  const viewer = useAuthStore((s) => s.user);
  const clearUser = useAuthStore((s) => s.clear);

  // The deletion grace banner relies on the user.deletion_scheduled_for
  // field which the auth store doesn't currently carry; the cancel
  // button still calls DELETE /users/me/delete so the user can recover
  // if they hit "delete" but reconsider before navigating away.
  const [scheduledFor, setScheduledFor] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState("");

  // T153 — backend export endpoint returns 202 (Accepted) with a job
  // id; the user receives an email with download URLs when the worker
  // completes (~60s for typical accounts).
  const exportMutation = useMutation({
    mutationFn: async () =>
      apiClient.post<{ job_id: string | null; audit_log_id: string | null; eta_seconds: number }>(
        "/api/v1/users/me/data-export"
      ),
    onSuccess: () => {
      toast({
        title: "Export queued",
        description: "We&rsquo;ll email you when your archive is ready.",
      });
      capture("data.export_requested");
    },
    onError: (error) => {
      toast({
        title: "Could not request export",
        description: error instanceof ApiError ? error.statusText : "Try again later.",
        variant: "destructive",
      });
    },
  });

  const scheduleDeletionMutation = useMutation({
    mutationFn: async () => apiClient.post<DeletionStateResponse>("/api/v1/users/me/delete"),
    onSuccess: (data) => {
      setScheduledFor(data.scheduled_for);
      toast({
        title: "Account scheduled for deletion",
        description: data.scheduled_for
          ? `Your account will be permanently deleted on ${new Date(
              data.scheduled_for
            ).toLocaleDateString()}.`
          : "30-day grace period started.",
      });
      capture("account.deletion_scheduled");
      clearUser();
      router.push("/login");
    },
    onError: (error) => {
      toast({
        title: "Could not schedule deletion",
        description: error instanceof ApiError ? error.statusText : "Try again later.",
        variant: "destructive",
      });
    },
  });

  const cancelDeletionMutation = useMutation({
    mutationFn: async () => apiClient.delete<DeletionStateResponse>("/api/v1/users/me/delete"),
    onSuccess: () => {
      setScheduledFor(null);
      toast({ title: "Deletion cancelled" });
      capture("account.deletion_cancelled");
    },
    onError: (error) => {
      toast({
        title: "Could not cancel",
        description: error instanceof ApiError ? error.statusText : "Try again later.",
        variant: "destructive",
      });
    },
  });

  const canSubmitDelete = deleteConfirm === "DELETE";

  return (
    <div className="space-y-6">
      {scheduledFor && (
        <section className="rounded-md border border-destructive/40 bg-destructive/5 p-4">
          <p className="text-sm font-medium">Account scheduled for deletion</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Your account will be permanently deleted on{" "}
            {new Date(scheduledFor).toLocaleDateString()}. You can cancel any time before then.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => cancelDeletionMutation.mutate()}
            disabled={cancelDeletionMutation.isPending}
          >
            Cancel deletion
          </Button>
        </section>
      )}

      <section className="space-y-2 rounded-md border p-4">
        <h3 className="text-sm font-medium">Export your data</h3>
        <p className="text-xs text-muted-foreground">
          We&rsquo;ll prepare a JSON archive containing your diary entries, reviews, Up Next
          backlog, and profile fields. You&rsquo;ll receive an email when it&rsquo;s ready to
          download.
        </p>
        <Button
          type="button"
          variant="outline"
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending}
        >
          {exportMutation.isPending ? "Requesting…" : "Export my data"}
        </Button>
      </section>

      <section className="space-y-2 rounded-md border border-destructive/30 p-4">
        <h3 className="text-sm font-medium text-destructive">Delete account</h3>
        <p className="text-xs text-muted-foreground">
          Permanently delete your account and all associated data after a 30-day grace period. You
          can cancel during the grace window.
        </p>
        <Dialog>
          <DialogTrigger asChild>
            <Button type="button" variant="destructive">
              Delete my account
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete your account?</DialogTitle>
              <DialogDescription>
                {viewer ? `@${viewer.handle} — ` : ""}
                Type <strong>DELETE</strong> to confirm. Your account will be permanently deleted
                after a 30-day grace period.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="delete-confirm">Confirmation</Label>
              <Input
                id="delete-confirm"
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
                placeholder="DELETE"
                autoComplete="off"
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="destructive"
                disabled={!canSubmitDelete || scheduleDeletionMutation.isPending}
                onClick={() => scheduleDeletionMutation.mutate()}
              >
                {scheduleDeletionMutation.isPending ? "Submitting…" : "Permanently delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </section>
    </div>
  );
}
