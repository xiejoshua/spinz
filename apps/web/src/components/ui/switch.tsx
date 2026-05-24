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
 *
 * HeroUI Switch is compound: the parent <Switch> is just the
 * accessible label wrapper; the visible track + thumb must be
 * rendered as <Switch.Control><Switch.Thumb /></Switch.Control>
 * children. Without those children the element renders as a 0×0
 * focusable span — which is exactly what was happening to the
 * notifications toggles ("don't have checkboxes" = no visible
 * control at all).
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
      >
        <HeroSwitch.Control>
          <HeroSwitch.Thumb />
        </HeroSwitch.Control>
      </HeroSwitch>
    );
  }
);
Switch.displayName = "Switch";
