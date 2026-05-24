"use client";

import { Avatar as HeroAvatar } from "@heroui/react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Adapter — exposes Avatar / AvatarImage / AvatarFallback names for
 * existing call-sites, backed by HeroUI's compound Avatar API.
 */

const Avatar = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => (
    <HeroAvatar
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI ref type diverges from native HTMLDivElement ref
      ref={ref as any}
      className={cn("relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full", className)}
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
      {...(props as any)}
    >
      {children}
    </HeroAvatar>
  )
);
Avatar.displayName = "Avatar";

const AvatarImage = React.forwardRef<HTMLImageElement, React.ImgHTMLAttributes<HTMLImageElement>>(
  ({ className, alt = "", src, ...props }, ref) => (
    <HeroAvatar.Image
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI ref type diverges from native HTMLImageElement ref
      ref={ref as any}
      src={src}
      alt={alt}
      className={cn("aspect-square h-full w-full", className)}
      {...props}
    />
  )
);
AvatarImage.displayName = "AvatarImage";

const AvatarFallback = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => (
    <HeroAvatar.Fallback
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI ref type diverges from native HTMLDivElement ref
      ref={ref as any}
      className={cn("flex h-full w-full items-center justify-center rounded-full", className)}
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
      {...(props as any)}
    >
      {children}
    </HeroAvatar.Fallback>
  )
);
AvatarFallback.displayName = "AvatarFallback";

export { Avatar, AvatarImage, AvatarFallback };
