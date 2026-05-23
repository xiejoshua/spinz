import { zodResolver } from "@hookform/resolvers/zod";
import type { FieldValues, UseFormReturn } from "react-hook-form";

export { zodResolver };

export type ApiErrorPayload = {
  detail?: string | { msg: string; loc?: string[] }[];
};

export function setApiFormErrors<TValues extends FieldValues>(
  form: UseFormReturn<TValues>,
  payload: ApiErrorPayload | undefined
): void {
  if (!payload?.detail) return;
  if (typeof payload.detail === "string") {
    form.setError("root", { message: payload.detail });
    return;
  }
  for (const issue of payload.detail) {
    const field = issue.loc?.find((part) => part !== "body");
    if (field) {
      form.setError(field as never, { message: issue.msg });
    }
  }
}
