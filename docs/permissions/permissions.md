# Permission System

LeadLab uses a granular, DB-backed permission system introduced in v2.0. Every
action in the application is protected by a **permission code** evaluated
against the requesting user's role(s) and scope.

---

## Permission codes

| Code | Group | Description |
|---|---|---|
| `record.view` | Records | View pipeline records |
| `record.create` | Records | Create new records |
| `record.edit` | Records | Edit existing records |
| `record.delete` | Records | Delete records |
| `category.view` | Categories | View pipeline categories |
| `category.manage` | Categories | Create / edit / delete categories |
| `team.manage` | Teams | Create / edit / delete teams, manage members |
| `role.manage` | Roles | Create / edit / delete custom roles, assign permissions |
| `billing.manage` | Billing | Manage subscription and billing settings |
| `firm.delete` | Firm | Delete the workspace (Owner only) |
| `firm.transfer` | Firm | Transfer ownership (Owner only) |
| `integrations.manage` | Integrations | Install / configure plugins and webhooks |
| `report.view` | Reports | Access reporting and analytics |
| `activity.create` | Streamline | Create activities and comments in the streamline |
| `streamline.view_all` | Streamline | View all streamline activities including restricted ones |
| `proposal.create` | Proposals | Create and manage proposals |

---

## Scopes

Scopes control *which records* a user can see when they have the relevant
permission:

| Scope | Meaning |
|---|---|
| `own` | Records where the user is `created_by` or `assigned_to` |
| `team` | Records belonging to any member of the user's team |
| `category` | Records in categories the user has an explicit `CategoryGrant` for |
| `all` | All records in the workspace |

The effective scope is the **widest** of:
1. `Membership.default_scope` (set by admins at member-management time)
2. Any active `CategoryGrant` entries → scope becomes at least `category`
3. Owner shortcut → always `all`

---

## Decision algorithm

```
can(user, firm, action, resource=None):
  1. No firm membership           → DENY
  2. Is Owner                     → ALLOW
  3. effective_perms = ∪ role.permissions (DB) ∪ legacy map (fallback)
  4. action ∉ effective_perms     → DENY
  5. If resource provided:
       scope = max(default_scope, category_scope, direct grant)
       evaluate scope rule        → ALLOW / DENY
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/firms/{id}/permission-catalogue` | List all permission codes |
| `GET` | `/api/v1/firms/{id}/me/permissions` | Current user's effective permissions |
| `GET` | `/api/v1/firms/{id}/members` | Members list now includes `roles[]` and `permissions[]` |

---

## Security rules

- **Tenant boundary** – no grant can cross workspace boundaries.
- **Privilege escalation prevention** – you cannot grant a permission you do not
  hold yourself.
- **Audit trail** – every permission change is recorded in
  `PermissionAuditLog` (append-only).
- **Owner role** – `is_system=True`, cannot be deleted or modified.
