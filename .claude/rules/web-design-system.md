---
paths:
  - "web/src/components/**"
  - "web/src/pages/**"
---
# Web Design System — Warm Personal Finance

Couplefins is a shared finance tool used monthly by a couple. The interface should feel
calm, personal, and trustworthy — like a well-organized notebook, not a corporate dashboard.
Prioritize clarity and scannability for financial data.

## Typography (enforce strictly)

**NEVER use Inter. It is banned from this project.**

- **UI font (Satoshi)**: all headings, labels, body text, buttons, navigation
- **Numbers (Satoshi tabular)**: financial figures use `font-variant-numeric: tabular-nums` for alignment
- **Mono font (Geist Mono)**: only for IDs, codes, technical identifiers — never for body text or numbers

Load Satoshi as a variable font from Fontshare. Load Geist Mono from Google Fonts or npm.

## Color Palette

### Base (warm neutrals)
- Background: warm off-white/cream (not pure white, not gray)
- Surface: slightly lighter or darker warm neutral for cards/sections
- Text: warm dark gray (not pure black)
- Muted text: medium warm gray

### Semantic (teal/coral)
- Positive/income/under-budget: teal (not green)
- Negative/expense/over-budget: coral (not red)
- Use muted variants for backgrounds, saturated for text/icons

### Accent
- One warm accent color for primary actions (buttons, links, focus states)
- Derive from teal or choose a complementary warm tone

## Spacing & Layout
- Generous whitespace — breathing room between sections
- Vary rhythm between sections (don't uniform-space everything)
- Card-based layout with gentle shadows (not flat, not heavy)
- Rounded corners (rounded-lg / rounded-xl) for a soft feel

## Depth System
- Subtle warm-toned shadows (not pure black shadows)
- 2-3 elevation levels max (flat, raised, modal)
- Borders: subtle, warm gray — not harsh dividers

## Motion
- 150ms for interactions (hover, focus, press)
- 200-300ms for layout transitions (expand, appear)
- Ease-out for entrances, ease-in for exits
- No gratuitous animation — motion should confirm actions

## Anti-Patterns (never do these)
- Never use Inter, Roboto, or Open Sans
- No indigo/blue/purple gradients
- No glassmorphism or frosted glass
- No uniform card grids with identical spacing
- No pure black (#000) or pure white (#fff) — always warm-shifted
- No animate-pulse skeleton loaders
- No native browser form controls unstyled in the design
- No decorative elements that serve no purpose
