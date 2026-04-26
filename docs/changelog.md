# Changelog

## v3.0.0 — Platform Release

### ✨ New features

- **German and Polish UI** — full translations for `de` and `pl` locales; locale auto-detected from browser preferences; all four languages (English, Czech, German, Polish) available in Settings → Language
- **Locale coverage CI** — new `check-locales` script fails the build if any key present in `en.json` is missing from another locale file
- **Community locale guide** — `CONTRIBUTING_LOCALES.md` step-by-step guide for adding new UI languages
- **Demo data** — `python manage.py load_demo_data` creates a realistic sample workspace with contacts, leads, activities, and tasks for evaluators and developers
- **Business proposals** — create, send, and track professional sales proposals with drag-and-drop line items, PDF export, signed public links, and accept/reject workflow; full analytics tab
- **Plugin ecosystem** — Email Sequences, VoIP / Click-to-Call, LinkedIn Enrichment, and Slack Notifications first-party plugins; plugin config schema UI; public plugin registry
- **Workflow automation** — visual trigger → condition → action rule builder; Celery execution engine with per-rule logs; 5 built-in automation templates
- **Design system** — Storybook 8 component library; Chromatic visual regression CI; consistent design tokens and typography scale
- **Smart lead scoring** — configurable weighted rules produce a 0–100 score badge
- **Saved views** — named filter + sort presets persisted per user
- **Activity composer** — Tiptap rich-text editor, @mention teammates, emoji picker
- **Adaptive dashboard** — drag-and-drop widget layout persisted per user
- **Command palette** — `Cmd/Ctrl+K` fuzzy search across leads, customers, and navigation

### 🔧 Improvements

- Updated `README.md` with complete v3.0 feature list
- Updated `install.md` with demo data instructions and renumbered sections
- Updated documentation site (`docs/`) to reflect v3.0 feature set

---

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
