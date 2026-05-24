"use client";

import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Editorial-styled custom toast primitives. The state machine in
 * @/hooks/use-toast is untouched — these primitives just render the
 * toast surface using our tokens. We don't wrap HeroUI's Toast (which
 * uses its own queue system) because the existing app already has a
 * working queue via use-toast.
 */

export type ToastProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: "default" | "destructive";
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  duration?: number;
};

export type ToastActionElement = React.ReactElement;

const ToastContext = React.createContext<{
  variant: "default" | "destructive";
  onClose?: () => void;
}>({ variant: "default" });

const ToastProvider = ({ children }: { children: React.ReactNode }) => <>{children}</>;

const ToastViewport = React.forwardRef<HTMLOListElement, React.HTMLAttributes<HTMLOListElement>>(
  ({ className, ...props }, ref) => (
    <ol
      ref={ref}
      className={cn(
        "pointer-events-none fixed top-4 right-4 z-[100] flex max-h-screen w-full max-w-[420px] flex-col-reverse gap-2 sm:bottom-4 sm:right-4 sm:top-auto sm:flex-col",
        className
      )}
      {...props}
    />
  )
);
ToastViewport.displayName = "ToastViewport";

const Toast = React.forwardRef<HTMLLIElement, ToastProps>(
  ({ className, variant = "default", onOpenChange, children, ...props }, ref) => {
    const onClose = React.useCallback(() => onOpenChange?.(false), [onOpenChange]);
    return (
      <ToastContext.Provider value={{ variant, onClose }}>
        <li
          ref={ref}
          className={cn(
            "pointer-events-auto relative flex w-full items-start gap-3 overflow-hidden rounded-md border p-4 pr-8 transition-all",
            className
          )}
          style={{
            background: variant === "destructive" ? "var(--danger)" : "var(--surface)",
            color: variant === "destructive" ? "var(--danger-foreground)" : "var(--foreground)",
            border:
              variant === "destructive" ? "1px solid var(--danger)" : "1px solid var(--border)",
            boxShadow: "var(--overlay-shadow)",
          }}
          // biome-ignore lint/suspicious/noExplicitAny: rest props from custom ToastProps need any-cast to satisfy <li> attribute types
          {...(props as any)}
        >
          {children}
        </li>
      </ToastContext.Provider>
    );
  }
);
Toast.displayName = "Toast";

const ToastTitle = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-sm font-semibold leading-tight", className)} {...props} />
  )
);
ToastTitle.displayName = "ToastTitle";

const ToastDescription = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-sm opacity-90 leading-snug", className)} {...props} />
  )
);
ToastDescription.displayName = "ToastDescription";

type ToastActionProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  altText?: string;
};

const ToastAction = React.forwardRef<HTMLButtonElement, ToastActionProps>(
  ({ className, altText, "aria-label": ariaLabel, ...props }, ref) => (
    <button
      ref={ref}
      aria-label={ariaLabel ?? altText}
      className={cn(
        "inline-flex h-8 shrink-0 cursor-pointer items-center justify-center rounded-md border bg-transparent px-3 text-sm font-medium transition-colors hover:bg-[color:var(--surface-secondary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--focus)]",
        className
      )}
      style={{ borderColor: "var(--border)" }}
      {...props}
    />
  )
);
ToastAction.displayName = "ToastAction";

const ToastClose = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement>
>(({ className, ...props }, ref) => {
  const { onClose } = React.useContext(ToastContext);
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClose}
      className={cn(
        "absolute right-1 top-1 cursor-pointer rounded-md p-1 opacity-0 transition-opacity hover:opacity-100 focus:opacity-100 focus:outline-none group-hover:opacity-100",
        className
      )}
      style={{ color: "currentColor" }}
      {...props}
    >
      <X className="h-4 w-4" />
    </button>
  );
});
ToastClose.displayName = "ToastClose";

export {
  ToastProvider,
  ToastViewport,
  Toast,
  ToastTitle,
  ToastDescription,
  ToastClose,
  ToastAction,
};
