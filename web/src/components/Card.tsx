import type { HTMLAttributes, ReactNode } from "react";

type CardElement = "div" | "section" | "form" | "aside";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  as?: CardElement;
}

const TAG_MAP: Record<CardElement, string> = {
  div: "div",
  section: "section",
  form: "form",
  aside: "aside",
};

export function Card({
  children,
  as: Tag = "div",
  className,
  ...props
}: CardProps) {
  const Element = TAG_MAP[Tag] as CardElement;
  return (
    // @ts-expect-error — polymorphic element type is safe here
    <Element
      className={`rounded-xl border border-border bg-card p-6 shadow-sm ${className ?? ""}`}
      {...props}
    >
      {children}
    </Element>
  );
}
