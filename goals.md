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
5. **API-first** — The project exposes a documented REST API (Django Ninja / OpenAPI) as its primary interface; there is no coupled frontend.

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
- [ ] Stripe Checkout session creation for upgrading to Pro
- [ ] Stripe webhook handler for subscription lifecycle events (activated, cancelled, payment failed)
- [ ] Usage limits per subscription tier (e.g. max leads on Free plan)

### v0.5 — Files & Attachments
- [ ] File attachment list and delete endpoints scoped to a Lead

### v0.6 — Reporting
- [ ] Lead pipeline summary endpoint (counts per status, total value)
- [ ] Activity feed endpoint across all leads for a Firm
- [ ] Task overdue report

### v1.0 — Production Hardening
- [ ] Docker Compose setup for local development (Postgres, Redis, app, worker)
- [ ] Rate limiting on authentication endpoints
- [ ] Comprehensive logging and error tracking integration (Sentry)
- [ ] Health check endpoint for load balancer probes
- [ ] CI/CD pipeline with linting, tests, and coverage reporting

---

## Out of Scope (for now)

- A bundled frontend / SPA — LeadLab is intentionally backend-only; consumers build their own UI.
- Complex workflow automation (sequences, drip campaigns) — may be added as an optional plugin in a future major version.
- LDAP / SSO — session-based auth is sufficient for the target audience; OAuth2 is a potential future addition.
