# Landing page revision plan (v2 — lead-generation focus)

## Context
- Public landing page lives in `frontend-spa/src/views/MarketingView.vue`. All copy is already localized
  under the `marketing.*` namespace in `en`, `cs`, `de`, and `pl` (locale coverage enforced by
  `frontend-spa/scripts/check-locales.mjs`).
- Current structure: sticky nav → hero → benefits/metrics → workflow steps → 6 feature cards →
  trust/for‑whom → pricing (Free + Pro) → bottom CTA → FAQ → footer. Design is clean red/white/gray,
  rounded‑2xl cards, soft borders, accessible FAQ (`dl/dt/dd` + `aria-expanded`).
- Existing language switcher exists only inside the authenticated app (`SettingsView.vue`, lines
  1039–1052) using `setLocale()` from `@/composables/useI18n.ts`. Marketing visitors cannot switch
  language, which blocks the multilingual lead‑gen goal.
- Baseline: `npm run type-check` has pre-existing TypeScript errors outside the landing page scope;
  `npm run check-locales` and `npm run build-only` pass.

## Why a v2 revision (review findings vs. freelo.io)
The current page is solid but reads more like a "documentation home" than a high‑conversion lead‑gen
site. Compared to freelo.io and similar SaaS landings, the following gaps hold back conversion:

1. **No language switcher on the public page.** Multilingual content exists, but visitors can't reach it.
2. **Hero is text‑only and centered.** Missing a product visual (dashboard mockup) and a tighter,
   benefit‑driven headline. Eyebrow says "CRM pro malé týmy" — too narrow for a lead-gen pitch.
3. **No social proof.** No customer logos strip, no testimonials, no usage numbers.
4. **No real lead capture.** Secondary CTA links to the GitHub issue tracker, which is wrong for a
   marketing page; primary CTA goes straight to `/app/register` with no email‑first option.
5. **Benefits section uses metric‑style tiles for non‑metric values** ("Zákazníci", "Úkoly"…). Visually
   confusing — these are categories, not numbers, so they should be presented differently.
6. **Feature cards are flat.** Six identical icon + title + description tiles; freelo.io alternates
   text/visual blocks with screenshots to add scannability and rhythm.
7. **No integrations strip.** LeadLab ships a Fakturoid plugin and email/calendar concepts but the page
   doesn't surface this trust signal.
8. **No "Why LeadLab" / comparison block** that quickly contrasts LeadLab with spreadsheets / generic CRMs.
9. **Pricing has only 2 tiers and lacks an annual toggle** — a small but proven conversion lever.
10. **CTA density is low on long scroll.** A sticky mobile CTA bar would reclaim conversions.
11. **FAQ uses `v-show`** (kept in DOM but invisible), which is fine, but the panel is not
    `hidden`-attribute toggled, so SR users hear collapsed content. Worth a small a11y polish.
12. **Footer is single‑row.** A 3–4 column footer (Product / Resources / Company / Legal) is the
    norm for SaaS lead‑gen pages and gives room for legal/contact links.

## Goals for v2
- Turn the page into a **focused lead‑generation funnel**: clear value prop → proof → product →
  pricing → capture, with multiple low‑friction CTAs.
- Keep the **clean, airy, minimalistic** look (lots of whitespace, soft shadows, rounded‑2xl cards,
  red brand accent on white). Inspired by **freelo.io**: friendly tone, generous spacing, illustrative
  visuals, scroll rhythm via alternating section backgrounds.
- Make the page **fully multilingual on the public side** (EN / CS / DE / PL) with a visible switcher.
- No hardcoded copy — every new string lives under `marketing.*` in all four locale files.
- No backend changes. No auth-app refactors. Page must keep rendering at the same route.

## Scope of changes

### A. Multilingual UX (must-have)
- A1. Add a small public **language switcher** in the sticky nav and in the footer (codes
  `EN / CS / DE / PL`, current language highlighted). Reuse `setLocale()` and `useI18n().locale`.
- A2. Reusable component `frontend-spa/src/components/LanguageSwitcher.vue` (compact button‑group
  variant for nav + minimal dropdown variant for footer), with `aria-label` and keyboard support.

### B. Hero & primary CTA (must-have)
- B1. Stronger benefit headline + supporting subhead. Eyebrow becomes a category badge
  ("CRM & lead workspace" / "CRM a lead workspace").
- B2. Two‑column hero on `md+`: copy left, **visual placeholder** right (CSS/SVG mock of a record
  detail / pipeline board — no external images, just composed Tailwind blocks so it stays light and
  themable). Mobile stays single column, centered.
- B3. **Inline email capture** next to "Get started": email field + "Start free" button submitting to
  `/app/register?email=…` (no new backend endpoint — the register form will pick up the prefill).
- B4. Tertiary "Watch product tour" link with `▶︎` glyph (anchors to `#workflow` for now; future video).
- B5. Hero "social proof" line under the CTA (e.g. "Built for growing service teams" / customer count
  copy that does not over-promise). Soft and honest tone.

### C. Trust & social proof (must-have)
- C1. New **logos / "trusted by" strip** below the hero. Use neutral greyscale text labels in cards
  if no real logos exist yet — keeps the section honest while leaving slots for future logos.
- C2. New **testimonials** section (2–3 quotes with name, role, company). Copy should be plausible
  and clearly framed as illustrative until real testimonials land — i.e. stored as locale keys but
  marked with a `// TODO: replace with real customer quote` Vue comment. Honest framing only.
- C3. New **integrations strip** ("Works with…") with simple labeled chips for Fakturoid, e-mail,
  calendar, CSV import, webhooks. Pure text + heroicon — no third-party logos.

### D. Information architecture & content polish
- D1. Replace the misleading "metrics tiles" in benefits with a proper **benefits row**: 3–4 short
  cards (icon + headline + 1‑sentence outcome). Move category labels into the workflow / features.
- D2. Reframe **workflow** copy as outcomes ("Capture leads in seconds", "Qualify with context", …)
  rather than imperative verbs only. Keep numbered steps + connector visual on `md+`.
- D3. **Features** section: keep 6 cards, alternate two visual sub-blocks (records & pipeline,
  proposals & tasks) using a 2-column "split" pattern between rows for rhythm, freelo-style.
- D4. New **"Why LeadLab" / comparison** mini-block (3 short bullets vs spreadsheets/email).
- D5. **Pricing**: add a Free / Pro / Team (or Pro / Business) annual‑monthly toggle with a "save 2
  months" badge. Keep prices honest and easy to change in the locale files.
- D6. **FAQ**: switch from `v-show` to `v-if` (or add `:hidden` attribute) so collapsed panels are
  hidden from assistive tech; expand from 5 to 7 entries (self-hosting, security/GDPR, data export,
  cancellation, support languages).
- D7. **Footer**: redesign to 4 columns (Product / Resources / Company / Legal) on `md+`, single
  column on mobile, language switcher + copyright on the bottom row.

### E. Conversion polish
- E1. **Sticky mobile CTA bar** (only `<md`) with "Start free" → `/app/register`.
- E2. **Anchor‑aware nav** with `scroll-margin-top` so anchors don't get hidden behind sticky header.
- E3. Section "eyebrow" labels (e.g. "Features", "Pricing") for quicker scanning.

### F. Visuals & motion (light-touch)
- F1. Subtle background gradient blob behind hero (CSS only, `bg-gradient-radial` or absolutely
  positioned soft shape) — kept very light to preserve the airy feel.
- F2. Hover lift on feature & pricing cards (`hover:shadow-md` + `transition`).
- F3. Respect `prefers-reduced-motion` — disable transforms when reduced-motion is set.

### G. Accessibility & semantics
- G1. Verify heading order (`h1 → h2 → h3`), one `h1` only.
- G2. Language switcher: `aria-pressed` on active item, `aria-label="Change language"`.
- G3. Email capture: `<label class="sr-only">`, proper `inputmode="email"`, `autocomplete="email"`,
  HTML5 validation.
- G4. Color contrast: keep text on red brand at WCAG AA (`text-white` on `bg-red-600` is fine).

### H. Localization
- H1. Every new string added to `marketing.*` in `en.json`, `cs.json`, `de.json`, `pl.json`.
- H2. Czech is the source of truth (per product positioning); EN/DE/PL translated from CS.
- H3. `npm run check-locales` must pass — all four locales mirror the same key tree.

### I. Out of scope
- No new backend endpoints, no auth-flow changes, no email‑sending integration.
- No new third-party logos / brand assets (placeholders only).
- No video assets — only a "Watch product tour" anchor link to the workflow section.
- Pre‑existing unrelated TypeScript errors stay as they are.

## Validation
- `npm run check-locales` — must pass (locale parity for new keys).
- `npm run lint` and `npm run test:unit` — must pass.
- `npm run build-only` — must pass.
- `npm run type-check` — should not introduce **new** errors in the touched files; pre-existing
  errors elsewhere remain out of scope.
- Manual smoke of the page in all four locales (CS / EN / DE / PL).

## Delegation
- All implementation is delegated to a subagent task per the user's instruction
  ("deleguj veškerou dílčí práci na subagenty"). The subagent receives this plan as its brief and
  implements sections A–H in a single coherent change, runs validation, and reports back.

## Work plan and progress
- [x] Review PR #260 and prior landing page work; record what already exists.
- [x] Inspect current `MarketingView.vue`, locale files, and `useI18n` / `setLocale` plumbing.
- [x] Compare with freelo.io to identify lead‑generation gaps.
- [x] Capture the v2 plan in this file.
- [ ] Delegate implementation of sections A–H to a subagent.
- [ ] Run `check-locales`, `lint`, `test:unit`, and `build-only` after implementation.
- [ ] Final review and pull request.

