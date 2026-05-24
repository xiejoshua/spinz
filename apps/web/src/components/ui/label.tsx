import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Native <label> with editorial defaults. Drop-in replacement for the
 * old Radix Label — call-sites only relied on htmlFor + className.
 */
const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    // biome-ignore lint/a11y/noLabelWithoutControl: htmlFor is passed in by call-sites; this primitive cannot know about its target control
    <label
      ref={ref}
      className={cn(
        "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        className
      )}
      style={{ color: "var(--foreground)" }}
      {...props}
    />
  )
);
Label.displayName = "Label";

export { Label };
