# Project Goals

This document describes the vision, design principles, and planned milestones for LeadLab.

---

## Vision

LeadLab aims to be a lightweight, developer-first multi-tenant CRM backend that small agencies and sales teams can self-host or extend without fighting a monolithic commercial platform. The codebase should remain small enough that a single developer can understand it end-to-end, while still being production-ready.

---

## Design Principles

1. **Multi-tenancy first** — All data is strictly scoped to a Firm. There must be no possibility of data leaking between tenants at the ORM or API layer.
2. **Explicit over implicit** — Permission checks (`require_membership`, `require_active_subscription`) are called at the top of every endpoint; middleware only resolves the current Firm, it never silently allows or denies requests.
3. **Thin models, fat API** — Business logic lives in the API layer (transactions, side-effects such as activity logging, Celery dispatch) rather than in model `save()` overrides, making the flow easy to trace.
4. **Graceful degradation** — Optional services (Celery, Redis, S3, Stripe) should never cause hard failures when not configured; the application should log and continue.
5. **API-first** — The project exposes a documented REST API (Django Ninja / OpenAPI) as its primary interface. A lightweight Django-rendered frontend is provided as a convenience layer on top of this API.

---

## Current Status

The following core features are implemented and tested:

- [x] Custom email-based user model with timezone support
- [x] Firm (tenant) model with auto-slug generation and Stripe fields
- [x] Membership model with Owner / Admin / Worker roles
- [x] Tenant middleware — resolves the active Firm from the `X-Firm-ID` request header
- [x] Role-based auth helpers (`require_membership`, `require_active_subscription`)
- [x] Customer (address book) CRUD with tag and metadata support
- [x] Lead pipeline with status transitions and automatic `STATUS_CHANGE` activity logging
- [x] Activity timeline — unified action hub supporting comments, calls, meetings, emails, file uploads, and task events
- [x] Task management with automatic `TASK_ASSIGNED` / `TASK_COMPLETED` activity logging
- [x] Async outbound email dispatch via Celery
- [x] Django admin registration for all models
- [x] OpenAPI docs at `/api/v1/docs`

---

## Planned Milestones

### v0.2 — Polish & Coverage
- [x] Add comprehensive unit and integration tests for all API endpoints
- [x] Add pagination support to list endpoints (customers, leads, tasks)
- [x] Implement lead filtering by date range, source, and tag
- [x] Improve search across customers (company name, phone)

### v0.3 — Invitations & Onboarding
- [x] Email-based invitation flow (send invite link, accept, create account)
- [x] Password reset via email
- [x] User profile update endpoint (name, timezone, avatar upload)

### v0.4 — Stripe Integration
- [x] Stripe Checkout session creation for upgrading to Pro
- [x] Stripe webhook handler for subscription lifecycle events (activated, cancelled, payment failed)
- [x] Usage limits per subscription tier (e.g. max leads on Free plan)

### v0.5 — Files & Attachments
- [x] File attachment list and delete endpoints scoped to a Lead

### v0.6 — Reporting
- [x] Lead pipeline summary endpoint (counts per status, total value)
- [x] Activity feed endpoint across all leads for a Firm
- [x] Task overdue report

### v1.0 — Production Hardening
- [x] Docker Compose setup for local development (Postgres, Redis, app, worker)
- [x] Rate limiting on authentication endpoints
- [x] Comprehensive logging and error tracking integration (Sentry)
- [x] Health check endpoint for load balancer probes
- [x] CI/CD pipeline with linting, tests, and coverage reporting

### v1.1 — Built-in Frontend
- [x] Landing page with branding and call-to-action
- [x] Registration and login pages with client-side validation
- [x] Forgot password and password reset pages
- [x] Email-based invitation acceptance page (supports new and existing users)
- [x] Post-registration onboarding flow with workspace creation
- [x] Dashboard overview with live stats (leads, customers, tasks, pipeline value) and Chart.js bar chart
- [x] Leads list page with status filter, create/edit modal, delete, and inline activity timeline
- [x] Standalone lead detail page with edit, status update, tasks, file attachments, and paginated activity timeline
- [x] Customers list page with live search, create/edit modal, and delete
- [x] Standalone customer detail page with contact info, tags, metadata, and mailto/tel quick actions
- [x] Task calendar page (FullCalendar) with overdue/upcoming task panels and task creation form
- [x] Team page with member list, role badges, member removal, and invite form
- [x] Settings page with profile display, workspace info, new workspace creation, and sign-out
- [x] Responsive sidebar layout with active nav highlighting, global lead search, and notification dropdown
- [x] Multi-workspace selector with automatic firmId persistence via localStorage
- [x] Toast notifications and global JS error boundary

---

## Road to v2.0 — Commercial-Grade LeadLab

The v2.0 milestone transforms LeadLab from a solid developer-first backend with a convenience frontend into a fully polished, commercially deployable SaaS product. The single biggest architectural shift is the migration from Django-rendered templates with vanilla JS to a **Vue 3 Single-Page Application (SPA)** served by the same Django backend. Every new milestone below builds on the previous one in a way that allows the existing v1.1 templates to remain functional until the replacement is feature-complete.

### Why Vue 3?

The current frontend is already API-first — every page bootstraps by calling the Django Ninja REST API and renders UI via vanilla JS string templates. This is essentially a hand-rolled SPA without a framework. Vue 3 formalises that pattern with:

- **Reactivity** — state changes automatically re-render only the affected DOM nodes; no more manual `innerHTML` rebuilds.
- **Component model** — reusable, testable UI units replace duplicated HTML across template files.
- **Pinia** — lightweight, TypeScript-friendly store that replaces scattered `localStorage` and global variables.
- **Vue Router** — true client-side navigation with history API, replacing full-page reloads between dashboard sections.
- **Vite** — sub-second hot-module replacement during development; optimised, tree-shaken production bundles.

The backend (Django Ninja REST API) does not change structurally. Only a small number of new endpoints are required.

---

### v1.2 — Frontend Build Toolchain

Lay the foundation for the reactive frontend without breaking the existing Django template frontend.

- [x] Add a `frontend-spa/` directory at the repo root with a Vite + Vue 3 + TypeScript project (`npm create vue@latest`)
- [x] Configure Tailwind CSS 3 with the JIT engine and a proper `tailwind.config.ts` (replaces the CDN `<script>` tag)
- [x] Set up ESLint + Prettier + `vue-tsc` for type checking in CI
- [x] Configure `vite.config.ts` to output built assets into `frontend/static/frontend/spa/` so Django's `collectstatic` picks them up
- [x] Add a Django view + template that serves `index.html` (the SPA shell) for all `/app/*` URLs; the old `/dashboard/*` routes remain untouched
- [x] Add `npm run build` as a step in the CI pipeline before the Docker image is built
- [x] Add `npm run test:unit` (Vitest) to CI

### v1.3 — Vue SPA: Auth & Shell

Port the auth flow and application shell into Vue so the SPA is self-contained.

- [x] Implement Vue Router with lazy-loaded route modules for every major section
- [x] Implement a `useAuth` Pinia store (login, register, me, logout) backed by the existing `/api/v1/users/*` endpoints
- [x] Implement a `useFirm` Pinia store (firm selection, multi-workspace switching) — replaces `localStorage` ad-hoc reads
- [x] Build the authenticated shell component: collapsible sidebar, top bar, mobile bottom nav, workspace switcher
- [x] Port Login, Register, Forgot Password, Reset Password, and Accept Invite pages as Vue SPA routes
- [x] Port the Onboarding flow (workspace creation) to Vue with a multi-step wizard component
- [x] Add route guards (`beforeEach`) that redirect unauthenticated users and users without a firm
- [x] Add a global toast / snackbar system as a Vue composable (`useToast`)
- [x] Add loading skeletons (pulse animations) for all data-fetching states

### v1.4 — Vue SPA: CRM Core Views

Replace the vanilla-JS dashboard pages with reactive Vue components.

- [x] **Dashboard overview** — reactive stat cards with auto-refresh every 60 s; replace Chart.js with Apache ECharts for richer, interactive charts
- [x] **Leads list** — virtual-scrolled table with server-side filtering, sorting, and pagination; inline status badge editor (click to change status without opening a modal)
- [x] **Kanban board view** — drag-and-drop pipeline board using `vue-draggable-plus`; cards show title, value, owner avatar, and overdue task indicator; toggled via a view-switcher button next to the table view
- [x] **Lead detail page** — fully reactive with optimistic UI updates (status changes appear immediately, roll back on error); tabbed layout: Overview / Activities / Tasks / Files
- [x] **Customers list** — live search with 300 ms debounce; infinite scroll or pagination toggle
- [x] **Customer detail page** — contact card, tag editor, metadata key-value editor, linked leads list
- [x] **Task calendar** — FullCalendar Vue 3 wrapper (`@fullcalendar/vue3`); month / week / agenda views; inline task creation by clicking a date
- [x] **Team page** — role badge editor (change role inline); invitation status tracking (pending / accepted / expired)
- [x] **Settings page** — profile editor with live avatar preview; workspace rename; danger zone (leave / delete workspace)
- [x] Write Vitest unit tests for all Pinia stores; write Vue Test Utils component tests for the 5 most complex components

### v1.5 — Real-Time Updates

Add push-based updates so multiple team members see live changes without polling.

- [x] Add `channels` and `daphne` to requirements; configure Django Channels with a Redis channel layer
- [x] Define a `FirmConsumer` WebSocket consumer that broadcasts events to a firm-scoped group
- [x] Emit channel messages on: lead created/updated/deleted, activity added, task completed
- [x] Implement a `useWebSocket` Vue composable that connects on mount, reconnects with exponential back-off, and dispatches Pinia mutations
- [x] Update the Leads Kanban and the Lead detail activity timeline to react to incoming WebSocket events (new card appears, new activity appended)
- [x] Add a persistent in-app notification bell (unread count badge) with a slide-over panel listing recent events
- [x] Store notifications in a new `Notification` model scoped to a Firm + User; provide REST endpoints to list and mark as read

### v1.6 — UX Polish & Accessibility

Raise the quality bar to match commercial SaaS standards.

- [x] **Dark mode** — implement via Tailwind's `class` strategy; persist user preference in `useTheme` composable (localStorage + `prefers-color-scheme` fallback); toggle button in AppShell sidebar; `dark:` classes applied to all major layouts, modals, inputs, and auth views
- [x] **Keyboard shortcuts** — `G L` → Leads, `G C` → Customers, `G D` → Dashboard, `N` → New lead (when on Leads page); display shortcut hints in a `?` help modal; `useKeyboardShortcuts` composable
- [x] **Empty states** — illustrated empty states with SVG icons, headline, subtitle, and clear CTA for all list views (no leads, no tasks, no team members, calendar)
- [x] **Error states** — `ErrorBoundary.vue` component with `onErrorCaptured` and retry slot; `NotFoundView.vue` 404 page; router catch-all updated to render the 404 page instead of redirecting
- [x] **Drag-and-drop file uploads** — drop zone on Lead detail Files tab with XHR progress bar and image thumbnail preview before upload
- [x] **Accessibility** — skip-to-content link at top of AppShell; `id="main-content"` on `<main>`; `aria-label`, `aria-modal`, `role` attributes on interactive elements; landmark roles in nav and dialogs
- [x] **i18n scaffolding** — `vue-i18n@9` installed; `locales/en.json` and `locales/cs.json` created; plugin wired in `main.ts`; `useI18n` re-export composable; AppShell nav, LoginView, and DashboardView updated to use `t()`
- [x] **Performance** — `index.html` updated with proper title, meta description, and Inter font preload; `vite.config.ts` adds `manualChunks` for vendor / echarts / fullcalendar bundles

### v1.7 — Public API & Integrations

Open LeadLab to the ecosystem.

- [x] **JWT API tokens** — add a `APIToken` model; provide UI in Settings to generate/revoke tokens; accept `Authorization: Bearer <token>` in Django Ninja auth (in addition to session auth)
- [x] **Outbound webhooks** — `WebhookEndpoint` model (URL, secret, event types); Celery task delivers signed `X-LeadLab-Signature` POST requests on lead and activity events; UI in Settings to manage endpoints and view delivery log
- [x] **iCal feed** — a per-user signed URL that exports tasks as an iCalendar file; importable into Google Calendar / Apple Calendar
- [x] **CSV import** — upload a CSV of leads or customers; background Celery job parses, validates, and creates records; progress shown in a status panel
- [x] **CSV/PDF export** — download the current filtered lead or customer list as CSV; generate a pipeline summary PDF via `weasyprint`
- [x] Expose a machine-readable OpenAPI schema at `/api/v1/openapi.json` and auto-generate a Python SDK with `openapi-python-client`

### v1.8 — Advanced Analytics & Reporting

Give sales managers actionable data.

- [x] **Pipeline velocity** — average time a lead spends in each status; displayed as a funnel chart
- [x] **Won / Lost breakdown by source** — stacked bar chart; filterable by date range
- [x] **Team performance** — table of members with leads owned, tasks completed, activities logged; sortable columns
- [x] **Trend charts** — leads created vs. closed per week for the last 12 weeks; rolling 30-day conversion rate
- [x] **Custom date range picker** — replace hardcoded "last 30 days" with a calendar range picker component
- [x] **Scheduled reports** — weekly email digest (Celery beat task) with pipeline summary; user can opt out in Settings
- [x] All chart data backed by dedicated `/api/v1/crm/reports/*` endpoints with caching via Redis (`django-cache-machine` or manual `cache.set`)

### v1.9 — Mobile PWA & End-to-End Testing

Polish for production confidence.

- [x] **PWA manifest** — `manifest.json` with icons, theme colour, display mode `standalone`; service worker (Workbox via Vite plugin) caches the app shell and static assets for offline use
- [x] **Push notifications** — Web Push API integration; notify assigned user when a task is due or a new lead is assigned; preference toggle in Settings
- [x] **Playwright E2E tests** — cover the critical paths: registration → onboarding → create lead → change status → add activity → complete task; run in CI on every PR
- [x] **Visual regression tests** — Percy or Playwright screenshot comparisons for the dashboard overview, lead detail, and Kanban board
- [x] **Load testing** — Locust scenario simulating 50 concurrent users; confirm API p95 < 200 ms
- [x] **Security hardening** — Content-Security-Policy header; Subresource Integrity for any remaining CDN assets; `django-axes` for brute-force protection on login; run `pip-audit` in CI

### v2.0 — Commercial Release

Ship a product teams pay for.

- [x] **White-label / custom branding** — Firm owners can upload a logo and set a primary colour; the SPA sidebar and email templates reflect the firm's brand
- [x] **Multi-language UI** — complete Czech translation (`cs.json`); language selector in Settings; accept-language header auto-detection on first visit
- [x] **Public marketing site** — replace the current `landing.html` with a proper landing page: hero, features, pricing table, testimonials, FAQ, and footer; built with Vue + the same Tailwind design system
- [x] **Subscription gating in the SPA** — Pinia `useFirm` store is aware of the subscription tier; locked features display an upgrade prompt instead of throwing a 403
- [x] **Onboarding wizard v2** — guided 5-step onboarding after workspace creation: create workspace → invite team → import leads CSV → configure pipeline stages → complete; dashboard banner directs returning users back to onboarding until complete
- [x] **Super-admin panel** — `/superadmin/` SPA route for support staff: view all firms, manually adjust subscription tier and status
- [x] **Plugin / extension system** — documented `LeadLabPlugin` interface (`frontend-spa/src/plugins/index.ts`) lets third-party developers register new activity types, sidebar nav items, and webhook event types without forking the core; backend registry in `leadlab/plugin_registry.py`; authoring guide at `docs/plugins.md`
- [x] **Comprehensive documentation site** — MkDocs Material site (`mkdocs.yml`) with: Getting Started, self-hosting guide, API reference, plugin authoring guide, changelog, and SLA
- [ ] **Security audit** — external pen test; resolve all critical/high findings; publish a responsible-disclosure policy
- [ ] **SLA & uptime** — public status page (e.g. Statuspage.io); uptime monitoring with PagerDuty alerting; define and document SLA for hosted offering

---

## Road to v3.0 — Enhanced Commercial Platform

The v3.0 milestone builds on the solid commercial foundation of v2.0 with three primary themes: **UX/UI excellence**, **business proposal workflows**, and a **rich plugin ecosystem**. The goal is to transform LeadLab from a CRM into a complete sales enablement platform that teams reach for daily.

---

### v2.1 — UX Foundation & Design System

Establish a consistent, polished design language across the entire SPA before adding new features on top.

- [x] **Design tokens** — extract all colours, spacing, border radii, and shadow values into a shared `design-tokens.ts`; wire them into `tailwind.config.ts` so every component references tokens rather than raw Tailwind classes
- [x] **Component library** — build a documented internal library (`src/components/ui/`) of base components: `Button`, `Input`, `Select`, `Modal`, `Badge`, `Avatar`, `Tooltip`, `Dropdown`; replace ad-hoc variants scattered across views
- [x] **Storybook** — set up Storybook 8 with the Vite builder; write stories for every base component and the 10 most complex composite components; add Chromatic visual regression CI step
- [x] **Micro-interactions** — add entrance / exit transitions (`v-motion` or Tailwind `transition`) to modals, slide-overs, toasts, and Kanban cards; use `reduced-motion` media query to disable for accessibility
- [x] **Responsive overhaul** — audit and fix every view on 375 px, 768 px, and 1440 px breakpoints; replace any overflow-hidden hacks with proper flex/grid layouts
- [x] **Typography scale** — define and apply a consistent typographic scale (display, heading, body, caption, label) via Tailwind's `fontSize` config; ensure correct heading hierarchy (`h1`–`h4`) for accessibility and SEO

### v2.2 — UX Intelligence & Personalisation

Make the UI feel smart and personal.

- [x] **Command palette** — `Cmd/Ctrl + K` opens a global fuzzy-search command palette (`vue-command-palette` or custom); supports navigating to any lead, customer, or settings page; shows recent items and keyboard shortcut hints
- [x] **Adaptive dashboard** — drag-and-drop widget layout (using `vue-grid-layout`); users pin the stat cards and charts they care about most; layout persisted per user in the backend
- [x] **Contextual quick actions** — right-click (or long-press on touch) context menu on lead and customer rows for instant access to: edit, change status, assign, delete, add activity
- [x] **Smart lead scoring** — display a configurable score (0–100) beside each lead based on weighted rules (last activity age, value, source); rules editable in Settings; colour-coded badge in list and Kanban views
- [x] **Saved views** — users save named filter + sort combinations (e.g. "My open leads", "High-value Q3") on Leads and Customers lists; saved views appear in the sidebar under the respective section
- [x] **Activity composer improvements** — rich-text editor (Tiptap) for comments and emails; @mention team members to tag them in activities (creates a notification); emoji picker

### v2.3 — Business Proposals & Quote Builder

Enable teams to create, send, and track professional sales proposals directly within LeadLab, closing the loop between pipeline and commercial output.

- [ ] **Proposal model** — new `Proposal` Django model scoped to a Lead: title, status (`Draft` / `Sent` / `Viewed` / `Accepted` / `Rejected` / `Expired`), expiry date, total value, currency, notes; REST endpoints for full CRUD
- [ ] **Line-item model** — `ProposalItem` with description, quantity, unit price, discount (%), VAT rate (%); computed totals (subtotal, tax, total) returned by the API
- [ ] **Template library** — `ProposalTemplate` model stores reusable line-item sets and text blocks scoped to a Firm; CRUD UI in Settings → Proposal Templates; templates can be applied to a new proposal with one click
- [ ] **Proposal builder UI** — dedicated route `/app/leads/:id/proposals/:pid`; drag-and-drop section reordering; inline rich-text editing for custom intro/closing text; live preview panel alongside the editor
- [ ] **PDF generation** — server-side PDF rendering via `weasyprint` using a Jinja2 HTML template; custom branding (firm logo, brand colour) injected from the Firm model; download and email buttons in the UI
- [ ] **Public proposal link** — signed, time-limited public URL (no auth required) that renders a read-only HTML version of the proposal; recipient can accept or reject with a single click; acceptance is logged as a `PROPOSAL_ACCEPTED` activity on the lead
- [ ] **Proposal analytics** — track: time-to-open, number of views, accepted/rejected ratio per template; displayed in a dedicated Proposals analytics tab in Analytics view
- [ ] **E-signature integration** — optional DocuSign or Dropbox Sign webhook: when all parties sign, update proposal status to `Accepted` automatically and fire the standard webhook events

### v2.4 — Plugin Marketplace & Ecosystem

Grow a first-party and third-party plugin ecosystem around the architecture established in v2.0.

- [ ] **Plugin manifest standard** — define a `leadlab-plugin.json` schema (name, version, entrypoint, permissions, config schema, icon URL); validate on `registerPlugin()` at startup; surface plugin info in Settings → Plugins
- [ ] **In-app plugin manager** — Settings → Plugins page listing all installed plugins with name, version, description, status toggle (enable/disable without uninstall), and a link to the authoring docs
- [ ] **First-party plugin: Email Sequences** — multi-step drip campaign plugin; define a sequence of timed emails per lead status transition; Celery beat schedules individual sends; plugin registers its own `SEQUENCE_EMAIL_SENT` activity type and sidebar nav item
- [ ] **First-party plugin: VoIP / Click-to-Call** — integrates with Twilio (or Vonage) to place calls directly from a lead detail page; call duration and recording URL logged as a `CALL` activity; plugin configuration in Settings (API key, caller ID)
- [ ] **First-party plugin: LinkedIn Enrichment** — given a LinkedIn profile URL on a customer record, fetches public profile data (name, title, company, avatar) via a proxy API; updates customer fields and logs an `ENRICHMENT` activity
- [ ] **First-party plugin: Slack Notifications** — sends a Slack message to a configurable channel on: new lead created, lead won/lost, task overdue, proposal accepted; configurable per event type in Settings; uses Slack Incoming Webhooks
- [ ] **Plugin config schema UI** — plugins declare a JSON Schema for their configuration; the Settings → Plugins page auto-renders a typed form (text, number, boolean, secret) for each plugin's settings; values stored in a `PluginConfig` model per Firm
- [ ] **Plugin API sandbox** — a `usePlugin(pluginName)` Vue composable that exposes a scoped API to plugins: `toast()`, `navigate()`, `openModal()`, `useFirm()`, `useAuth()`; prevents plugins from accessing internals they did not declare in their manifest permissions
- [ ] **Public plugin registry** — a static JSON registry (hosted on GitHub Pages or a CDN) listing community plugins with name, author, description, version, and install instructions; linked from the in-app plugin manager

### v2.5 — Workflow Automation

Let teams define trigger → action rules without writing code.

- [ ] **Automation rule model** — `AutomationRule` with trigger (lead status change, task overdue, proposal accepted, custom webhook), conditions (field comparisons), and actions (send email, create task, update field, call webhook, run plugin action)
- [ ] **Automation builder UI** — visual rule editor in Settings → Automations; each rule card shows trigger → conditions → actions in a readable sentence; toggle on/off per rule
- [ ] **Celery execution engine** — rules evaluated in a Celery task on every trigger event; execution log per rule (last run, status, error message) stored in `AutomationRun` model and visible in the UI
- [ ] **Built-in templates** — ship 5 ready-to-use automation templates: "Remind assignee 1 day before task due", "Notify owner when lead won", "Send welcome email when lead created", "Mark lead as Lost after 30 days of inactivity", "Create follow-up task when proposal sent"

### v3.0 — Platform Release

Consolidate v2.x features, raise quality standards, and position LeadLab as a full-featured sales platform.

- [ ] **Full accessibility audit** — WCAG 2.2 AA compliance verified by automated (`axe-core` CI step) and manual testing; publish an accessibility statement
- [ ] **Performance budget** — Lighthouse CI enforcing LCP < 2.5 s, TBT < 200 ms, CLS < 0.1 on the dashboard and lead detail pages; bundle size budget enforced in CI (main bundle ≤ 150 kB gzipped)
- [ ] **Internationalisation expansion** — add German (`de.json`) and Polish (`pl.json`) translations; community contribution guide for adding new locales; locale coverage check in CI (fail if any key is missing from a locale file)
- [ ] **User impersonation in Super Admin** — super admins can impersonate any firm member to debug issues; impersonation session logged to an `ImpersonationLog` model; banner displayed while impersonating
- [ ] **Advanced RBAC** — custom roles beyond Owner / Admin / Worker; per-resource permission overrides (e.g. "Worker can delete their own leads"); role editor in Settings
- [ ] **Data retention & compliance** — configurable data retention policies per Firm (auto-delete leads older than N days); GDPR right-to-erasure endpoint; audit log of all destructive actions
- [ ] **White-label SaaS mode** — a single LeadLab deployment can serve multiple branded domains (custom domain per Firm); SSL provisioned automatically via Let's Encrypt; login page shows firm logo and brand colour
- [ ] **Enterprise SSO** — SAML 2.0 / OIDC authentication for firms on an Enterprise plan; JIT provisioning creates Membership on first SSO login; attribute mapping for role assignment
- [ ] **v3.0 launch** — public announcement, updated marketing site with v3 feature highlights, migration guide from v2.x, and a recorded product demo video

---

## Out of Scope (for now)

- LDAP — SAML/OIDC SSO (planned for v3.0) covers enterprise auth requirements; LDAP sync is not planned.
- Native mobile apps (iOS/Android) — the PWA covers mobile use cases; a React Native / Expo app could be a post-v3.0 initiative.
