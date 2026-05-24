"use client";

import { Chip } from "@heroui/react";
import type * as React from "react";

import { cn } from "@/lib/utils";

type ShadcnVariant = "default" | "secondary" | "destructive" | "outline";

const COLOR_MAP: Record<ShadcnVariant, "default" | "accent" | "danger"> = {
  default: "accent",
  secondary: "default",
  destructive: "danger",
  outline: "default",
};

const VARIANT_MAP: Record<ShadcnVariant, "primary" | "secondary" | "tertiary" | "soft"> = {
  default: "primary",
  secondary: "soft",
  destructive: "primary",
  outline: "secondary",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: ShadcnVariant;
}

function Badge({ className, variant = "default", children, ...props }: BadgeProps) {
  return (
    <Chip
      size="sm"
      color={COLOR_MAP[variant]}
      variant={VARIANT_MAP[variant]}
      className={cn("text-xs font-semibold", className)}
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
      {...(props as any)}
    >
      {children}
    </Chip>
  );
}

export function badgeVariants({
  variant = "default",
  className,
}: { variant?: ShadcnVariant; className?: string } = {}): string {
  return cn(
    "chip",
    "chip--sm",
    `chip--${COLOR_MAP[variant]}`,
    `chip--${VARIANT_MAP[variant]}`,
    className
  );
}

export { Badge };
