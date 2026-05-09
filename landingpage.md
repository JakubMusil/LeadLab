# Landing page update plan

## Context
- PR #260 is merged. It improved user detail labels, descriptions, activity type localization, and permission code localization.
- Current public landing page is `frontend-spa/src/views/MarketingView.vue` and contains hardcoded English copy.
- Supported frontend locales are `en`, `cs`, `de`, and `pl`; locale coverage is checked by `frontend-spa/scripts/check-locales.mjs`.
- Baseline frontend validation before changes: `npm run type-check` fails on pre-existing TypeScript issues outside the landing page scope.

## Goals
- Keep the existing clean, airy design direction, inspired by simple Czech SaaS/product websites.
- Reframe the landing page for regular business owners, managers, and teams handling customers, tasks, offers, permissions, and agenda.
- Replace hardcoded marketing copy with localized strings in all supported locales.
- Improve UX clarity with stronger navigation labels, concrete benefits, focused feature sections, approachable pricing/trust content, and accessible FAQ behavior.
- Avoid unrelated backend or authenticated-app changes.

## Work plan and progress
- [x] Review PR #260 and note follow-up translation/UX context.
- [x] Inspect the current landing page implementation and localization setup.
- [x] Run baseline frontend validation and record pre-existing failures.
- [x] Add localized landing page copy under a dedicated locale namespace in `en`, `cs`, `de`, and `pl`.
- [x] Refactor `MarketingView.vue` to use localized content instead of hardcoded English strings.
- [x] Update the page structure and copy for a clearer owner/manager-focused story: hero, benefits, workflow, features, trust, pricing/CTA, FAQ, footer.
- [x] Preserve the clean red/white/gray visual style while making the page more spacious and conversion-oriented.
- [x] Check keyboard/accessibility details for links, FAQ controls, and semantic sections.
- [ ] Run locale validation and relevant frontend checks after implementation.
- [ ] Final review and pull request.

Notes: Added the marketing locale namespace with hero, nav, benefits, workflow, features, trust, pricing/CTA, FAQ, and footer copy in all locales. MarketingView refactored to use `useI18n` (`t`/`tm`) for all copy — no hardcoded English remains. Page structure updated: sticky nav with anchors, hero with eyebrow + note, benefits metrics grid, numbered workflow steps, 6 feature cards with heroicons, trust/for-whom + assurances, pricing plans from locale, CTA banner, accessible FAQ (dl/dt/dd with aria-expanded/aria-controls), semantic header/main/footer. Clean red/white/gray design preserved. Pre-existing TypeScript errors in unrelated files remain unchanged.
