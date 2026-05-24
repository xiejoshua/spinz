"use client";

import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import { useMutation } from "@tanstack/react-query";

type ResendResponse = {
  ok: boolean;
  verified?: boolean;
};

/**
 * Shared mutation for POST /api/v1/auth/resend-verification. Used by
 * both the verification banner in (app)/layout.tsx and the Email
 * sub-section on /profile/[handle]/settings so the toast copy +
 * rate-limit handling stay consistent across surfaces.
 *
 * The mutation does NOT flip ``user.email_verified`` in the auth
 * store — the verification still requires the user to click the link
 * in their inbox. The banner / settings copy makes that explicit.
 */
export function useResendVerification() {
  const { toast } = useToast();
  return useMutation({
    mutationFn: async () => apiClient.post<ResendResponse>("/api/v1/auth/resend-verification"),
    onSuccess: () => {
      toast({
        title: "Verification email resent",
        description: "Check your inbox for the new link.",
      });
      capture("auth.verification_resent");
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 429) {
        toast({
          title: "Too many requests",
          description: "Try again later.",
          variant: "destructive",
        });
        return;
      }
      toast({
        title: "Couldn't resend verification email",
        description: "Try again in a moment.",
        variant: "destructive",
      });
    },
  });
}
