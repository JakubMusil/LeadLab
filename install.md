# Installation Guide

This guide walks you through setting up LeadLab for local development and for production.

---

## Prerequisites

| Requirement | Minimum version |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 14+ (optional for local dev — SQLite works out of the box) |
| Redis | 6+ (required only for async email / Celery tasks) |

---

## 1. Clone the Repository

```bash
git clone https://github.com/JakubMusil/LeadLab.git
cd LeadLab
```

---

## 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

LeadLab reads its configuration from environment variables. For local development you can export them in your shell or place them in a `.env` file and load it with a tool such as `direnv` or `python-dotenv`.

### Required for production, optional for local dev

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(insecure built-in)* | Django secret key — **must** be changed in production |
| `DJANGO_DEBUG` | `True` | Set to `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated list of allowed hostnames |

### Database (defaults to SQLite)

| Variable | Default | Description |
|---|---|---|
| `DB_ENGINE` | `django.db.backends.sqlite3` | Django database backend |
| `DB_NAME` | `db.sqlite3` (in project root) | Database name / path |
| `DB_USER` | *(empty)* | Database user |
| `DB_PASSWORD` | *(empty)* | Database password |
| `DB_HOST` | *(empty)* | Database host |
| `DB_PORT` | *(empty)* | Database port |

### Redis / Celery (optional for local dev)

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL, used as Celery broker and result backend |

### Stripe (optional for local dev)

| Variable | Default | Description |
|---|---|---|
| `STRIPE_SECRET_KEY` | *(empty)* | Stripe secret key for subscription management |
| `STRIPE_WEBHOOK_SECRET` | *(empty)* | Stripe webhook signing secret |

### Email (defaults to console backend)

| Variable | Default | Description |
|---|---|---|
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` | Django email backend |
| `EMAIL_HOST` | *(empty)* | SMTP server hostname |
| `EMAIL_PORT` | `587` | SMTP port |
| `EMAIL_USE_TLS` | `True` | Enable STARTTLS |
| `EMAIL_HOST_USER` | *(empty)* | SMTP username |
| `EMAIL_HOST_PASSWORD` | *(empty)* | SMTP password |
| `DEFAULT_FROM_EMAIL` | `noreply@leadlab.io` | Default sender address |

### AWS S3 (optional — falls back to local media storage)

| Variable | Default | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | *(empty)* | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | *(empty)* | AWS secret key |
| `AWS_STORAGE_BUCKET_NAME` | *(empty)* | S3 bucket name |
| `AWS_S3_REGION_NAME` | `eu-central-1` | S3 region |

---

## 5. Apply Migrations

```bash
python manage.py migrate
```

---

## 6. Create a Superuser (optional)

```bash
python manage.py createsuperuser
```

The prompt will ask for an email address and password. Use these credentials to access the Django admin at `/admin/`.

---

## 7. Run the Development Server

```bash
python manage.py runserver
```

The API is now available at `http://127.0.0.1:8000/api/v1/` and the interactive docs at `http://127.0.0.1:8000/api/v1/docs`.

---

## 8. Run the Celery Worker (optional)

Celery is only required for async outbound email dispatch. If you don't need it, the application degrades gracefully.

```bash
celery -A leadlab worker --loglevel=info
```

---

## Production Checklist

- Set `DJANGO_SECRET_KEY` to a long random string.
- Set `DJANGO_DEBUG=False`.
- Set `DJANGO_ALLOWED_HOSTS` to your domain(s).
- Use PostgreSQL — set all `DB_*` variables.
- Point `REDIS_URL` at a production Redis instance.
- Configure SMTP credentials for `EMAIL_*` variables.
- Run `python manage.py collectstatic` and serve the `staticfiles/` directory through a web server (nginx, etc.).
- Use gunicorn or uvicorn behind a reverse proxy:

  ```bash
  gunicorn leadlab.wsgi:application --bind 0.0.0.0:8000
  ```
