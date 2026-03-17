---
paths:
  - "web/src/components/**"
  - "web/src/pages/**"
  - "web/src/layouts/**"
---
# Web Design System — Warm Personal Finance

Calm, personal, trustworthy — like a well-organized notebook, not a corporate dashboard.

## Typography
- **NEVER use Inter. It is banned.** Use Satoshi (variable, from Fontshare) for all UI text.
- Financial figures: `font-variant-numeric: tabular-nums`
- Mono (Geist Mono): only for IDs/codes/technical identifiers

## Color
- Backgrounds/surfaces: warm off-white/cream (never pure white or gray)
- Text: warm dark gray (never pure black)
- Positive/income/under-budget: teal (not green). Negative/expense/over-budget: coral (not red)
- Warm accent for primary actions (derived from teal or complementary warm tone)

## Anti-Patterns (never do these)
- No Inter, Roboto, or Open Sans
- No indigo/blue/purple gradients or glassmorphism
- No pure black (#000) or pure white (#fff)
- No uniform card grids with identical spacing
- No blank empty states or generic CTAs ("Submit", "OK")
- No color-only status indicators
- No interactive elements without visible focus state
- No missing loading/error states on async operations

Full reference (spacing, motion, identity, dark mode, accessibility, audit checklist): see `web-design-reference` skill.
