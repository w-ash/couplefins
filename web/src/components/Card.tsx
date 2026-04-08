import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
import { cn } from "@/lib/cn";

type CardElement = "div" | "section" | "form" | "aside";

type CardProps<T extends CardElement = "div"> = {
  children: ReactNode;
  as?: T;
} & ComponentPropsWithoutRef<T>;

export function Card<T extends CardElement = "div">({
  children,
  as,
  className,
  ...props
}: CardProps<T>) {
  const Tag = (as ?? "div") as ElementType;
  return (
    <Tag
      className={cn(
        "rounded-xl border border-border bg-card p-6 shadow-sm",
        className,
      )}
      {...props}
    >
      {children}
    </Tag>
  );
}
