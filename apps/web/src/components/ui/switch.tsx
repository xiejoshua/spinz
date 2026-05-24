"use client";

import { Switch as HeroSwitch } from "@heroui/react";
import * as React from "react";

import { cn } from "@/lib/utils";

export type SwitchProps = {
  checked: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  id?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  className?: string;
};

/**
 * Adapter — maps shadcn's `checked` / `onCheckedChange` to HeroUI's
 * React Aria `isSelected` / `onChange`.
 */
export const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
  ({ checked, onCheckedChange, disabled, className, ...rest }, ref) => {
    return (
      <HeroSwitch
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ref={ref as any}
        isSelected={checked}
        onChange={onCheckedChange}
        isDisabled={disabled}
        className={cn(className)}
        {...rest}
      />
    );
  }
);
Switch.displayName = "Switch";
