# API Reference

The LeadLab API is available at `/api/v1/` and is documented interactively via OpenAPI.

Visit `/api/v1/docs` when running a local instance.

## Authentication

LeadLab uses session authentication. POST to `/api/v1/auth/login/` with `email` and `password`. A session cookie is set on success.

## Endpoints overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/login/` | Sign in |
| POST | `/api/v1/auth/logout/` | Sign out |
| GET | `/api/v1/auth/me/` | Current user |
| GET | `/api/v1/firms/` | List firms |
| POST | `/api/v1/firms/` | Create firm |
| GET | `/api/v1/firms/{id}/` | Get firm |
| PUT | `/api/v1/firms/{id}/` | Update firm |
| POST | `/api/v1/firms/{id}/branding/` | Update branding (Pro) |
| GET | `/api/v1/firms/{id}/contacts/` | List contacts |
| POST | `/api/v1/firms/{id}/contacts/` | Create contact |
| GET | `/api/v1/firms/{id}/deals/` | List deals |
| POST | `/api/v1/firms/{id}/deals/` | Create deal |
| GET | `/api/v1/firms/{id}/activities/` | List activities |
| POST | `/api/v1/firms/{id}/webhooks/` | Register webhook |

## Pagination

All list endpoints accept `page` (1-based) and `page_size` (default 20).

## Branding endpoint

```http
POST /api/v1/firms/{id}/branding/
Content-Type: multipart/form-data

logo: <file>           (optional)
primary_color: #e63946  (optional)
```
