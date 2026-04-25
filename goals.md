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

- [ ] **JWT API tokens** — add a `APIToken` model; provide UI in Settings to generate/revoke tokens; accept `Authorization: Bearer <token>` in Django Ninja auth (in addition to session auth)
- [ ] **Outbound webhooks** — `WebhookEndpoint` model (URL, secret, event types); Celery task delivers signed `X-LeadLab-Signature` POST requests on lead and activity events; UI in Settings to manage endpoints and view delivery log
- [ ] **iCal feed** — a per-user signed URL that exports tasks as an iCalendar file; importable into Google Calendar / Apple Calendar
- [ ] **CSV import** — upload a CSV of leads or customers; background Celery job parses, validates, and creates records; progress shown in a status panel
- [ ] **CSV/PDF export** — download the current filtered lead or customer list as CSV; generate a pipeline summary PDF via `weasyprint`
- [ ] Expose a machine-readable OpenAPI schema at `/api/v1/openapi.json` and auto-generate a Python SDK with `openapi-python-client`

### v1.8 — Advanced Analytics & Reporting

Give sales managers actionable data.

- [ ] **Pipeline velocity** — average time a lead spends in each status; displayed as a funnel chart
- [ ] **Won / Lost breakdown by source** — stacked bar chart; filterable by date range
- [ ] **Team performance** — table of members with leads owned, tasks completed, activities logged; sortable columns
- [ ] **Trend charts** — leads created vs. closed per week for the last 12 weeks; rolling 30-day conversion rate
- [ ] **Custom date range picker** — replace hardcoded "last 30 days" with a calendar range picker component
- [ ] **Scheduled reports** — weekly email digest (Celery beat task) with pipeline summary; user can opt out in Settings
- [ ] All chart data backed by dedicated `/api/v1/crm/reports/*` endpoints with caching via Redis (`django-cache-machine` or manual `cache.set`)

### v1.9 — Mobile PWA & End-to-End Testing

Polish for production confidence.

- [ ] **PWA manifest** — `manifest.json` with icons, theme colour, display mode `standalone`; service worker (Workbox via Vite plugin) caches the app shell and static assets for offline use
- [ ] **Push notifications** — Web Push API integration; notify assigned user when a task is due or a new lead is assigned; preference toggle in Settings
- [ ] **Playwright E2E tests** — cover the critical paths: registration → onboarding → create lead → change status → add activity → complete task; run in CI on every PR
- [ ] **Visual regression tests** — Percy or Playwright screenshot comparisons for the dashboard overview, lead detail, and Kanban board
- [ ] **Load testing** — Locust scenario simulating 50 concurrent users; confirm API p95 < 200 ms
- [ ] **Security hardening** — Content-Security-Policy header; Subresource Integrity for any remaining CDN assets; `django-axes` for brute-force protection on login; run `pip-audit` in CI

### v2.0 — Commercial Release

Ship a product teams pay for.

- [ ] **White-label / custom branding** — Firm owners can upload a logo and set a primary colour; the SPA sidebar and email templates reflect the firm's brand
- [ ] **Multi-language UI** — complete Czech translation (`cs.json`); language selector in Settings; accept-language header auto-detection on first visit
- [ ] **Public marketing site** — replace the current `landing.html` with a proper landing page: hero, features, pricing table, testimonials, FAQ, and footer; built with Vue + the same Tailwind design system
- [ ] **Subscription gating in the SPA** — Pinia `useFirm` store is aware of the subscription tier; locked features display an upgrade prompt instead of throwing a 403
- [ ] **Onboarding wizard v2** — guided 5-step onboarding after workspace creation: invite team → import leads CSV → configure pipeline stages → connect calendar → complete; tracks completion with a checklist on the dashboard
- [ ] **Super-admin panel** — internal Django admin extension (or a separate `/superadmin/` SPA route) for support staff: view all firms, impersonate users, manually adjust subscription status
- [ ] **Plugin / extension system** — a documented `LeadLabPlugin` interface that lets third-party developers register new activity types, sidebar nav items, and webhook event types without forking the core
- [ ] **Comprehensive documentation site** — MkDocs or Docusaurus site with: Getting Started, self-hosting guide, API reference (from OpenAPI), plugin authoring guide, and changelog
- [ ] **Security audit** — external pen test; resolve all critical/high findings; publish a responsible-disclosure policy
- [ ] **SLA & uptime** — public status page (e.g. Statuspage.io); uptime monitoring with PagerDuty alerting; define and document SLA for hosted offering

---

## Out of Scope (for now)

- Complex workflow automation (sequences, drip campaigns) — may be added as an optional plugin in a future major version.
- LDAP / SSO — session-based auth is sufficient for the target audience; OAuth2 is a potential future addition.
- Native mobile apps (iOS/Android) — the PWA covers mobile use cases; a React Native / Expo app could be a post-v2.0 initiative.
