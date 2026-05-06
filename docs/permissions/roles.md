# Roles

LeadLab supports both **system roles** (pre-created for every workspace) and
**custom roles** (defined by Owners and Admins).

---

## System roles

| Role | Code | Key permissions |
|---|---|---|
| **Owner** | `owner` | All permissions; cannot be removed or edited |
| **Admin** | `admin` | Everything except `billing.manage`, `firm.delete`, `firm.transfer` |
| **Member** | `member` | `record.*`, `activity.create`, `proposal.create`, `report.view` |
| **Guest** | `guest` | `record.view`, `category.view` (read-only) |

> `WORKER` is a deprecated alias for `member` retained for backward
> compatibility. New code and invitations should use `member`.

---

## Custom roles

Owners and Admins with `role.manage` permission can create additional roles:

1. Navigate to **Settings → Roles**.
2. Click **New Role** and provide a code, name, and description.
3. Use the permission matrix to toggle individual permissions.

**Constraints:**
- Custom roles cannot receive `billing.manage`, `firm.delete`, or `firm.transfer`
  (Owner-only permissions).
- You can only grant permissions that you yourself hold (no privilege
  escalation).

---

## Assigning roles

Roles are assigned per **Membership** (user ↔ workspace). A membership can
hold multiple roles; the effective permission set is the **union** of all
assigned roles.

### Via invitation

```json
POST /api/v1/firms/{id}/members
{
  "email": "jane@example.com",
  "role_codes": ["member", "my-custom-role"],
  "default_scope": "category",
  "team_id": "<uuid>"
}
```

### Via member management UI

**Settings → Team** → click a member row → edit Roles, Scope, Team fields.

---

## API reference

| Method | Path | Guard |
|---|---|---|
| `GET` | `/api/v1/firms/{id}/roles` | Any member |
| `POST` | `/api/v1/firms/{id}/roles` | `role.manage` |
| `PATCH` | `/api/v1/firms/{id}/roles/{role_id}` | `role.manage`, custom only |
| `DELETE` | `/api/v1/firms/{id}/roles/{role_id}` | `role.manage`, custom only |
| `PUT` | `/api/v1/firms/{id}/roles/{role_id}/permissions` | `role.manage` + privilege check |
