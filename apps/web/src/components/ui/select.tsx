"use client";

import { Select as HeroSelect, ListBox } from "@heroui/react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Adapter — shadcn Select API backed by HeroUI Select + ListBox.
 *
 *  shadcn:                              HeroUI:
 *  <Select value onValueChange>     →   <Select selectedKey onSelectionChange>
 *    <SelectTrigger>                →     <Select.Trigger>
 *      <SelectValue placeholder/>   →       <Select.Value/>
 *    </SelectTrigger>                       <Select.Indicator/>
 *    <SelectContent>                →     <Select.Popover><ListBox>
 *      <SelectItem value="x">y      →       <ListBox.Item id="x">y</ListBox.Item>
 *    </SelectContent>               →     </ListBox></Select.Popover>
 *  </Select>                            </Select>
 */

type SelectProps = {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
  children?: React.ReactNode;
  name?: string;
};

const SelectRootCtx = React.createContext<{
  placeholder?: string;
  setPlaceholder: (p: string) => void;
}>({ placeholder: undefined, setPlaceholder: () => {} });

const Select = ({ value, defaultValue, onValueChange, disabled, children, name }: SelectProps) => {
  const [placeholder, setPlaceholder] = React.useState<string | undefined>();
  return (
    <SelectRootCtx.Provider value={{ placeholder, setPlaceholder }}>
      <HeroSelect
        selectedKey={value}
        defaultSelectedKey={defaultValue}
        onSelectionChange={(key) => onValueChange?.(key as string)}
        isDisabled={disabled}
        name={name}
        placeholder={placeholder}
      >
        {children}
      </HeroSelect>
    </SelectRootCtx.Provider>
  );
};

const SelectTrigger = React.forwardRef<HTMLButtonElement, React.HTMLAttributes<HTMLButtonElement>>(
  ({ className, children, ...props }, ref) => (
    <HeroSelect.Trigger
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI ref type diverges from native HTMLButtonElement ref
      ref={ref as any}
      className={cn(className)}
      // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
      {...(props as any)}
    >
      {children}
    </HeroSelect.Trigger>
  )
);
SelectTrigger.displayName = "SelectTrigger";

const SelectValue = ({ placeholder }: { placeholder?: string }) => {
  const { setPlaceholder } = React.useContext(SelectRootCtx);
  React.useEffect(() => {
    if (placeholder) setPlaceholder(placeholder);
  }, [placeholder, setPlaceholder]);
  return (
    <>
      <HeroSelect.Value />
      <HeroSelect.Indicator />
    </>
  );
};

const SelectContent = ({
  className,
  children,
}: { className?: string; children?: React.ReactNode }) => (
  <HeroSelect.Popover className={cn(className)}>
    <ListBox>{children}</ListBox>
  </HeroSelect.Popover>
);

type SelectItemProps = {
  value: string;
  children?: React.ReactNode;
  className?: string;
  disabled?: boolean;
};

const SelectItem = ({ value, children, className, disabled }: SelectItemProps) => (
  <ListBox.Item
    id={value}
    isDisabled={disabled}
    className={cn(className)}
    textValue={typeof children === "string" ? children : undefined}
  >
    {children}
    <ListBox.ItemIndicator />
  </ListBox.Item>
);

const SelectGroup = ({ children }: { children?: React.ReactNode }) => (
  <ListBox.Section>{children}</ListBox.Section>
);

const SelectLabel = ({
  children,
  className,
}: { children?: React.ReactNode; className?: string }) => (
  <div className={cn("px-2 py-1.5 text-sm font-semibold", className)}>{children}</div>
);

const SelectSeparator = ({ className }: { className?: string }) => (
  <div className={cn("-mx-1 my-1 h-px", className)} style={{ background: "var(--separator)" }} />
);

export {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectLabel,
  SelectItem,
  SelectSeparator,
};
