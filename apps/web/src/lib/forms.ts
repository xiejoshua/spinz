import { zodResolver } from "@hookform/resolvers/zod";
import type { FieldValues, UseFormReturn } from "react-hook-form";

export { zodResolver };

type PydanticIssue = { msg: string; loc?: string[] };

// Backend custom error shape (mirrors auth/routes.py `_signup_error_response`):
// `{"error": "weak_password", "message": "password must contain at least one digit"}`
type CustomError = { error: string; message: string; field?: string };

// `detail` is typed `unknown` because the caller (api-client's ApiError)
// stores response bodies as `unknown` — narrowing happens inside the
// helper via the type-guards below.
export type ApiErrorPayload = {
  detail?: unknown;
};

function isPydanticIssueArray(value: unknown): value is PydanticIssue[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        "msg" in item &&
        typeof (item as { msg: unknown }).msg === "string"
    )
  );
}

function isCustomError(value: unknown): value is CustomError {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    "message" in value &&
    typeof (value as { message: unknown }).message === "string"
  );
}

// Route backend error codes to the right form field so users see the
// message under the input instead of as a generic banner.
const ERROR_FIELD_MAP: Record<string, string> = {
  weak_password: "password",
  invalid_email: "email",
  duplicate_email: "email",
  duplicate_handle: "handle",
  invalid_handle: "handle",
  reserved_handle: "handle",
};

export function setApiFormErrors<TValues extends FieldValues>(
  form: UseFormReturn<TValues>,
  payload: ApiErrorPayload | undefined
): void {
  if (!payload?.detail) return;

  // String detail — generic error banner (rare).
  if (typeof payload.detail === "string") {
    form.setError("root", { message: payload.detail });
    return;
  }

  // Backend custom shape: {error, message[, field]} — route to the
  // field it's about (via field map or explicit `field`).
  if (isCustomError(payload.detail)) {
    const field = payload.detail.field ?? ERROR_FIELD_MAP[payload.detail.error];
    if (field) {
      form.setError(field as never, { message: payload.detail.message });
    } else {
      form.setError("root", { message: payload.detail.message });
    }
    return;
  }

  // Pydantic default 422 shape: [{loc, msg, type}, ...]
  if (isPydanticIssueArray(payload.detail)) {
    for (const issue of payload.detail) {
      const field = issue.loc?.find((part) => part !== "body");
      if (field) {
        form.setError(field as never, { message: issue.msg });
      }
    }
  }
}
