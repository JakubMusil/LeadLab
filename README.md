# LeadLab

**LeadLab** is a full-stack multi-tenant SaaS CRM/ERP platform built with Django / Django Ninja on the backend and a Vue 3 SPA on the frontend. It covers the complete business lifecycle — from the first sales contact all the way through delivery and post-sale service — in a single, unified workspace called a *Firm*.

---

## Features

### CRM — Sales & Relationships

- **Contact book** — Unified address book for companies and people; IČO/DIČ, tags, custom metadata, company–person hierarchy, and enrichment via plugins.
- **Opportunity pipeline (Leads)** — 6-stage Kanban (New → Contacted → Qualified → Proposal → Won / Lost / Canceled) with drag-and-drop, smart lead scoring (0–100), and saved filter views.
- **Business proposals** — Quote builder with line items, PDF export, public signing links, accept/reject tracking, and proposal templates.
- **Realization (project delivery)** — Kanban activated automatically on Won; milestones, time tracking, linked tasks, activities, documents, and financial reports.
- **Management (post-delivery)** — SLA/warranty/retention tracking with colour-coded time indicators, service Kanban, and automatic escalation via the automation engine.
- **Activity timeline** — Immutable event log per entity: comments (with @mention via Tiptap), calls, meetings, emails, file uploads, status changes, and task events.
- **Task management** — Global task manager with calendar view, templates, checklists, due-date assignment, and automatic completion logging.

### ERP — Operations & Tools

- **Time tracking** — Persistent sitewide floating timer; attach entries to any entity (Lead, Realization, Task, etc.) or log manually as a timesheet entry.
- **Financial reports** — P&L overview at Opportunity / Realization / Customer level; timesheet, expense and revenue items; Fakturoid API integration for invoicing; CSV/PDF export.
- **Calendar** — Aggregated monthly/weekly/daily view (FullCalendar) showing tasks, milestones, SLA expiry, and activity events; iCal export.
- **Documents** — Central file store with drag-and-drop upload, signed temporary share links, in-browser image/PDF preview, and cross-entity search.

### Platform

- **Multi-tenancy** — Every record is strictly scoped to one Firm; users can belong to multiple Firms with independent roles.
- **Role-based access control** — Three roles per Firm: Owner, Admin, and Worker.
- **Email invitations** — Invite team members by email; new users register directly from the invitation link.
- **Subscription tiers** — Free and Pro plans enforced at the API layer, backed by Stripe Checkout.
- **API tokens** — Personal Bearer tokens for machine-to-machine access alongside session auth.
- **Outbound webhooks** — Register endpoints to receive real-time event payloads; delivery attempt log included.
- **Real-time updates** — WebSocket channel (Django Channels) broadcasts pipeline events to connected browser clients.
- **Web Push notifications** — VAPID-based push for task assignments and lead events.
- **Workflow automation** — Visual trigger → condition → action rule builder with AND/OR logic; evaluated by Celery with a full execution log.
- **Plugin system** — Register custom nav items, activity types, and webhook event types from external Django apps; first-party plugins for Email Sequences, VoIP/Click-to-Call, LinkedIn Enrichment, and Slack Notifications; community plugins via the public registry.
- **White-label branding** — Custom logo and brand colour per workspace (Pro tier).
- **Async email dispatch** — Outbound emails queued via Celery / Redis.
- **File storage** — Local media or AWS S3 via `django-storages`.
- **Brute-force protection** — `django-axes` locks accounts after repeated failed login attempts.
- **Error tracking** — Optional Sentry integration; activated by setting `SENTRY_DSN`.
- **Health endpoint** — `GET /api/v1/health/` probes the database and cache for load-balancer use.

### Vue 3 SPA

- Multi-language UI (English / Czech / German / Polish) with dark mode.
- Onboarding wizard, analytics dashboard (pipeline velocity, team performance, conversion trends), and super-admin panel.
- Command palette (`Cmd/Ctrl+K`), keyboard shortcuts, notification bell, and Tiptap rich-text editor with @mention.
- PWA manifest + service worker.
- Internal design system (Button, Input, Modal, Badge, …) documented in Storybook.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django / Django Ninja |
| ASGI server | Daphne (production), Django dev server (local) |
| Database | PostgreSQL (SQLite for local dev) |
| Task queue | Celery + Redis |
| Real-time | Django Channels + channels-redis |
| Payments | Stripe Checkout |
| Storage | Local FS / AWS S3 (django-storages) |
| Auth | Session-based + Bearer API tokens |
| Frontend | Vue 3 + TypeScript + Tailwind CSS (Vite) |
| Error tracking | Sentry (optional) |
| Documentation | MkDocs |

---

## Project Structure

```
leadlab/          # Django project settings, URL conf, Celery config, root API, plugin registry
users/            # Custom User model (email-based), auth endpoints, password reset, avatars
firms/            # Firm & Membership models, tenant middleware, role auth, invitations,
                  #   billing (Stripe), API tokens, outbound webhooks
crm/              # Contact, Lead, Activity, Task, Realization, Management, Proposal,
                  #   Automation models and API; WebSocket consumers;
                  #   integrations (iCal, CSV, PDF); push notifications
plugins/          # Plugin registry and first-party plugin implementations
frontend/         # Thin Django app that serves the compiled Vue SPA
frontend-spa/     # Vue 3 + TypeScript SPA source (npm build)
docs/             # MkDocs documentation site
e2e/              # Playwright end-to-end tests
manage.py
requirements.txt
docker-compose.yml
Dockerfile
```

---

## Quick Start

### Option A — Docker Compose (recommended)

```bash
git clone https://github.com/JakubMusil/LeadLab.git
cd LeadLab
cp .env.example .env   # edit variables as needed
docker compose up --build
```

Apply migrations and create a superuser inside the running container:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

The API is available at `http://localhost:8000/api/v1/` and the web app at `http://localhost:8000/`.

### Option B — Local Development

**Prerequisites:** Python 3.11+, Node.js 20+, Redis 7+ (optional for local dev).

```bash
git clone https://github.com/JakubMusil/LeadLab.git
cd LeadLab

# Python environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend SPA
cd frontend-spa && npm install && npm run build-only && cd ..

# Environment variables
cp .env.example .env   # edit as needed

# Database
python manage.py migrate

# (Optional) seed demo data
python manage.py load_demo_data
# → creates demo@leadlab.io / Demo1234! with a sample workspace

# Start the dev server
python manage.py runserver
```

> **WebSockets:** The Django dev server does not support WebSockets. Use Daphne to test real-time events locally:
> ```bash
> daphne -b 127.0.0.1 -p 8000 leadlab.asgi:application
> ```

> **Celery** (async email, CSV import, automations, weekly digest):
> ```bash
> celery -A leadlab worker --loglevel=info
> celery -A leadlab beat --loglevel=info   # scheduled tasks
> ```

See [install.md](install.md) for the full environment variable reference and production deployment checklist.

---

## API Overview

All endpoints are served at `/api/v1/`. Authentication uses **session cookies** (set by `POST /users/login`) or a **Bearer token** (`Authorization: Bearer <token>`). Public exceptions are noted below.

Every CRM/ERP request requires an `X-Firm-ID` header to identify the active tenant.

Interactive API docs are available at `/api/v1/docs` when the server is running.

### Authentication — `/api/v1/users/`

| Method | Path | Auth | Description |
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

| Method | Path | Role | Description |
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

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/{token}` | No | Preview an invitation |
| POST | `/{token}/accept` | No | Accept an invitation (creates account if needed) |

### CRM — `/api/v1/crm/`

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/customers` | member | List / search contacts |
| POST | `/customers` | Worker+ | Create a contact |
| GET | `/customers/{id}` | member | Get a contact |
| PUT | `/customers/{id}` | Worker+ | Replace a contact |
| DELETE | `/customers/{id}` | Admin+ | Delete a contact |
| GET | `/leads` | member | List leads (filter by status / assignee / source / tag / date) |
| POST | `/leads` | Worker+ | Create a lead |
| GET | `/leads/{id}` | member | Get a lead |
| PATCH | `/leads/{id}` | Worker+ | Update a lead (status change auto-logged) |
| DELETE | `/leads/{id}` | Admin+ | Delete a lead |
| GET | `/leads/{id}/activities` | member | Paginated activity timeline |
| POST | `/activities` | Worker+ | Log an activity |
| GET | `/tasks` | member | List tasks (filter by completed) |
| POST | `/tasks` | Worker+ | Create a task |
| POST | `/tasks/{id}/complete` | Worker+ | Mark a task as completed |
| GET | `/realizations` | member | List realizations |
| POST | `/realizations` | Worker+ | Create a realization |
| GET | `/realizations/{id}` | member | Get a realization |
| PATCH | `/realizations/{id}` | Worker+ | Update a realization |
| DELETE | `/realizations/{id}` | Admin+ | Delete a realization |
| GET | `/milestones` | member | List milestones |
| POST | `/milestones` | Worker+ | Create a milestone |
| GET | `/management` | member | List management records |
| POST | `/management` | Worker+ | Create a management record |
| GET | `/management/{id}` | member | Get a management record |
| PATCH | `/management/{id}` | Worker+ | Update a management record |
| GET | `/automations` | Admin+ | List automation rules |
| POST | `/automations` | Admin+ | Create an automation rule |
| PATCH | `/automations/{id}` | Admin+ | Update an automation rule |
| DELETE | `/automations/{id}` | Admin+ | Delete an automation rule |
| GET | `/automations/{id}/runs` | Admin+ | List automation execution log |

### ERP — `/api/v1/erp/`

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/time-entries` | member | List time entries (filter by user, entity, date) |
| POST | `/time-entries` | Worker+ | Create / stop a time entry |
| PATCH | `/time-entries/{id}` | Worker+ | Edit a time entry |
| DELETE | `/time-entries/{id}` | Worker+ | Delete a time entry |
| GET | `/documents` | member | List documents (filter by entity) |
| POST | `/documents` | Worker+ | Upload a document |
| DELETE | `/documents/{id}` | Admin+ | Delete a document |

### Integrations — `/api/v1/integrations/`

| Method | Path | Description |
|---|---|---|
| GET | `/ical/token` | Get signed iCal feed URL |
| GET | `/ical/tasks` | Public iCal feed (token-authenticated) |
| POST | `/import/leads` | Bulk-import leads from CSV |
| POST | `/import/customers` | Bulk-import contacts from CSV |
| GET | `/import/{job_id}` | Poll import job status |
| GET | `/import` | List recent import jobs |
| GET | `/export/leads.csv` | Download leads as CSV |
| GET | `/export/customers.csv` | Download contacts as CSV |
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

---

## License

MIT
