# Cedar visual design context

Status: implemented UI direction with remaining brand proposals
Scope: Vue dashboard, sign-in screen, loading/error states, and browser-generated PDF reports

## Implemented direction — 2026-09-05

The frontend review and browser reassessment were approved for implementation. This section records the resulting UI decisions; the original brand proposal below remains background for unresolved artwork/font decisions.

- Keep white headers and surfaces, Geist interface text, Cedar teal primary actions, and restrained gold attention treatment. A shared `PerformanceHeader.vue` repeats the existing Cedar artwork and back navigation across dashboard, employee, and interpretation routes. All product routes and their headers share the 1920px maximum content width in `web/src/style.css`. Header actions use their own row on phones. No new artwork or full teal header is introduced.
- The dashboard uses two compact summary columns on phones and four on wide screens. Detailed source interpretation remains on its separate route, without a card on the main dashboard. Below the `2xl` table breakpoint, employee cards preserve every KPI plus overall/status, data confidence, separate Data Issues and Performance Alerts counts, and the details action without horizontal scrolling. On wider screens, the dashboard expands to the shared 1920px maximum and the fixed-width table keeps both finding columns visible without horizontal scrolling. Multiword table headers stay on one line, and the Employee sort label aligns with the employee values. The reporting-period filter reserves enough width for its date picker and quick-range buttons before the five operational filters.
- Null chart scores appear as gaps. A visible legend and distinct dash patterns identify series; an expandable table exposes exact backend weekly values and explicit missing-data labels. Chart scope follows backend operational and period filters.
- Employee Details and its shared header align with the dashboard's content width. Report previews use `ReportPreviewContent.vue`: a viewport-bounded modal up to 1400px wide, fixed header/footer regions, and one scrolling content body with non-shrinking cards. The application page itself keeps natural document scrolling.
- Runtime CSS variables in `web/src/style.css` remain the canonical web token source (runtime-owned mapping). The Tailwind `@theme inline` adapter exposes semantic utility colors. `--compliance-foreground: #80520b` supplies readable small compliance labels on pale gold surfaces; `--chart-2: #c18426` remains the line color. The dark label value is `#f1bd64`.
- `Progress.vue` owns the warning tone used for withheld employee data confidence. `style.css` owns global scrollbar colors and reduced-motion behavior. Explicit status text remains mandatory.
- Both PDF generators already use `#078181` and retain their existing rendering in this pass. Their constants still mirror web palette values manually; a shared browser/PDF token export is a future maintenance change requiring PDF visual verification.

See [UX guidelines](ux-guidelines.md) for state and component ownership and [the test handover](handover.md#frontend-verification--2026-09-05) for completed browser checks and verification limits.

Remaining follow-ups include sign-in refinements, official compact/reversed logo artwork, PDF token consolidation and layout verification, and measured bundle splitting. Condensing employee explanations and grouping multiple source schemas remain optional; preserve all evidence text and backend meaning when revisiting them.

### Reconciliation with the original proposal

| Original observation/proposal | Current evidence | Resolution |
| --- | --- | --- |
| Generic blue controls and placeholder identity | Runtime already used Cedar teal and supplied PNG before this pass | Preserve implemented branding; the baseline descriptions below are historical |
| PDF dark green `#174C3C` | Both generators already use `#078181` | No PDF palette change needed |
| Predominantly white dashboard | Confirmed readable in desktop/mobile review | Retain white header; improve shared identity and density |
| Gold chart and label treatment | Small ochre labels lacked normal-text contrast | Separate readable text foreground from chart-line color |

## Employee evidence tables — 2026-09-14

Employee Details replaces its three standalone KPI score cards with three full-width evidence sections, ordered Productivity, Compliance, and Quality. Each header retains the backend score and overall weight with a short performance-record description. On Employee Details, a small help icon beside “evidence” in each KPI heading opens that KPI's calculation sentence in a floating panel; the report preview omits these icons. There is no separate calculation card. Overall result and data confidence retain their existing sections.

Desktop uses semantic tables; phones use labeled record cards showing the same independently paginated records. Shared `EmployeeEvidenceTable.vue` and `EvidenceRecordDetails.vue` own both Employee Details and report preview presentation. IDs and text wrap, and shared Collapsible controls reveal full values, findings, scoring impacts, and safe evidence links.

The evidence sections reuse the main dashboard table's white card, compact table,
muted range-and-page-size footer, and outline page controls. Each KPI defaults to five
rows and offers 15, 30, or All. The report preview uses those display options while
retaining the complete employee/KPI record set for PDF export.

The approved table simplification combines related dates/IDs and first-pass/rework fields,
moves secondary source values into View record, and gives backend findings and exclusions
a dedicated Issues column. `EvidenceRecordIssues.vue` shares issue presentation between
desktop tables and mobile cards. Existing Cedar tokens, Geist typography, natural page
scrolling, pagination, complete record disclosures, and the downloaded PDF layout remain.

Record-specific Needs attention cards are replaced by table-local affected-record counts,
All records / Needs review controls, plain finding labels, and restrained gold row
emphasis. Attendance disclosures expose scheduled/actual times individually and mark
missing fields identified by backend findings. Shared table and record components own
the same behavior on page, mobile cards, and report preview; PDF layout stays unchanged.

Background evidence requests preserve the existing record surface. A reserved small
status line and delayed spinner communicate longer updates without moving table rows.
Shared controls expose an opt-in busy presentation that keeps opacity stable while
preserving disabled behavior; ordinary disabled states retain their existing treatment.

The portrait employee PDF presents scores, Data Issues, Performance Alerts, and trends, followed by complete performance records; formula explanations and metric definitions are omitted. Section titles and column headings repeat on continuation pages; ordinary records stay together and oversized notes may flow across pages. The existing PDF palette is preserved. Each finding states a review action, and dashboard rows count the two categories separately.

See [evidence read contracts](persistence.md#employee-evidence-reads) and
[implementation verification](ux-guidelines.md#employee-review-verification--2026-09-14).

## Employee weekly trends — 2026-09-15

The home dashboard, Employee Details, and employee report preview share one weekly KPI chart
component. Employee Details loads the backend's existing dashboard trend contract with the
employee ID and active resolved dates; the report preview uses the employee-scoped trend points
in its snapshot. All three views retain Cedar's teal Productivity, gold Compliance, and dark
Quality series, the visible legend, missing-score gaps, and an expandable exact-values table.

The browser-generated employee PDF draws those same snapshot points as a compact vector chart
above its weekly-values table. It labels the score scale and series patterns, shows isolated
points without joining across missing weeks, and preserves the separate evidence appendix.
Insufficient-data reports keep the overall result withheld while showing auditable component
trends.

## Reporting date range — 2026-09-15

The shared `ReportingPeriodPicker.vue` is used inside the call-center filter console
described below. The console adds visible Today, This week, and This month shortcuts.

The dashboard period control opens a compact dialog with quick ranges beside a two-month
shadcn-vue RangeCalendar on desktop; phones show one month and stack the controls. Calendar
range interiors use Cedar's pale teal secondary surface, endpoints use primary teal, and the
quick-range selection uses the shared ToggleGroup's brand tone. Date text fields offer typed
DD/MM/YYYY entry without a browser-native calendar popup. The existing white surfaces, Geist
type, semantic borders, focus ring, and restrained gold attention treatment remain.

The range highlighted in the dialog is a preview. The backend resolves rolling Last month,
Last 6 months, and Last year presets against the latest evidence date and calculates the
committed filtered response. Explicit custom ranges use inclusive UTC dates; setting both
dates equal selects one day. The selected label changes with the successful response, and
short ranges keep the existing insufficient-data status when evidence
confidence is low.
Screens and browser-generated PDFs display dates as DD/MM/YYYY; API values remain ISO dates.

When a preset extends before the first canonical evidence date, the calendar preview keeps
the full selected range. The dialog names the chosen preset and explains the missing earlier
records. The calendar and typed custom dates also allow dates outside evidence coverage.
After Apply, the dashboard badge retains the full selected dates; a separate note shows the
available date window used for scores. Employee details and report previews preserve that
same distinction.

## Call-center dashboard filters — 2026-09-23

The main dashboard is now framed as a call-center performance overview. Its operational
filter console follows the supplied dashboard reference while preserving Cedar's white,
teal, black, and restrained-gold system. `CallCenterFilterBar.vue` owns the dashboard's
Reporting period, Campaign, Queue, Shift, Supervisor, and Location controls. The console
uses the shared authored Select primitive, compact labeled fields, and a single bordered
surface rather than adding a new visual language.

Reporting period opens the shared Cedar date-range picker with a two-month calendar on
desktop, a one-month calendar on phones, and typed `DD/MM/YYYY` dates. Today, This week,
and This month remain visible beside it. The quick ranges anchor to the latest canonical
evidence date and send explicit inclusive ISO start/end dates. On phones, controls reflow
without losing labels or actions.

The five operational dimensions are optional canonical employee-profile fields. When a
source does not provide a dimension, its selector contains only the corresponding All
option; the interface never invents a campaign, queue, shift, supervisor, or location.
Filter changes continue to retain the last successful response during loading and failure.
Employee Results now presents Campaign / Queue in place of Team on the main dashboard;
the existing team and employee API filters remain available for compatibility and reports.

## KPI summary and breakdown — 2026-09-23

The four summary cards retain the compact two-column phone and four-column desktop layout.
Each shows the backend average for employees eligible for an overall result, along with the
scored and withheld populations. The three KPI cards show their overall weights and separate
download and View breakdown actions. The overall card states the 100% evidence requirement.

One panel below the cards shows the selected KPI's backend-calculated average component
scores and documented weights. Tabs switch between Productivity, Compliance, and Quality;
selecting the open card again collapses the panel. The panel uses the same white surfaces,
Geist text, Cedar marker colors, and semantic table treatment as the dashboard. Missing
scores appear as dashes. The UI does not imply a universal KPI target, prior-period delta,
or benchmark when none is defined by the backend.

## Original brand proposal and unresolved assets

## Goal

Bring the Cedar Digital Solutions identity into the performance app without reducing readability or making KPI and status colors ambiguous. The supplied teal Cedar logo is the proposed product logo. The accompanying brand board supplies five base colors: teal, golden yellow, black, white, and a light gray.

The following proposal does not replace source artwork. Unresolved fonts, official gray, and alternate logo assets remain proposals; the implemented direction above records the approved UI scope.


Recommended asset set:

- `cedar-logo-lockup-teal.png`: transparent full lockup for sign-in and report previews.
- `cedar-mark-teal.png`: transparent circuit-tree mark for compact headers and icons.
- A future SVG export from the original designer is preferable for sharp scaling. Do not auto-trace the PNG if official vector artwork is available.

Every visible logo image should have meaningful alternative text such as `Cedar Digital Solutions`; a decorative duplicate should use an empty `alt` value.

## Brand palette

| Token name | Source value | Proposed role | Usage constraint |
| --- | --- | --- | --- |
| Cedar teal | `#078181` | Primary actions, links, focus ring, active controls, logo, primary chart series | Use white text on solid teal. Avoid large areas of saturated teal behind dense content. |
| Golden yellow | `#F1BD64` | Highlights, selected summaries, callouts, and a secondary chart series | Use black text. Do not use gold text on white or treat gold as the only warning signal. |
| Cedar black | `#0D0D0D` | Main text, dark surfaces, and the darkest chart series | Prefer this softened black over pure `#000000` for normal UI text. |
| White | `#FFFFFF` | Page and card surfaces, text on teal/black | Keep the main dashboard predominantly white for clarity. |
| Cedar gray | approximately `#C5C7C6` | Borders, dividers, disabled controls, and quiet surfaces | The brand board does not print a hex value for this color. Confirm the official value before implementation; the value here is a visual estimate from the supplied JPEG. |

Tints and shades derived from these five base colors are allowed for UI states. They should be generated consistently, not introduced as unrelated accent colors. Examples include a very light teal surface for selected rows and a pale gold surface for attention callouts.

## Recommended color hierarchy

The app should feel white and spacious first, teal-branded second, and gold-accented third. Black provides the reading contrast; gray stays structural rather than decorative.

Approximate distribution for a typical dashboard screen:

- 70–80% white and near-white surfaces.
- 10–15% black and gray typography, borders, and structure.
- 5–10% teal for identity, actions, links, progress, and selected states.
- Less than 5% gold for emphasis and attention.

Gold should remain scarce. If it appears on every card, it stops communicating emphasis and the dashboard becomes visually noisy.

## Semantic token proposal

The app already uses shadcn-vue semantic tokens in `web/src/style.css`. Replacing token values is preferable to scattering brand hex codes through Vue components.

| Existing semantic token | Proposed brand mapping |
| --- | --- |
| `background`, `card`, `popover` | White |
| `foreground`, `card-foreground`, `popover-foreground` | Cedar black |
| `primary`, `ring`, `sidebar-primary` | Cedar teal |
| `primary-foreground` | White |
| `accent` | Golden yellow or a pale derived gold tint, depending on component size |
| `accent-foreground` | Cedar black |
| `secondary` | Very light derived teal tint |
| `secondary-foreground` | Cedar black |
| `muted` | Very light gray tint made from Cedar gray and white |
| `muted-foreground` | Dark neutral derived from Cedar black and gray |
| `border`, `input`, `sidebar-border` | Cedar gray, usually as a lighter tint |
| `chart-1` | Cedar teal — Productivity |
| `chart-2` | Golden yellow — Compliance |
| `chart-3` | Cedar black — Quality |

The KPI mapping above is a presentation convention only. It does not change KPI meaning, formulas, weights, or backend data.

### Status colors

The five brand colors are not a complete semantic status system. Destructive errors should keep a dedicated accessible red, because rendering an error in teal or gold would blur its meaning. Status must also be communicated with text and icons, never color alone.

- Success/scored: teal treatment plus explicit label.
- Attention/insufficient data: pale gold background, black text, warning icon, and explicit label.
- Error/destructive: existing semantic red, with accessible foreground contrast.
- Neutral/informational: gray or pale teal treatment plus explicit label.

`Insufficient data` must continue to look distinct from a low score. Branding must not weaken the product's evidence-confidence guardrail.

## Logo placement

### Sign-in screen

- Replace the lock icon above `Welcome back` with the full Cedar lockup.
- Target a displayed width around `180–220px`; preserve the original aspect ratio.
- Keep generous clear space around the lockup, at least the visual width of the `C` in `CEDAR`.
- Use a white or very light gray page background so the teal artwork remains crisp.
- Keep the sign-in button solid teal with white text.

### Dashboard header

- Replace the shield tile with the compact Cedar mark.
- Use a mark height around `32–36px` and retain the adjacent `Performance dashboard` title.
- Do not squeeze the full lockup and tagline into the current 36px header slot.
- Keep the report action as the primary teal button; gold is not appropriate for the most common action.

### Browser icon

- Use the supplied Cedar logo artwork as the browser favicon so the product remains identifiable in tabs and bookmarks.
- Replace the raster favicon with an official compact SVG mark when Cedar provides one; do not recreate or auto-trace the mark.

### Detail and interpretation pages

- Repeat the compact mark only in a persistent product header, if one is introduced.
- Do not place a large logo inside every card or section. Brand continuity should come from tokens and typography.

### PDF reports

- Replace the text-only `CEDAR` header with an optimized logo lockup if pdfmake image quality and bundle size are acceptable.
- Until that is verified, use teal `CEDAR` text as a reliable fallback.
- The PDF generators now use Cedar teal `#078181`. A shared token export could replace manually mirrored constants after PDF verification.
- Use gold only for small emphasis areas and attention notices; preserve black text and printable contrast.

## Component-level application

| Area | Historical pre-branding baseline | Proposed Cedar treatment |
| --- | --- | --- |
| Sign-in identity | Generic lock icon | Full Cedar lockup on a calm white/gray field |
| Dashboard identity | Shield icon in a blue primary tile | Compact teal Cedar mark and black title text |
| Primary buttons | Generic blue | Cedar teal with white text and a visible teal focus ring |
| Cards and tables | White with neutral borders | Keep white; introduce Cedar gray borders and pale teal selected/hover states |
| KPI summary cards | Generic primary/chart colors | Teal, gold, and black indicators with text labels and consistent ordering |
| Trend chart | Generic blue/purple palette | Teal Productivity, gold Compliance, black Quality; also retain legend labels and distinguishable markers/dash patterns |
| Progress/confidence | Generic primary | Teal when sufficient; gold attention treatment below the threshold, always accompanied by the percentage/status text |
| Warnings | Generic warning | Pale gold surface with black text and warning icon |
| PDF exports | Separate dark-green palette | Match the browser palette and introduce the supplied lockup after render verification |

## Typography

The brand board mentions `Isonorm-Regular`, while the web app currently loads Geist. The proposed first pass keeps Geist for all interface text because it is already configured and is more suitable for dense tables, percentages, and form controls.

Isonorm should be considered only if Cedar owns an appropriate webfont license and can provide official font files. If supplied, it could be limited to brand display headings; body copy, controls, and numeric tables should remain Geist. The wordmark inside the logo must not be recreated with a substitute font.

## Accessibility and data-visualization rules

- Verify every foreground/background pair against WCAG AA before implementation. Normal text needs at least 4.5:1 contrast and large text at least 3:1.
- Gold should normally be a background with Cedar black text, not foreground text on white.
- Do not rely on the three KPI colors alone. Keep labels in legends/tooltips and add markers or line patterns where supported.
- Preserve visible keyboard focus using the teal ring with sufficient contrast against both white and gold surfaces.
- Test color-blind legibility for trend charts, status badges, and confidence indicators.
- Check the logo at actual display sizes on desktop and mobile; the tagline should never be rendered at an unreadable size.
- Print-test reports in color and grayscale before adopting the palette in PDFs.

## Dark mode

The stylesheet contains dark-mode tokens, but the current UI does not expose a theme control. The safest first implementation is to complete and verify the light Cedar theme. If dark mode is later enabled, it should deliberately use Cedar black as the background, white text, teal primary actions, gold highlights, and a lighter gray for borders. The existing generic blue dark theme should not be exposed as if it were the Cedar theme.

## Proposed implementation sequence

1. Confirm the official Cedar gray hex value and whether Isonorm webfont files are licensed and available.
2. Prepare transparent, tightly cropped full-lockup and compact-mark logo assets from the supplied master image, or obtain official SVG versions.
3. Update the semantic tokens in `web/src/style.css`, including chart, focus, success, warning, and border behavior.
4. Replace the sign-in and dashboard placeholder icons with the appropriate logo variants.
5. Review summary cards, badges, progress bars, tables, links, and charts in desktop and mobile layouts.
6. Align both PDF generators with the approved palette and test scored and insufficient-data reports visually.
7. Run the frontend production build and complete contrast, keyboard, responsive, and grayscale checks.

## Decisions needed before implementation

1. Is the central light gray's official hex value available, or should the estimated value be sampled and adopted?
2. Can Cedar provide transparent PNG or SVG versions of the full lockup and standalone circuit-tree mark?
3. Should the logo tagline appear on the sign-in screen only, or also in the dashboard header?
4. Is Isonorm licensed for web embedding, or should the application keep Geist throughout?
5. Is a Cedar-branded dark mode required now, or should the initial implementation remain light-only?

## Acceptance criteria for the eventual implementation

- The supplied Cedar artwork, not a generic icon or recreated wordmark, is used for primary product identity.
- Semantic theme tokens control the palette; ordinary components do not hard-code brand colors.
- Browser UI and PDF reports use the approved Cedar teal and the same visual hierarchy.
- Gold is used as an accent/attention color with readable black text.
- Error, warning, success, selected, disabled, and insufficient-data states remain unambiguous without relying on color alone.
- Charts remain understandable in color, for common color-vision deficiencies, and in grayscale exports.
- The app passes `pnpm build` and is visually checked at relevant desktop and mobile sizes.

## Performance-first employee review — 2026-09-14

Remove the Compliance calculation card and replace standalone Findings with compact Needs attention above the three tables. Show three issue groups initially, with Show all/Show fewer controls; hide the section when no relevant issues remain. Preserve white surfaces and existing status treatments. Shared EmployeeAttentionSummary/EmployeeAttentionItem and EmployeeCalculationDetails components serve both page and report preview. Detailed calculations remain collapsed by default at the end of each view.
