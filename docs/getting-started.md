# Getting Started

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+

## Installation

```bash
git clone https://github.com/JakubMusil/LeadLab.git
cd LeadLab
cp .env.example .env   # fill in your values
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

## Running the frontend

```bash
cd frontend-spa
npm install
npm run dev
```

## Running the backend

```bash
python manage.py runserver
```

Visit `http://localhost:8000` to see the marketing page or `http://localhost:5173` during development.

## First sign-in

1. Navigate to `/app/` and register an account.
2. Create your workspace (Firm).
3. Complete the onboarding wizard to invite teammates and customise your pipeline.

## Environment variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `MEDIA_ROOT` | Filesystem path for uploads |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts |
