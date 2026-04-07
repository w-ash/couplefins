---
paths:
  - "web/src/components/**"
  - "web/src/pages/**"
  - "web/src/layouts/**"
---
# Component Primitives

Use shared building blocks — never hand-roll equivalent styling inline.

- **Buttons**: `<Button>` from `@/components/Button` (variants: primary/secondary/destructive, sizes: default/sm)
- **Inputs**: compose from `baseInputClass` / `selectInputClass` in `@/lib/input-styles`
- **Percent inputs**: `<PercentInput>` component
- **Cards**: top-level `rounded-xl border border-border bg-card p-6 shadow-sm`, nested `rounded-lg`
- **Segmented controls**: `<SegmentedControl>` from `@/components/SegmentedControl` (shapes: rounded/pill, sizes: default/sm)
- **Page header**: `<PageHeader>` — never hand-roll h1 + flex layout
- **Async states**: `<PageLoading>`, `<PageError>`, `<PageEmpty>` from `@/components/PageStates`
- **Stats row**: `<StatsGrid>` component
- **Dialogs**: `<Dialog>` from `@/components/Dialog` (sizes: default/sm). Use `<DialogHeader>` for title + close button, `<DialogFooter>` for action buttons. Confirmation dialogs can use `<Dialog size="sm">` with inline body/footer.
- **Section headers**: compose from `sectionHeadingClass` / `sectionDescriptionClass` in `@/lib/layout`
- **Table header rows**: use `tableHeaderRowClass` from `@/lib/layout` on `<tr>` inside `<thead>`
- **Popovers**: `z-50`, `mt-1.5` offset, single-section `rounded-lg`, multi-section `rounded-xl`
