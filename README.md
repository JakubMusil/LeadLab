# LeadLab

**LeadLab** is a full-stack multi-tenant SaaS CRM/ERP platform built with Django / Django Ninja on the backend and a Vue 3 SPA on the frontend. It covers the complete business lifecycle — from the first sales contact all the way through post-sale service — in a single, unified workspace called a *Firm*.

---

## Features

### CRM — Sales & Relationships

- **Contact book** — Unified address book for companies and people; IČO/DIČ, tags, custom metadata, company–person hierarchy, and enrichment via plugins.
- **Configurable pipeline (Records)** — Fully customisable categories (e.g. Sales, Service, Onboarding) each with their own stages, fields, and colour scheme. Records move through stages via drag-and-drop Kanban, with smart lead scoring (0–100) and saved filter views.
- **Pipeline settings** — Admin UI to create and reorder categories, define custom stages (incl. terminal/won flags), and toggle which fields (value, date range, notes, source, …) are visible per category.
- **Checkpoints** — Per-record milestones with optional due dates and completion tracking (replaces the old Realization milestone system).
- **Business proposals** — Quote builder with line items, PDF export, public signing links, accept/reject tracking, and proposal templates.
- **Activity timeline (Streamline)** — Immutable event log per entity (Record, Customer, Proposal, Task): comments with @mention (Tiptap rich text), calls, meetings, emails, SMS, WhatsApp, voice memos, file uploads, checklists, status changes, task events, AI summaries, and more. Emoji reactions on any activity. The sidebar toolbar is driven by a backend registry — no frontend hardcoding.
- **Task management** — Global task manager with calendar view, templates, rich-text descriptions, checklists / sub-tasks (Streamline Items), due-date ranges, priorities, status workflow, tags, watchers, favourites, personal reminders, recurring tasks, task dependencies (blocks / related-to), and an approval workflow. Calendar-bound task kinds (call, meeting, event) auto-close on expiry.

### ERP — Operations & Tools

- **Time tracking** — Persistent sitewide floating timer; attach entries to any entity (Record, Customer, Task) or log manually as a timesheet entry.
- **Financial reports** — P&L overview at Record / Customer level; timesheet, expense and revenue items with multi-currency support; Fakturoid API integration for invoicing; CSV/PDF export.
- **Multi-currency** — 14 supported currencies. Exchange rates auto-fetched from ECB daily at 17:30 UTC (or maintained manually per workspace). Canonical amounts stored on every financial record for consistent reporting. Per-workspace and per-user number/currency locale override.
- **Calendar** — Aggregated monthly/weekly/daily view (FullCalendar) showing tasks, checkpoints, and activity events; iCal export.
- **Documents** — Central file store with drag-and-drop upload, signed temporary share links, in-browser image/PDF preview, and cross-entity search.
- **Product catalog** — Internal catalog of products/services for use in proposal line items.

### Platform

- **Multi-tenancy** — Every record is strictly scoped to one Firm; users can belong to multiple Firms with independent roles.
- **Role-based access control** — Three roles per Firm: Owner, Admin, and Worker.
- **Email invitations** — Invite team members by email; new users register directly from the invitation link.
- **Subscription tiers** — Free and Pro plans enforced at the API layer, backed by Stripe Checkout.
- **API tokens** — Personal Bearer tokens for machine-to-machine access alongside session auth.
- **Outbound webhooks** — Register endpoints to receive real-time event payloads; delivery attempt log included.
- **Real-time updates** — WebSocket channel (Django Channels) broadcasts pipeline events to connected browser clients.
- **Web Push notifications** — VAPID-based push for task assignments and record events.
- **Workflow automation** — Visual trigger → condition → action rule builder with AND/OR logic; built-in templates; evaluated by Celery with a full execution log.
- **Streamline tool registry** — Backend-driven registry of activity toolbar tools; entity-type-specific toolbars served via `/api/v1/streamline/tools`, eliminating frontend hardcoding.
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
- Command palette (`Cmd/Ctrl+K`), keyboard shortcuts, notification bell, and Tiptap rich-text editor with @mention, task lists, highlight, and link support.
- Pipeline settings view for managing categories, stages, and field visibility.
- Public task share links (read-only task view without login).
- PWA manifest + service worker.
- Internal design system (Button, Input, Modal, Badge, …) documented in Storybook.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django / Django Ninja (API v2.5) |
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
leadlab/          # Django project settings, URL conf, Celery config, root API
users/            # Custom User model (email-based), auth endpoints, password reset, avatars
firms/            # Firm & Membership models, tenant middleware, role auth, invitations,
                  #   billing (Stripe), API tokens, outbound webhooks
crm/              # Core CRM/ERP models and APIs:
                  #   Customer, PipelineRecord, Category, Stage, CategoryField, Checkpoint,
                  #   Activity, Task, Proposal, Automation, Project, Document, TimeEntry,
                  #   ExpenseItem, RevenueItem; WebSocket consumers;
                  #   integrations (iCal, CSV, PDF, Fakturoid); push notifications;
                  #   Streamline tool registry
plugins/          # Plugin registry and first-party plugin implementations
                  #   (email_sequences, voip, linkedin_enrichment, slack_notifications,
                  #    fakturoid)
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

# (Optional) seed pipeline categories
python manage.py seed_pipeline_categories

# Start the dev server
python manage.py runserver
```

> **WebSockets:** The Django dev server does not support WebSockets. Use Daphne to test real-time events locally:
> ```bash
> daphne -b 127.0.0.1 -p 8000 leadlab.asgi:application
> ```

> **Celery** (async email, CSV import, automations, ECB rate sync, weekly digest):
> ```bash
> celery -A leadlab worker --loglevel=info
> celery -A leadlab beat --loglevel=info   # scheduled tasks (ECB daily at 17:30 UTC, etc.)
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
| PATCH | `/me` | Yes | Update profile (name, timezone, number_locale) |
| POST | `/me/avatar` | Yes | Upload / replace profile picture |
| POST | `/password-reset/request` | No | Send a password-reset email |
| POST | `/password-reset/confirm` | No | Set a new password via reset token |

### Firms & Team — `/api/v1/firms/`

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/` | authenticated | List the caller's Firms |
| POST | `/` | authenticated | Create a Firm (caller becomes Owner) |
| GET | `/{firm_id}` | member | Get Firm details (incl. currency & locale settings) |
| PATCH | `/{firm_id}` | Admin+ | Rename a Firm |
| DELETE | `/{firm_id}` | Owner | Delete a Firm |
| PATCH | `/{firm_id}/currency` | Admin+ | Set default currency, number locale, exchange rate mode |
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
| GET | `/{firm_id}/exchange-rates` | member | List firm exchange rates |
| POST | `/{firm_id}/exchange-rates` | Admin+ | Create / update a manual exchange rate |
| GET | `/{firm_id}/exchange-rates/export.csv` | member | Export exchange rates as CSV |

### Invitations (public) — `/api/v1/invitations/`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/{token}` | No | Preview an invitation |
| POST | `/{token}/accept` | No | Accept an invitation (creates account if needed) |

### CRM — `/api/v1/crm/`

#### Contacts

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/customers` | member | List / search contacts |
| POST | `/customers` | Worker+ | Create a contact |
| GET | `/customers/{id}` | member | Get a contact |
| PUT | `/customers/{id}` | Worker+ | Replace a contact |
| DELETE | `/customers/{id}` | Admin+ | Delete a contact |

#### Pipeline Records

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/records` | member | List records (filter by status / category / assignee / source / tag / date) |
| POST | `/records` | Worker+ | Create a record |
| GET | `/records/{id}` | member | Get a record |
| PATCH | `/records/{id}` | Worker+ | Update a record (stage/status changes auto-logged) |
| DELETE | `/records/{id}` | Admin+ | Delete a record |
| GET | `/records/{id}/activities` | member | Paginated activity timeline |
| GET | `/records/{id}/checkpoints` | member | List checkpoints |
| POST | `/records/{id}/checkpoints` | Worker+ | Create a checkpoint |
| PATCH | `/records/{id}/checkpoints/{cp_id}` | Worker+ | Update a checkpoint |
| DELETE | `/records/{id}/checkpoints/{cp_id}` | Admin+ | Delete a checkpoint |

#### Pipeline Configuration (Categories / Stages / Fields)

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/categories` | member | List all pipeline categories |
| POST | `/categories` | Admin+ | Create a category |
| PATCH | `/categories/{id}` | Admin+ | Update a category |
| DELETE | `/categories/{id}` | Admin+ | Delete a category (403 if records exist) |
| GET | `/categories/{id}/stages` | member | List stages for a category |
| POST | `/categories/{id}/stages` | Admin+ | Create a stage |
| PATCH | `/categories/{id}/stages/{stage_id}` | Admin+ | Update a stage |
| DELETE | `/categories/{id}/stages/{stage_id}` | Admin+ | Delete a stage (403 if records use it) |
| GET | `/categories/{id}/fields` | member | List field configuration for a category |
| POST | `/categories/{id}/fields/{field_key}` | Admin+ | Enable / upsert a field |
| PATCH | `/categories/{id}/fields/{field_key}` | Admin+ | Update a field's visibility / required flag |
| DELETE | `/categories/{id}/fields/{field_key}` | Admin+ | Remove a field from the category |

#### Activities & Proposals

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/activities` | Worker+ | Log an activity |
| PATCH | `/activities/{id}` | Worker+ | Edit an activity |
| DELETE | `/activities/{id}` | Worker+ | Soft-delete an activity |
| POST | `/activities/{id}/reactions` | Worker+ | Add / toggle an emoji reaction |
| GET | `/proposals` | member | List proposals |
| POST | `/proposals` | Worker+ | Create a proposal |
| GET | `/proposals/{id}` | member | Get a proposal |
| PATCH | `/proposals/{id}` | Worker+ | Update a proposal |

#### Tasks

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/tasks` | member | List tasks (filter by status / priority / kind / assignee / tag) |
| POST | `/tasks` | Worker+ | Create a task |
| GET | `/tasks/{id}` | member | Get a task |
| PATCH | `/tasks/{id}` | Worker+ | Update a task |
| DELETE | `/tasks/{id}` | Admin+ | Delete a task |
| POST | `/tasks/{id}/complete` | Worker+ | Mark a task as completed |
| POST | `/tasks/{id}/approve` | Worker+ | Approve or reject a task |
| GET | `/tasks/{id}/streamline-items` | member | List checklist / sub-task items |
| POST | `/tasks/{id}/streamline-items` | Worker+ | Add checklist / sub-task items |
| PATCH | `/tasks/{id}/streamline-items/{item_id}` | Worker+ | Toggle or update an item |

#### Automations

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/automations` | Admin+ | List automation rules |
| POST | `/automations` | Admin+ | Create an automation rule |
| GET | `/automations/{id}` | Admin+ | Get a rule |
| PATCH | `/automations/{id}` | Admin+ | Update a rule |
| DELETE | `/automations/{id}` | Admin+ | Delete a rule |
| GET | `/automations/{id}/runs` | Admin+ | List automation execution log |
| GET | `/automations/templates` | Admin+ | List built-in automation templates |
| POST | `/automations/from-template/{template_id}` | Admin+ | Create a rule from a template |

### ERP — `/api/v1/erp/`

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/time-entries` | member | List time entries (filter by user, entity, date) |
| POST | `/time-entries` | Worker+ | Create a time entry |
| PATCH | `/time-entries/{id}` | Worker+ | Edit a time entry |
| DELETE | `/time-entries/{id}` | Worker+ | Delete a time entry |
| GET | `/expenses` | member | List expense items |
| POST | `/expenses` | Worker+ | Create an expense item |
| PATCH | `/expenses/{id}` | Worker+ | Update an expense item |
| DELETE | `/expenses/{id}` | Admin+ | Delete an expense item |
| GET | `/revenues` | member | List revenue items |
| POST | `/revenues` | Worker+ | Create a revenue item |
| PATCH | `/revenues/{id}` | Worker+ | Update a revenue item |
| DELETE | `/revenues/{id}` | Admin+ | Delete a revenue item |
| GET | `/reports/summary` | member | Aggregated P&L summary |
| GET | `/documents` | member | List documents (filter by entity) |
| POST | `/documents` | Worker+ | Upload a document |
| DELETE | `/documents/{id}` | Admin+ | Delete a document |

### Integrations — `/api/v1/integrations/`

| Method | Path | Description |
|---|---|---|
| GET | `/ical/token` | Get signed iCal feed URL |
| GET | `/ical/tasks` | Public iCal feed (token-authenticated) |
| POST | `/import/records` | Bulk-import records from CSV |
| POST | `/import/customers` | Bulk-import contacts from CSV |
| GET | `/import/{job_id}` | Poll import job status |
| GET | `/import` | List recent import jobs |
| GET | `/export/records.csv` | Download records as CSV |
| GET | `/export/customers.csv` | Download contacts as CSV |
| GET | `/export/pipeline.pdf` | Download pipeline summary as PDF |
| POST | `/fakturoid/test` | Test Fakturoid API connection |
| POST | `/fakturoid/invoices` | Create an invoice in Fakturoid |

### Streamline — `/api/v1/streamline/`

| Method | Path | Description |
|---|---|---|
| GET | `/tools` | List all registered activity tools (label, icon, category, form schema) |
| GET | `/tools/{activity_type}` | Get details for a single tool |
| GET | `/toolbar/{entity_type}` | Get the ordered toolbar tool list for a given entity type |

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
