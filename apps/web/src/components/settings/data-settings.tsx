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
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import { useAuthStore } from "@/stores/auth";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";

type DeletionStateResponse = {
  status: string;
  scheduled_for: string | null;
};

const DELETE_TOKEN = "DELETE";

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
  const [confirmOpen, setConfirmOpen] = useState(false);
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
        description: "We’ll email you when your archive is ready.",
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

  const canSubmitDelete = deleteConfirm === DELETE_TOKEN;

  return (
    <div className="space-y-14">
      {scheduledFor && (
        <Section
          label="Pending deletion"
          tone="danger"
          description={`Your account will be permanently deleted on ${new Date(
            scheduledFor
          ).toLocaleDateString()}. You can cancel any time before then.`}
        >
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => cancelDeletionMutation.mutate()}
            disabled={cancelDeletionMutation.isPending}
          >
            {cancelDeletionMutation.isPending ? "Cancelling…" : "Cancel deletion"}
          </Button>
        </Section>
      )}

      <Section
        label="Export"
        description="We’ll prepare a JSON archive containing your diary entries, reviews, Up Next backlog, and profile fields. You’ll receive an email when it’s ready to download."
      >
        <Button
          type="button"
          variant="outline"
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending}
        >
          {exportMutation.isPending ? "Requesting…" : "Export my data"}
        </Button>
      </Section>

      <Section
        label="Delete account"
        tone="danger"
        description="Permanently delete your account and all associated data after a 30-day grace period. Diary entries, reviews, backlog, follows, and aux’d cards are all removed when the window closes. You can cancel during the grace window; once the window closes, nothing recovers."
      >
        <Dialog
          open={confirmOpen}
          onOpenChange={(value) => {
            setConfirmOpen(value);
            if (!value) setDeleteConfirm("");
          }}
        >
          <DialogTrigger asChild>
            <Button type="button" variant="destructive">
              Delete my account
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: "11px",
                  letterSpacing: "0.18em",
                  color: "var(--danger)",
                }}
              >
                Permanent deletion
              </div>
              <DialogTitle
                className="mt-3 font-serif font-semibold leading-[1.1] tracking-[-0.015em]"
                style={{
                  fontSize: "clamp(22px, 3vw, 28px)",
                  color: "var(--foreground)",
                  fontFamily: "var(--font-serif)",
                }}
              >
                Delete {viewer ? `@${viewer.handle}` : "your account"}?
              </DialogTitle>
              <div
                className="mt-3 h-px w-12"
                style={{ background: "var(--danger)", opacity: 0.6 }}
              />
              <DialogDescription
                className="pt-3 font-sans text-[14px] leading-[1.6]"
                style={{ color: "var(--muted)" }}
              >
                Your account enters a 30-day grace period. Sign in any time before it closes to
                cancel. Once the window closes, your data is removed for good.
              </DialogDescription>
            </DialogHeader>

            <div className="mt-6 space-y-2">
              <label
                htmlFor="delete-confirm"
                className="block font-mono uppercase"
                style={{
                  fontSize: "11px",
                  letterSpacing: "0.18em",
                  color: "var(--muted)",
                }}
              >
                Type <span style={{ color: "var(--foreground)" }}>{DELETE_TOKEN}</span> to confirm
              </label>
              <input
                id="delete-confirm"
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value.toUpperCase())}
                placeholder={DELETE_TOKEN}
                autoComplete="off"
                spellCheck={false}
                className="block w-full rounded-md px-4 py-3 font-mono text-[15px] tracking-[0.12em] focus:outline-none focus:ring-2"
                style={{
                  background: "var(--field-background)",
                  color: "var(--field-foreground)",
                  border: "1px solid var(--field-border)",
                  // biome-ignore lint/suspicious/noExplicitAny: CSS custom property key needs cast to satisfy React.CSSProperties index signature
                  ["--tw-ring-color" as any]: "var(--danger)",
                }}
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setConfirmOpen(false)}
                disabled={scheduleDeletionMutation.isPending}
              >
                Keep account
              </Button>
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
      </Section>
    </div>
  );
}

/**
 * Editorial section: mono uppercase eyebrow → hairline → description →
 * children. `tone="danger"` colors the eyebrow + hairline in --danger
 * so the destructive section reads as such without resorting to a
 * filled-card shell.
 */
function Section({
  label,
  description,
  tone = "default",
  children,
}: {
  label: string;
  description: string;
  tone?: "default" | "danger";
  children: ReactNode;
}) {
  const eyebrowColor = tone === "danger" ? "var(--danger)" : "var(--muted)";
  const ruleColor = tone === "danger" ? "var(--danger)" : "var(--separator)";
  const ruleOpacity = tone === "danger" ? 0.6 : 1;
  return (
    <section className="space-y-4">
      <div className="space-y-2">
        <h3
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: eyebrowColor,
          }}
        >
          {label}
        </h3>
        <div className="h-px" style={{ background: ruleColor, opacity: ruleOpacity }} />
        <p
          className="pt-1 font-sans text-[14px] leading-[1.55]"
          style={{ color: "var(--muted)", maxWidth: "60ch" }}
        >
          {description}
        </p>
      </div>
      {children}
    </section>
  );
}
