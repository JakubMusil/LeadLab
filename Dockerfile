FROM node:20-slim AS spa-builder

WORKDIR /build/frontend-spa
COPY frontend-spa/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend-spa/ ./
RUN npm run build-only

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy the built SPA assets from the builder stage
COPY --from=spa-builder /build/frontend/static/frontend/spa ./frontend/static/frontend/spa

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "leadlab.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
