"use client";

import { Button as HeroButton, type ButtonProps as HeroButtonProps } from "@heroui/react";
import * as React from "react";

import { cn } from "@/lib/utils";

type ShadcnVariant =
  | "default"
  | "destructive"
  | "outline"
  | "secondary"
  | "ghost"
  | "link";
type ShadcnSize = "default" | "sm" | "lg" | "icon";

const VARIANT_MAP: Record<ShadcnVariant, HeroButtonProps["variant"]> = {
  default: "primary",
  destructive: "danger",
  outline: "outline",
  secondary: "secondary",
  ghost: "ghost",
  link: "ghost",
};

const SIZE_MAP: Record<ShadcnSize, HeroButtonProps["size"]> = {
  default: "md",
  sm: "sm",
  lg: "lg",
  icon: "md",
};

export interface ButtonProps
  extends Omit<
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    "type" | "onClick"
  > {
  variant?: ShadcnVariant;
  size?: ShadcnSize;
  asChild?: boolean;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "default",
      size = "default",
      asChild = false,
      disabled,
      onClick,
      type = "button",
      children,
      ...props
    },
    ref
  ) => {
    const heroVariant = VARIANT_MAP[variant];
    const heroSize = SIZE_MAP[size];
    const isIconOnly = size === "icon";

    if (asChild && React.isValidElement(children)) {
      const child = children as React.ReactElement<Record<string, unknown>>;
      return (
        <HeroButton
          variant={heroVariant}
          size={heroSize}
          isIconOnly={isIconOnly}
          isDisabled={disabled}
          className={cn(
            variant === "link" && "underline-offset-4 hover:underline",
            className
          )}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          render={(injected: any) =>
            React.cloneElement(child, {
              ...injected,
              ...(child.props as Record<string, unknown>),
              className: cn(
                injected?.className as string,
                child.props.className as string
              ),
            })
          }
        />
      );
    }

    return (
      <HeroButton
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ref={ref as any}
        variant={heroVariant}
        size={heroSize}
        isIconOnly={isIconOnly}
        isDisabled={disabled}
        type={type}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onClick={onClick as any}
        className={cn(
          variant === "link" && "underline-offset-4 hover:underline",
          className
        )}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        {...(props as any)}
      >
        {children}
      </HeroButton>
    );
  }
);
Button.displayName = "Button";

export function buttonVariants({
  variant = "default",
  size = "default",
  className,
}: {
  variant?: ShadcnVariant;
  size?: ShadcnSize;
  className?: string;
} = {}): string {
  const v = VARIANT_MAP[variant];
  const s = SIZE_MAP[size];
  const iconOnly = size === "icon";
  return cn(
    "button",
    `button--${s}`,
    `button--${v}`,
    iconOnly && "button--icon-only",
    className
  );
}

export { Button };
