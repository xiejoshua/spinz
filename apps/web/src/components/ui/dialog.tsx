"use client";

import { Modal } from "@heroui/react";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Adapter — exposes the shadcn Dialog API surface backed by HeroUI Modal.
 * Call-sites keep using:
 *   <Dialog open onOpenChange>
 *     <DialogContent>
 *       <DialogHeader><DialogTitle/><DialogDescription/></DialogHeader>
 *       …
 *       <DialogFooter>…</DialogFooter>
 *     </DialogContent>
 *   </Dialog>
 */

type DialogProps = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: React.ReactNode;
};

const Dialog = ({ open, onOpenChange, children }: DialogProps) => {
  return (
    <Modal isOpen={open} onOpenChange={onOpenChange}>
      {children}
    </Modal>
  );
};

const DialogTrigger = ({ children }: { children: React.ReactNode; asChild?: boolean }) => {
  return <>{children}</>;
};

const DialogClose = ({ children, ...props }: React.HTMLAttributes<HTMLButtonElement>) => {
  return (
    <button type="button" slot="close" {...props}>
      {children}
    </button>
  );
};

const DialogContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => (
    <Modal.Backdrop>
      <Modal.Container>
        <Modal.Dialog
          // biome-ignore lint/suspicious/noExplicitAny: HeroUI ref type diverges from native HTMLDivElement ref
          ref={ref as any}
          className={cn("relative w-full max-w-lg sm:rounded-lg", className)}
          // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
          {...(props as any)}
        >
          {children}
          <Modal.CloseTrigger className="absolute right-4 top-4 inline-flex h-6 w-6 cursor-pointer items-center justify-center rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--focus)]">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </Modal.CloseTrigger>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  )
);
DialogContent.displayName = "DialogContent";

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <Modal.Header
    className={cn("flex flex-col space-y-1.5 text-left", className)}
    // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
    {...(props as any)}
  />
);
DialogHeader.displayName = "DialogHeader";

const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <Modal.Footer
    className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}
    // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
    {...(props as any)}
  />
);
DialogFooter.displayName = "DialogFooter";

const DialogTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <Modal.Heading
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI ref type diverges from native HTMLHeadingElement ref
      ref={ref as any}
      className={cn("text-lg font-semibold leading-none tracking-tight", className)}
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
      {...(props as any)}
    />
  )
);
DialogTitle.displayName = "DialogTitle";

const DialogDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn("text-sm", className)} style={{ color: "var(--muted)" }} {...props} />
));
DialogDescription.displayName = "DialogDescription";

export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
};
