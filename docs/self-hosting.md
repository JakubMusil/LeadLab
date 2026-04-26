# Self-Hosting Guide

## Docker (recommended)

```bash
docker compose up -d
```

The `docker-compose.yml` in the project root starts:

- `web` – Django application server (Gunicorn)
- `db` – PostgreSQL
- `redis` – Celery broker (optional for background tasks)

### Environment

Copy `.env.example` to `.env` and fill in:

```env
SECRET_KEY=change-me
DATABASE_URL=postgres://leadlab:password@db:5432/leadlab
ALLOWED_HOSTS=yourdomain.com,localhost
MEDIA_ROOT=/app/media
```

## Nginx reverse proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    location /media/ { alias /app/media/; }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Updates

```bash
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
docker compose restart web
```

## Backups

PostgreSQL:
```bash
pg_dump leadlab | gzip > leadlab-$(date +%F).sql.gz
```
