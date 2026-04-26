# Changelog

## v2.0.0 — Commercial Release

### ✨ New features

- **White-label branding** — upload a custom logo and set a brand colour per workspace (Pro tier)
- **Multi-language UI** — English and Czech; locale auto-detected from browser preferences
- **Public marketing site** — landing page at `/` with features, pricing, testimonials, and FAQ
- **Subscription gating** — Analytics dashboard requires Pro subscription; shows upgrade prompt otherwise
- **Onboarding wizard** — 5-step guided setup for new workspaces (invite, pipeline, email, integrations, review)
- **Super-admin panel** — staff users can list all firms and adjust subscription tiers
- **Plugin system** — register custom nav items, activity types, and webhook event types
- **Documentation** — full MkDocs site with getting started, self-hosting, API reference, and plugin authoring guides
- **Security policy** — `SECURITY.md` with responsible disclosure instructions
- **SLA** — uptime commitments and support response times

### 🔧 Improvements

- Brand colour applied via CSS custom property `--brand-color` across the entire app
- Dashboard shows setup banner until onboarding is complete
- Super-admin route `/app/superadmin` visible only to staff users

### 🐛 Bug fixes

- Session-based `is_staff` check now propagated to frontend auth store

---

## v1.0.0 — Initial Release

- Core CRM: contacts, deals, pipeline
- Firm / workspace isolation
- Email sequences
- Webhooks
- Activity feed
