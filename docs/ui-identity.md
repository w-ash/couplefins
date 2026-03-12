# UI Identity

Why this app looks and feels the way it does. For enforcement rules (the *what*), see [`.claude/rules/web-design-system.md`](../.claude/rules/web-design-system.md). For generic design methodology, see [`dev-setup-guide/react-design-identity.md`](dev-setup-guide/react-design-identity.md). For user personas and journeys, see [`user-flows.md`](user-flows.md).

---

## Who This Is For

A tech-comfortable couple who open this app once a month, for about fifteen minutes, to reconcile shared expenses and manage their shared budget together. It replaces a shared spreadsheet. The interface should feel like a well-organized notebook you pull out briefly — calm, personal, trustworthy. Financial data should inform, not stress.

---

## Design Principles

Four beliefs that guide decisions when two valid approaches exist.

### Warm over clinical

Financial apps default to cold precision. This app is about a relationship, not an account balance. Cream backgrounds, teal and coral semantics, Satoshi's humanist geometry, rounded surfaces — every material choice favors warmth over sterility. The palette has a warm shift baked into every neutral (`oklch(... 85)` hue angle), so even dark mode feels warm rather than cold.

### Informative, not alarming

Teal and coral replace green and red. Green/red triggers traffic-light associations — good/bad, go/stop — which turns every expense into a small judgment. Teal and coral communicate direction (positive/negative) without the emotional weight. The settlement card states a fact ("Alice owes Bob $127.50"), not an alert.

### Clarity over density

Two users, once a month. The interface can afford generous whitespace and progressive disclosure because nobody is power-using this eight hours a day. Who-owes-whom is the hero element, not a number buried in a table footer. Category breakdowns expand on demand. Tables show the essential columns, not every field the API returns.

### Presence over authentication

Two named profiles, always visible in the sidebar, switchable in one click. No login wall — this is a trusted-device, two-person tool where authentication adds friction for zero security benefit. The sidebar shows both partners at all times, making the two-person nature of the app spatially obvious even when only one person is using it.

---

## Visual Language

### Typography

**Satoshi** (variable, from Fontshare) handles all UI text — headings, body, buttons, labels. It has the geometric structure financial data needs for precision, and the humanist stroke terminals that give a personal tool its personality. Financial figures use Satoshi with `tabular-nums` for column alignment — not a monospace font, which would feel like a terminal.

**Geist Mono** is scoped strictly to technical identifiers: database IDs, codes, slugs. Never for amounts, dates, or body text.

Inter is explicitly banned. It's the typographic equivalent of no decision — every AI-generated template uses it, and choosing it signals that nobody thought about type.

### Color

The palette uses **OKLCH** throughout — perceptually uniform, so lightness and chroma adjustments behave predictably when building dark mode variants or muted backgrounds.

**Warm neutrals** form the foundation. The background sits at `oklch(0.985 0.003 85)` — not white, not gray, but a subtle cream. Text is `oklch(0.268 0.006 58)` — warm dark gray, not black. This hue-85 warm shift is faint but it prevents the clinical feeling of a gray-on-white spreadsheet. In dark mode, the same warmth carries through at `oklch(0.175 0.006 58)`.

**Teal** (`oklch(0.525 0.105 175)`) serves double duty: primary action color and positive-amount indicator. This creates a natural association — forward actions and positive outcomes share the same visual language.

**Coral** (`oklch(0.577 0.15 27)`) marks negative amounts and destructive actions. The hue sits firmly in coral territory, not alarm-red.

**Amber** (`oklch(0.666 0.14 55)`) handles warnings — the middle lane between teal and coral for states that need attention without urgency.

### Space and rhythm

Generous whitespace signals "take your time" — appropriate for a tool used briefly once a month, where density offers no advantage. Spacing between sections intentionally varies: different content types get different breathing room. Uniform spacing between uniform containers signals template, not craft.

Content widths are capped (`max-w-3xl` to `max-w-5xl`) and centered. The content floats in space rather than stretching edge-to-edge, reinforcing the notebook metaphor.

### Depth and surface

Cards use `rounded-xl` corners, gentle `shadow-sm` shadows, and warm-gray borders. The effect is paper in a notebook, not tiles in a dashboard grid.

The depth system is shallow: flat (page background), raised (cards), and modal/popover. Two to three levels, not a complex elevation hierarchy. Borders are warm gray (`border-border` and `border-border-muted`), never harsh dividers.

### Motion

150ms for color transitions on hover and focus. 200–300ms for layout shifts like expanding sections. Motion confirms that an action registered — it doesn't decorate. No gratuitous animation. This is a monthly-use tool where animation novelty wears off fast and becomes irritation.

---

## Signature Elements

Four things that make this app visually recognizable without a logo.

**The identity toggle.** Both people are visible in the sidebar as compact avatar buttons — colored circles with initials, a pulse dot on the active person. Not a dropdown, not a settings screen. The two-person nature of the app is spatially encoded, always visible, switchable in one click.

**The settlement card.** Who-owes-whom is the first prominent element on the transactions page, styled as a centered statement with the person's name in a colored pill. Settlement is the immediate actionable answer; budget tracking is the longer arc. The settlement card leads because it resolves the session's most time-sensitive question.

**Teal/coral financial semantics.** Every amount in every table and summary is colored: teal for positive, coral for negative. This consistent color language replaces the conventional green/red and becomes a visual fingerprint across the app.

**The sticky action panel.** In the upload flow, the confirm/back actions live in a sidebar that stays fixed alongside scrolling content. No modal, no context-switching — a persistent decision surface that summarizes counts (new, changed, unchanged) while the user reviews details.

---

## Intentional Departures

Where the app breaks convention, and why.

| Convention | What we do instead | Why |
|---|---|---|
| Green/red for money | Teal/coral | Less anxiety. Financial data should inform, not trigger fight-or-flight. |
| Login/auth wall | Two named profiles, no auth | Only two users on a trusted device. Auth adds friction for zero security benefit in a 15-min monthly session. |
| User menu in header or dropdown | Identity toggle in sidebar | Both people always visible. The app's two-person nature is spatially encoded, not hidden behind a menu. |
| White/gray neutral palette | Warm cream and warm dark gray | Notebook feeling, not spreadsheet feeling. Every neutral has a warm hue shift. |
| Modal confirmation for imports | Sticky sidebar action panel | Users can scroll through preview data while the action panel stays visible. No context-switching between preview and confirm. |

## Conventions We Follow

Where the app deliberately follows standard patterns, and why the convention serves us.

| Pattern | Why we follow it |
|---|---|
| Left sidebar navigation | Familiar for data-centric apps. Five pages is few enough that a sidebar doesn't overwhelm. |
| Card-based content sections | Known mental model for grouped information. Cards with warm borders and shadows fit the notebook metaphor. |
| Dark/light mode with system detection | Users expect this. Three-way toggle (system/light/dark) with FOIT prevention covers all preferences. |
| Icon + text label on nav items | Clarity. Icons alone are ambiguous — a gear could mean settings, configuration, or preferences. |
| Form → Preview → Confirm upload flow | Trust-building pattern for data import. Users see what will happen before it happens. |

---

## Anti-Identity

What the app avoids, and what choosing those defaults would signal.

**Inter, Roboto, Open Sans** — "Nobody made a typography decision." Satoshi occupies the same readability tier with actual character.

**Indigo/purple gradients** — The statistical average of "modern web app." This app has no gradients at all — solid warm tones throughout.

**Glassmorphism, frosted glass** — Decorative complexity for its own sake. Depth here comes from subtle shadows and background shifts, not blur filters.

**Uniform card grids** — Identical containers with identical spacing signals template, not craft. Content types get different treatments and rhythm.

**`animate-pulse` skeleton loaders** — Reads as broken, not loading. Loading states use contextual text ("Analyzing transactions...") with a spinner icon.

**Pure black or white** — Breaks the warm palette. The darkest text is `oklch(0.268 ...)`, not `#000`. The lightest background is `oklch(0.985 ...)`, not `#fff`.

**Generic CTAs** — "Submit", "OK", "Confirm" tell the user nothing. Every button label is verb + object: "Upload CSV", "Confirm Import", "Add Group."

**Color-only status** — Inaccessible and ambiguous. Status always combines icon, color, and text label.

---

## Voice and Tone

How the app speaks.

**Plain language.** "Alice's share" not "payer allocation percentage." Domain terms like `payer_percentage` and `reconciliation_period` stay in the code. The UI says "shared," "personal," "split."

**Factual, not celebratory.** "Import Complete" with a summary of what happened, not "Great job!" or confetti. The user performed a routine monthly task, not an achievement.

**Person names, not "you/them."** The settlement card says "Alice owes Bob $127.50", not "You owe your partner." Both people might be looking at the screen together.

**Directional empty states.** "No shared transactions for March 2026" is a fact. "Upload CSVs from both partners to see shared transactions here" is a direction. Use both — state what's missing, then tell the user what to do next.

**No jargon in the UI.** "Shared" and "Personal" (not "tagged" or "reconciled"). "Split" (not "allocation ratio"). "Category group" is about as technical as it gets, and it maps to a visible UI concept the user can point at.
