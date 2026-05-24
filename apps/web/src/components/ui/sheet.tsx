"use client";

import { Drawer } from "@heroui/react";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Adapter — exposes the shadcn Sheet API surface backed by HeroUI Drawer.
 * The single existing call-site uses side="bottom" (the log sheet).
 */

type SheetProps = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: React.ReactNode;
};

const Sheet = ({ open, onOpenChange, children }: SheetProps) => {
  return (
    <Drawer isOpen={open} onOpenChange={onOpenChange}>
      {children}
    </Drawer>
  );
};

const SheetTrigger = ({ children }: { children: React.ReactNode; asChild?: boolean }) => {
  return <>{children}</>;
};

const SheetClose = ({ children, ...props }: React.HTMLAttributes<HTMLButtonElement>) => {
  return (
    <button type="button" slot="close" {...props}>
      {children}
    </button>
  );
};

type SheetContentProps = React.HTMLAttributes<HTMLDivElement> & {
  side?: "top" | "right" | "bottom" | "left";
};

const SheetContent = React.forwardRef<HTMLDivElement, SheetContentProps>(
  ({ className, children, side = "bottom", ...props }, ref) => {
    // map shadcn `side` → HeroUI Drawer `placement`
    const placement =
      side === "top" ? "top" : side === "left" ? "left" : side === "right" ? "right" : "bottom";
    return (
      <Drawer.Backdrop>
        <Drawer.Content placement={placement}>
          <Drawer.Dialog
            // biome-ignore lint/suspicious/noExplicitAny: HeroUI ref type diverges from native HTMLDivElement ref
            ref={ref as any}
            className={cn(className)}
            // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
            {...(props as any)}
          >
            {children}
            <Drawer.CloseTrigger className="absolute right-4 top-4 inline-flex h-6 w-6 cursor-pointer items-center justify-center rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--focus)]">
              <X className="h-4 w-4" />
              <span className="sr-only">Close</span>
            </Drawer.CloseTrigger>
          </Drawer.Dialog>
        </Drawer.Content>
      </Drawer.Backdrop>
    );
  }
);
SheetContent.displayName = "SheetContent";

const SheetHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <Drawer.Header
    className={cn("flex flex-col space-y-2 text-left", className)}
    // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
    {...(props as any)}
  />
);
SheetHeader.displayName = "SheetHeader";

const SheetFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <Drawer.Footer
    className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}
    // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
    {...(props as any)}
  />
);
SheetFooter.displayName = "SheetFooter";

const SheetTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <Drawer.Heading
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI ref type diverges from native HTMLHeadingElement ref
      ref={ref as any}
      className={cn("text-lg font-semibold leading-none tracking-tight", className)}
      style={{ color: "var(--foreground)" }}
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
      {...(props as any)}
    />
  )
);
SheetTitle.displayName = "SheetTitle";

const SheetDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn("text-sm", className)} style={{ color: "var(--muted)" }} {...props} />
));
SheetDescription.displayName = "SheetDescription";

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
};
