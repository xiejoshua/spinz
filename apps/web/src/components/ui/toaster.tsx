"use client";

import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";
import { useToast } from "@/hooks/use-toast";

/**
 * Renders the active toast queue inside the bottom-right viewport.
 *
 * Each <Toast> sits *inside* <ToastViewport> (the editorial <ol>) so
 * the items have a visible anchor. The earlier draft rendered toasts
 * as siblings of the viewport — valid HTML but the toasts had no
 * positioned parent, so on screen nothing ever appeared.
 */
export function Toaster() {
  const { toasts } = useToast();

  return (
    <ToastProvider>
      <ToastViewport>
        {toasts.map(({ id, title, description, action, ...props }) => (
          <Toast key={id} {...props}>
            <div className="flex-1 space-y-0.5">
              {title && <ToastTitle>{title}</ToastTitle>}
              {description && <ToastDescription>{description}</ToastDescription>}
            </div>
            {action}
            <ToastClose />
          </Toast>
        ))}
      </ToastViewport>
    </ToastProvider>
  );
}
