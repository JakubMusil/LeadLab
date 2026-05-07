# Installation Guide

This guide walks you through setting up LeadLab for local development and for production.

---

## Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Python | 3.11+ | Backend runtime |
| Node.js | 20+ | Required to build the Vue 3 SPA |
| PostgreSQL | 16+ | Optional for local dev — SQLite works out of the box |
| Redis | 7+ | Required for Celery, Django Channels, and caching |

> **Tip:** You can skip Node.js if you run the project through Docker, which handles the SPA build automatically.

---

## Option A — Docker Compose (recommended)

The included `docker-compose.yml` starts PostgreSQL, Redis, the Django web server (Daphne), the Celery worker, and Celery Beat (periodic tasks) in one command.

```bash
git clone https://github.com/JakubMusil/LeadLab.git
cd LeadLab

# Copy and edit the environment file
cp .env.example .env   # or create .env manually — see §4 below

docker compose up --build
```

The API is now available at `http://localhost:8000/api/v1/` and the web app at `http://localhost:8000/`.

To apply migrations or create a superuser inside the running container:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

---

## Option B — Local Development (without Docker)

### 1. Clone the Repository

```bash
git clone https://github.com/JakubMusil/LeadLab.git
cd LeadLab
```

---

### 2. Create a Python Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

---

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Build the Frontend SPA

The Vue 3 SPA must be compiled before the Django app can serve it.

```bash
cd frontend-spa
npm install
npm run build-only
cd ..
```

The compiled assets are written to `frontend/static/frontend/spa/` and picked up by Django's static file serving.

---

### 5. Configure Environment Variables

LeadLab reads its configuration from environment variables. For local development you can export them in your shell or place them in a `.env` file and load it with a tool such as `direnv` or `python-dotenv`.

#### Core Django

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(insecure built-in)* | Django secret key — **must** be changed in production |
| `DJANGO_DEBUG` | `True` | Set to `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated list of allowed hostnames |

#### Database (defaults to SQLite)

| Variable | Default | Description |
|---|---|---|
| `DB_ENGINE` | `django.db.backends.sqlite3` | Django database backend |
| `DB_NAME` | `db.sqlite3` (in project root) | Database name / path |
| `DB_USER` | *(empty)* | Database user |
| `DB_PASSWORD` | *(empty)* | Database password |
| `DB_HOST` | *(empty)* | Database host |
| `DB_PORT` | *(empty)* | Database port |

#### Redis / Celery (optional for local dev, required in production)

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL — used as Celery broker, result backend, channel layer, and cache |

#### Stripe

| Variable | Default | Description |
|---|---|---|
| `STRIPE_SECRET_KEY` | *(empty)* | Stripe secret key for subscription management |
| `STRIPE_WEBHOOK_SECRET` | *(empty)* | Stripe webhook signing secret |
| `STRIPE_PRICE_ID` | *(empty)* | Stripe Price ID for the Pro subscription |

#### Email (defaults to console backend)

| Variable | Default | Description |
|---|---|---|
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` | Django email backend |
| `EMAIL_HOST` | *(empty)* | SMTP server hostname |
| `EMAIL_PORT` | `587` | SMTP port |
| `EMAIL_USE_TLS` | `True` | Enable STARTTLS |
| `EMAIL_HOST_USER` | *(empty)* | SMTP username |
| `EMAIL_HOST_PASSWORD` | *(empty)* | SMTP password |
| `DEFAULT_FROM_EMAIL` | `noreply@leadlab.io` | Default sender address |

#### AWS S3 (optional — falls back to local media storage)

| Variable | Default | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | *(empty)* | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | *(empty)* | AWS secret key |
| `AWS_STORAGE_BUCKET_NAME` | *(empty)* | S3 bucket name |
| `AWS_S3_REGION_NAME` | `eu-central-1` | S3 region |

#### Web Push / VAPID (optional)

| Variable | Default | Description |
|---|---|---|
| `VAPID_PRIVATE_KEY` | *(empty)* | VAPID private key for Web Push |
| `VAPID_PUBLIC_KEY` | *(empty)* | VAPID public key served to browsers |
| `VAPID_ADMIN_EMAIL` | `admin@leadlab.io` | Contact email embedded in VAPID claims |

To generate a VAPID key pair:

```bash
python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print('Private:', v.private_key()); print('Public:', v.public_key())"
```

#### Brute-force Protection (django-axes)

| Variable | Default | Description |
|---|---|---|
| `AXES_FAILURE_LIMIT` | `10` | Failed login attempts before lockout |
| `AXES_ENABLE` | `True` | Set to `False` to disable axes (e.g. in tests) |

#### Error Tracking (optional)

| Variable | Default | Description |
|---|---|---|
| `SENTRY_DSN` | *(empty)* | Sentry DSN — Sentry is only initialised when this is set |

#### Content Security Policy

| Variable | Default | Description |
|---|---|---|
| `CSP_DEFAULT_SRC` | `'self'` | CSP `default-src` directive |
| `CSP_SCRIPT_SRC` | `'self' 'unsafe-inline' https://cdn.jsdelivr.net` | CSP `script-src` directive |
| `CSP_STYLE_SRC` | `'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net` | CSP `style-src` directive |
| `CSP_FONT_SRC` | `'self' https://fonts.gstatic.com` | CSP `font-src` directive |
| `CSP_IMG_SRC` | `'self' data: blob:` | CSP `img-src` directive |
| `CSP_CONNECT_SRC` | `'self' wss: ws:` | CSP `connect-src` directive |
| `CSP_WORKER_SRC` | `'self' blob:` | CSP `worker-src` directive |
| `CSP_REPORT_URI` | *(empty)* | Optional CSP violation report endpoint |

#### Miscellaneous

| Variable | Default | Description |
|---|---|---|
| `RATELIMIT_ENABLE` | `True` | Set to `False` to disable API rate limiting globally |
| `FRONTEND_URL` | *(empty)* | Public base URL of the frontend; used in Stripe redirect URLs |

---

### 6. Apply Migrations

```bash
python manage.py migrate
```

---

### 7. Create a Superuser (optional)

```bash
python manage.py createsuperuser
```

The prompt will ask for an email address and password. Use these credentials to access the Django admin at `/admin/` and the super-admin CRM panel at `/app/superadmin`.

---

### 8. Load Demo Data (optional)

Populate the database with a sample workspace, contacts, leads, activities, and tasks for evaluation or development:

```bash
python manage.py load_demo_data
```

This creates a demo user (`demo@leadlab.io` / `Demo1234!`) and a workspace called *LeadLab Demo* with realistic sample data. You can customise the email, password, and workspace name:

```bash
python manage.py load_demo_data --email you@example.com --password MyPass123! --firm-name "Acme Corp"
```

---

### 9. Run the Development Server

```bash
python manage.py runserver
```

The API is now available at `http://127.0.0.1:8000/api/v1/` and the interactive docs at `http://127.0.0.1:8000/api/v1/docs`.

> **WebSockets:** The Django development server does not support WebSockets. To test real-time push events locally, run Daphne instead:
>
> ```bash
> daphne -b 127.0.0.1 -p 8000 leadlab.asgi:application
> ```

---

### 10. Run the Celery Worker (optional)

Celery is required for async outbound email, email invitations, password-reset emails, and CSV import jobs. If Redis is not running the application degrades gracefully.

```bash
celery -A leadlab worker --loglevel=info
```

To also process scheduled tasks (weekly pipeline digest), run Celery Beat alongside the worker:

```bash
celery -A leadlab beat --loglevel=info
```

---

## Production Checklist

- Set `DJANGO_SECRET_KEY` to a long random string.
- Set `DJANGO_DEBUG=False`.
- Set `DJANGO_ALLOWED_HOSTS` to your domain(s).
- Use PostgreSQL — set all `DB_*` variables.
- Point `REDIS_URL` at a production Redis instance (enables Celery, Channels, and Redis cache).
- Configure SMTP credentials for `EMAIL_*` variables.
- Set `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and `STRIPE_PRICE_ID` to enable subscriptions.
- Set `VAPID_PRIVATE_KEY` and `VAPID_PUBLIC_KEY` to enable Web Push notifications.
- Set `SENTRY_DSN` to enable error tracking (recommended).
- Set `FRONTEND_URL` to your public domain for correct Stripe redirect URLs.
- Run `python manage.py collectstatic --noinput` and serve `staticfiles/` via a web server (nginx, CDN, etc.).
- Use **Daphne** (ASGI) rather than a plain WSGI server to support WebSockets:

  ```bash
  daphne -b 0.0.0.0 -p 8000 leadlab.asgi:application
  ```

  Or via the Docker image (handled automatically by `docker-compose.yml`):

  ```bash
  docker compose up -d
  ```

- Run the Celery worker and Celery Beat as separate processes (or containers):

  ```bash
  celery -A leadlab worker --loglevel=info
  celery -A leadlab beat --loglevel=info
  ```

