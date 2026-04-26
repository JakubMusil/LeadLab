# LeadLab

**LeadLab** is a full-stack multi-tenant SaaS CRM built with Django 6 / Django Ninja on the backend and a Vue 3 SPA on the frontend. It provides a clean REST API and a real-time web application for managing sales leads, customers, tasks, and team collaboration — all scoped to isolated workspaces called *Firms*.

---

## Features

- **Multi-tenancy** — Every piece of data belongs to exactly one Firm. Users can be members of multiple Firms with different roles.
- **Lead pipeline** — Track opportunities through statuses: New → Contacted → Proposal → Negotiation → Won / Lost / Canceled.
- **Customer address book** — Reusable contact records with tags, custom metadata, and links to multiple leads.
- **Activity timeline** — Immutable event log per lead: comments, calls, meetings, emails, file uploads, status changes, and task events.
- **Task management** — To-do items scoped to leads with due dates, assignment, and automatic completion logging. Weekly digest email via Celery Beat.
- **Role-based access control** — Three membership roles per Firm: Owner, Admin, and Worker.
- **Email invitations** — Invite team members by email; new users can create an account directly from the invitation link.
- **Subscription tiers** — Free and Pro plans enforced at the API layer, backed by Stripe Checkout.
- **API tokens** — Personal Bearer tokens for machine-to-machine access alongside session auth.
- **Outbound webhooks** — Register endpoints to receive real-time event payloads (lead created/updated/deleted, activity created).
- **Real-time updates** — WebSocket channel via Django Channels broadcasts pipeline events to connected browser clients.
- **Web Push notifications** — VAPID-based push notifications for task assignments and lead events.
- **Integrations** — iCal task feed, CSV bulk import/export for leads and customers, PDF pipeline summary.
- **White-label branding** — Upload a custom logo and set a brand colour per workspace (Pro tier).
- **Async email dispatch** — Outbound emails queued via Celery / Redis.
- **File storage** — Local media or AWS S3 via `django-storages`.
- **Plugin system** — Register custom nav items, activity types, and webhook event types from external Django apps.
- **Brute-force protection** — django-axes blocks accounts after repeated failed login attempts.
- **Error tracking** — Optional Sentry integration; activated by setting `SENTRY_DSN`.
- **Health endpoint** — `GET /api/v1/health/` probes the database and cache for load-balancer use.
- **Vue 3 SPA** — Full CRM UI with multi-language support (English / Czech), onboarding wizard, analytics dashboard, super-admin panel, and white-label theming.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6 / Django Ninja |
| ASGI server | Daphne (production), Django dev server (local) |
| Database | PostgreSQL (SQLite for local dev) |
| Task queue | Celery + Redis |
| Real-time | Django Channels + channels-redis |
| Payments | Stripe Checkout |
| Storage | Local FS / AWS S3 |
| Auth | Session-based + Bearer API tokens |
| Frontend | Vue 3 + TypeScript + Tailwind CSS (Vite build) |
| Error tracking | Sentry (optional) |

---

## Project Structure

```
leadlab/          # Django project settings, URL conf, Celery config, root API, plugin registry
users/            # Custom User model (email-based), auth endpoints, password reset, avatars
firms/            # Firm & Membership models, tenant middleware, role auth, invitations,
                  #   billing (Stripe), API tokens, outbound webhooks
crm/              # Customer, Lead, Activity, Task models and API; WebSocket consumers;
                  #   integrations (iCal, CSV, PDF); push notifications
frontend/         # Thin Django app that serves the compiled Vue SPA
frontend-spa/     # Vue 3 + TypeScript SPA source (npm build)
docs/             # MkDocs documentation site
e2e/              # End-to-end tests
manage.py
requirements.txt
docker-compose.yml
Dockerfile
```

---

## API Overview

All endpoints are served at `/api/v1/`. Most endpoints accept **session cookies** (set by `POST /users/login`) or a **Bearer token** (`Authorization: Bearer <token>`). Public exceptions are noted below.

Every CRM request requires an `X-Firm-ID` header to identify the active tenant.

### Authentication — `/api/v1/users/`

| Method | Path | Auth required | Description |
|---|---|---|---|
| POST | `/register` | No | Create a new account |
| POST | `/login` | No | Start a session |
| POST | `/logout` | Yes | End the current session |
| GET | `/me` | Yes | Return the current user |
| PATCH | `/me` | Yes | Update profile (name, timezone) |
| POST | `/me/avatar` | Yes | Upload / replace profile picture |
| POST | `/password-reset/request` | No | Send a password-reset email |
| POST | `/password-reset/confirm` | No | Set a new password via reset token |

### Firms & Team — `/api/v1/firms/`

| Method | Path | Role required | Description |
|---|---|---|---|
| GET | `/` | authenticated | List the caller's Firms |
| POST | `/` | authenticated | Create a Firm (caller becomes Owner) |
| GET | `/{firm_id}` | member | Get Firm details |
| PATCH | `/{firm_id}` | Admin+ | Rename a Firm |
| DELETE | `/{firm_id}` | Owner | Delete a Firm |
| POST | `/{firm_id}/branding` | Owner | Upload logo / set brand colour |
| GET | `/{firm_id}/members` | member | List team members |
| POST | `/{firm_id}/members` | Admin+ | Add an existing user as member |
| PATCH | `/{firm_id}/members/{id}` | Admin+ | Change a member's role |
| DELETE | `/{firm_id}/members/{id}` | Admin+ | Remove a member |
| GET | `/{firm_id}/invitations/` | Admin+ | List email invitations |
| POST | `/{firm_id}/invitations/` | Admin+ | Send an email invitation |
| POST | `/{firm_id}/billing/checkout` | Owner | Create Stripe Checkout session |
| GET | `/{firm_id}/tokens` | member | List API tokens |
| POST | `/{firm_id}/tokens` | member | Create an API token |
| DELETE | `/{firm_id}/tokens/{id}` | member / Admin+ | Revoke an API token |
| GET | `/{firm_id}/webhooks` | Admin+ | List webhook endpoints |
| POST | `/{firm_id}/webhooks` | Admin+ | Create a webhook endpoint |
| PATCH | `/{firm_id}/webhooks/{id}` | Admin+ | Update a webhook endpoint |
| DELETE | `/{firm_id}/webhooks/{id}` | Admin+ | Delete a webhook endpoint |
| GET | `/{firm_id}/webhooks/{id}/deliveries` | Admin+ | List delivery attempts |

### Invitations (public) — `/api/v1/invitations/`

| Method | Path | Auth required | Description |
|---|---|---|---|
| GET | `/{token}` | No | Preview an invitation |
| POST | `/{token}/accept` | No | Accept an invitation (creates account if needed) |

### CRM — `/api/v1/crm/`

| Method | Path | Role required | Description |
|---|---|---|---|
| GET | `/customers` | member | List / search customers |
| POST | `/customers` | Worker+ | Create a customer |
| GET | `/customers/{id}` | member | Get a customer |
| PUT | `/customers/{id}` | Worker+ | Replace a customer |
| DELETE | `/customers/{id}` | Admin+ | Delete a customer |
| GET | `/leads` | member | List leads (filter by status / assignee / source / tag / date) |
| POST | `/leads` | Worker+ | Create a lead |
| GET | `/leads/{id}` | member | Get a lead |
| PATCH | `/leads/{id}` | Worker+ | Update a lead (status change auto-logged) |
| DELETE | `/leads/{id}` | Admin+ | Delete a lead |
| GET | `/leads/{id}/activities` | member | Paginated activity timeline for a lead |
| POST | `/activities` | Worker+ | Log an activity (unified action hub) |
| GET | `/tasks` | member | List tasks (filter by completed) |
| POST | `/tasks` | Worker+ | Create a task |
| POST | `/tasks/{id}/complete` | Worker+ | Mark a task as completed |

### Integrations — `/api/v1/integrations/`

| Method | Path | Description |
|---|---|---|
| GET | `/ical/token` | Get signed iCal feed URL |
| GET | `/ical/tasks` | Public iCal feed (token-authenticated) |
| POST | `/import/leads` | Bulk-import leads from CSV |
| POST | `/import/customers` | Bulk-import customers from CSV |
| GET | `/import/{job_id}` | Poll import job status |
| GET | `/import` | List recent import jobs |
| GET | `/export/leads.csv` | Download leads as CSV |
| GET | `/export/customers.csv` | Download customers as CSV |
| GET | `/export/pipeline.pdf` | Download pipeline summary as PDF |

### Web Push — `/api/v1/push/`

| Method | Path | Description |
|---|---|---|
| GET | `/vapid-public-key` | Return the server's VAPID public key (unauthenticated) |
| POST | `/subscribe` | Register a push subscription |
| POST | `/unsubscribe` | Remove a push subscription |

### Stripe Webhook — `/api/v1/stripe/`

| Method | Path | Description |
|---|---|---|
| POST | `/webhook` | Receive Stripe events (e.g. subscription activated) |

### Health — `/api/v1/health/`

| Method | Path | Description |
|---|---|---|
| GET | `/` | Probe DB and cache; returns `200 ok` or `503 error` |

Interactive API docs are available at `/api/v1/docs` when the server is running.

---

## License

MIT
