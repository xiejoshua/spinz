"use client";

import { Dropdown, Menu } from "@heroui/react";
import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Adapter — shadcn DropdownMenu API backed by HeroUI Dropdown + Menu.
 */

const DropdownMenu = ({ children }: { children?: React.ReactNode }) => (
  <Dropdown>{children}</Dropdown>
);

const DropdownMenuTrigger = ({ children }: { children?: React.ReactNode; asChild?: boolean }) => {
  return <>{children}</>;
};

const DropdownMenuPortal = ({ children }: { children?: React.ReactNode }) => <>{children}</>;

type DropdownMenuContentProps = {
  children?: React.ReactNode;
  className?: string;
  align?: "start" | "center" | "end";
  sideOffset?: number;
};

const DropdownMenuContent = ({ children, className, align }: DropdownMenuContentProps) => (
  <Dropdown.Popover
    className={cn(className)}
    placement={align === "end" ? "bottom right" : align === "center" ? "bottom" : "bottom left"}
  >
    <Menu>{children}</Menu>
  </Dropdown.Popover>
);

type DropdownMenuItemProps = {
  children?: React.ReactNode;
  onSelect?: () => void;
  asChild?: boolean;
  className?: string;
  disabled?: boolean;
};

const DropdownMenuItem = ({ children, onSelect, className, disabled }: DropdownMenuItemProps) => (
  <Menu.Item className={cn(className)} isDisabled={disabled} onAction={onSelect}>
    {children}
  </Menu.Item>
);

const DropdownMenuLabel = ({
  children,
  className,
}: { children?: React.ReactNode; className?: string }) => (
  <div className={cn("px-2 py-1.5 text-sm font-semibold", className)}>{children}</div>
);

const DropdownMenuSeparator = ({ className }: { className?: string }) => (
  <div className={cn("-mx-1 my-1 h-px", className)} style={{ background: "var(--separator)" }} />
);

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuPortal,
};
