# LeadLab

**LeadLab** is a multi-tenant SaaS CRM backend built with Django and Django Ninja. It provides a clean REST API for managing sales leads, customers, tasks, and team collaboration — all scoped to isolated workspaces called *Firms*.

---

## Features

- **Multi-tenancy** — Every piece of data belongs to exactly one Firm. Users can be members of multiple Firms with different roles.
- **Lead pipeline** — Track opportunities through statuses: New → Contacted → Proposal → Negotiation → Won / Lost / Canceled.
- **Customer address book** — Reusable contact records with tags, custom metadata, and links to multiple leads.
- **Activity timeline** — Immutable event log per lead: comments, calls, meetings, emails, file uploads, status changes, and task events.
- **Task management** — To-do items scoped to leads with due dates, assignment, and automatic completion logging.
- **Role-based access control** — Three membership roles per Firm: Owner, Admin, and Worker.
- **Subscription tiers** — Free and Pro plans enforced at the API layer, backed by Stripe.
- **Async email dispatch** — Outbound emails queued via Celery / Redis.
- **File storage** — Local media or AWS S3 via `django-storages`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5+ / Django Ninja |
| Database | PostgreSQL (SQLite for local dev) |
| Task queue | Celery + Redis |
| Payments | Stripe |
| Storage | Local FS / AWS S3 |
| Auth | Session-based (`django_auth`) |

---

## Project Structure

```
leadlab/          # Django project settings, URL conf, Celery config, root API
users/            # Custom User model (email-based), register / login / logout endpoints
firms/            # Firm & Membership models, tenant middleware, role-based auth helpers
crm/              # Customer, Lead, Activity, Task models and API endpoints
manage.py
requirements.txt
```

---

## API Overview

All endpoints are served at `/api/v1/` and require session authentication (except `/api/v1/users/register` and `/api/v1/users/login`). Every CRM request also requires an `X-Firm-ID` header to identify the active tenant.

### Authentication — `/api/v1/users/`

| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create a new account |
| POST | `/login` | Start a session |
| POST | `/logout` | End the current session |
| GET | `/me` | Return the current user |

### Firms & Team — `/api/v1/firms/`

| Method | Path | Role required | Description |
|---|---|---|---|
| GET | `/` | any member | List the caller's Firms |
| POST | `/` | authenticated | Create a Firm (caller becomes Owner) |
| GET | `/{firm_id}` | member | Get Firm details |
| DELETE | `/{firm_id}` | Owner | Delete a Firm |
| GET | `/{firm_id}/members` | member | List team members |
| POST | `/{firm_id}/members` | Admin+ | Invite a member |
| DELETE | `/{firm_id}/members/{id}` | Admin+ | Remove a member |

### CRM — `/api/v1/crm/`

| Method | Path | Role required | Description |
|---|---|---|---|
| GET | `/customers` | member | List / search customers |
| POST | `/customers` | Worker+ | Create a customer |
| GET | `/customers/{id}` | member | Get a customer |
| PUT | `/customers/{id}` | Worker+ | Update a customer |
| DELETE | `/customers/{id}` | Admin+ | Delete a customer |
| GET | `/leads` | member | List leads (filter by status / assignee) |
| POST | `/leads` | Worker+ | Create a lead |
| GET | `/leads/{id}` | member | Get a lead |
| PATCH | `/leads/{id}` | Worker+ | Update a lead (status change is auto-logged) |
| DELETE | `/leads/{id}` | Admin+ | Delete a lead |
| GET | `/leads/{id}/activities` | member | Paginated timeline for a lead |
| POST | `/activities` | Worker+ | Log an activity (unified action hub) |
| GET | `/tasks` | member | List tasks |
| POST | `/tasks` | Worker+ | Create a task |
| POST | `/tasks/{id}/complete` | Worker+ | Mark a task as completed |

Interactive API docs are available at `/api/v1/docs` when the server is running.

---

## License

MIT
