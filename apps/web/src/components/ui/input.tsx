import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Native input styled with our editorial tokens. We don't wrap HeroUI's
 * compound Input here because the call-sites use a flat `<Input>` API.
 */
const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          "flex h-9 w-full rounded-md px-3 py-1 text-sm transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        style={{
          background: "var(--field-background)",
          color: "var(--field-foreground)",
          border: "1px solid var(--field-border)",
          boxShadow: "var(--field-shadow)",
        }}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
