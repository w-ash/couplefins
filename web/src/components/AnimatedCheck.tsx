interface AnimatedCheckProps {
  size?: number;
  className?: string;
}

export function AnimatedCheck({ size = 48, className }: AnimatedCheckProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 60 60"
      fill="none"
      className={className ? `animated-check ${className}` : "animated-check"}
      aria-hidden="true"
    >
      <circle
        cx="30"
        cy="30"
        r="26.5"
        stroke="var(--primary)"
        strokeWidth="2.5"
        strokeDasharray="166"
        strokeDashoffset="166"
        style={{ animation: "check-circle-draw 400ms ease-out 100ms forwards" }}
      />
      <path
        d="M18 30 L26 38 L42 22"
        stroke="var(--primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="30"
        strokeDashoffset="30"
        style={{ animation: "check-mark-draw 300ms ease-out 350ms forwards" }}
      />
    </svg>
  );
}
