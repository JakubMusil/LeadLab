# Teams

Teams group members of a workspace so that a **Manager** or **Admin** can
assign records and visibility scopes at the team level instead of individually.

---

## Overview

- A workspace can have any number of teams.
- Teams are **single-level** (no nested sub-teams in v1).
- Each membership has an optional *primary team* (`Membership.team`), used
  for `scope=team` resolution.
- A membership can also participate in additional teams through the
  `TeamMembership` many-to-many relation.

---

## Creating a team

1. Navigate to **Settings → Teams** (requires `team.manage` permission).
2. Click **New Team**, enter a name and choose a colour.
3. Expand the team row and add members using the member picker.

---

## Scope resolution for teams

When a membership has `default_scope = "team"`:

```
visible records = records where assigned_to ∈ team.members
                  OR created_by = user
                  OR assigned_to = user
```

The team used for resolution is `Membership.team` (the primary team FK).

---

## API reference

| Method | Path | Guard |
|---|---|---|
| `GET` | `/api/v1/firms/{id}/teams` | Any member |
| `POST` | `/api/v1/firms/{id}/teams` | `team.manage` |
| `PATCH` | `/api/v1/firms/{id}/teams/{team_id}` | `team.manage` |
| `DELETE` | `/api/v1/firms/{id}/teams/{team_id}` | `team.manage` |
| `POST` | `/api/v1/firms/{id}/teams/{team_id}/members/{membership_id}` | `team.manage` |
| `DELETE` | `/api/v1/firms/{id}/teams/{team_id}/members/{membership_id}` | `team.manage` |

---

## Example: onboarding a Sales team

```http
POST /api/v1/firms/{firm_id}/teams
Content-Type: application/json

{"name": "Sales CZ", "color": "#22c55e"}
```

```http
POST /api/v1/firms/{firm_id}/teams/{team_id}/members/{membership_id}
```

Then set each Sales member's `default_scope` to `"team"` via
`PATCH /api/v1/firms/{firm_id}/members/{membership_id}`.
