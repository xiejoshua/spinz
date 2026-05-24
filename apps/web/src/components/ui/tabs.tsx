"use client";

import { Tabs as HeroTabs } from "@heroui/react";
import type * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Adapter — shadcn Tabs API backed by HeroUI Tabs.
 *  shadcn:                       HeroUI:
 *  value/onValueChange      →    selectedKey/onSelectionChange
 *  <TabsList>               →    <Tabs.ListContainer><Tabs.List>
 *  <TabsTrigger value=x>    →    <Tabs.Tab id=x>
 *  <TabsContent value=x>    →    <Tabs.Panel id=x>
 */

type TabsProps = {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  children?: React.ReactNode;
  className?: string;
};

const Tabs = ({ value, defaultValue, onValueChange, children, className }: TabsProps) => {
  return (
    <HeroTabs
      selectedKey={value}
      defaultSelectedKey={defaultValue}
      onSelectionChange={(key) => onValueChange?.(key as string)}
      className={className}
    >
      {children}
    </HeroTabs>
  );
};

const TabsList = ({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <HeroTabs.ListContainer
    // biome-ignore lint/suspicious/noExplicitAny: HeroUI spread accepts HTML attributes but types diverge
    {...(props as any)}
  >
    <HeroTabs.List className={cn(className)} aria-label="Tabs">
      {children}
    </HeroTabs.List>
  </HeroTabs.ListContainer>
);

type TabsTriggerProps = {
  value: string;
  children?: React.ReactNode;
  className?: string;
  disabled?: boolean;
};

const TabsTrigger = ({ value, children, className, disabled }: TabsTriggerProps) => (
  <HeroTabs.Tab id={value} className={cn(className)} isDisabled={disabled}>
    {children}
    <HeroTabs.Indicator />
  </HeroTabs.Tab>
);

type TabsContentProps = {
  value: string;
  children?: React.ReactNode;
  className?: string;
};

const TabsContent = ({ value, children, className }: TabsContentProps) => (
  <HeroTabs.Panel id={value} className={className}>
    {children}
  </HeroTabs.Panel>
);

export { Tabs, TabsList, TabsTrigger, TabsContent };
