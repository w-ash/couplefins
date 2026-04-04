import type { SVGProps } from "react";

const handPaths = [
  "M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2",
  "M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2",
  "M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8",
  "M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15",
];

export function CoupleFinsLogo({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="-8 0 40 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...props}
    >
      {/* Right hand — rotated 45° CW, shifted right */}
      <g transform="translate(8, 0) rotate(45, 12, 12)">
        {handPaths.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
      {/* Left hand — mirrored, shifted left */}
      <g transform="translate(16, 0) scale(-1, 1) rotate(45, 12, 12)">
        {handPaths.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
    </svg>
  );
}
